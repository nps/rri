#!/usr/bin/env python

import inspect
import re
import sys


EXIT_SUCC = 0
EXIT_PERM = 100
EXIT_TEMP = 111
DEBUG = True
VALID_NAME_CHAR = re.compile("\w")


def _debug(msg):
    if DEBUG:
        print >> sys.stderr, "[DEBUG]: %s" % msg


def _get_trace():
    trace = inspect.trace()
    try:
        sys.stderr.write("TraceBack:\n")
        for t in trace:
            # second element of trace is lineno, third is function name
            sys.stderr.write("\tIn function: '" + t[3] + "' at line: " + str(t[2]) + "\n")
    finally:
        del trace


class Rule:
    def __init__(self, name):
        self._name = name
        self._rhs = None
        self._rx = None

    def set_body(self, body):
        if self._rhs:
            raise Exception("%s rule already has a body" % self._name())
        else:
            self._rhs = body
            self._rx = re.compile(self._rhs)

    def regex(self):
        return self._rx

    def string(self):
        return self._rhs

    def name(self):
        return self._name


class TheRules:
    def __init__(self, intprtr):
        self._rules = dict()
        self._intprtr = intprtr
        self._index = 0

    def add_rule(self,rule):
        name = rule.name()
        if name is None:
            raise Exception("Cannot add an anonymous rule to the set")
        self._rules[name] = rule

    def __iter__(self):
        self._index = len(self._rules.values())
        return self

    def next(self):
        if self._index == 0:
            raise StopIteration
        self._index = self._index - 1
        return self._rules.values()[self._index]

    def get_rule(self,r):
        if not self._rules.has_key(r):
            raise Exception("No rule for type: %s found" % r)
        return self._rules.get(r)


# Essentally an abstract state class we derive meaningful states from
class InterpretterState:
    def __init__(self, intprtr):
        self._intprtr = intprtr

    def analyze_token(self,tok):
        pass

    def _die(self,msg):
        raise Exception(msg)


class InRuleState(InterpretterState):
    def __init__(self, intprtr, rule):
        InterpretterState.__init__(self, intprtr)
        self._rule = rule
        self._rule_started = False
        self._rule_ended = False
        self._rule_body = ""
        self._eat_space = False

    def analyze_token(self,tok):
        if not self._rule_started:
            if tok.isspace():
                pass
            elif tok == "\"":
                _debug("%s rule started" % self._rule.name())
                self._rule_started = True
            elif tok == 's':
                self._eat_space = True
            else:
                self._die("Unexpected token %s at line %s, char %s"
                    %  (tok.encode('string_escape', self._intprtr.lineno(),
                    self._intprtr.charno())))

        elif not self._rule_ended:
            if tok == "\"":
                self._rule_ended = True
            elif tok.isspace():
                if self._eat_space:
                    pass
                else:
                    self._rule_body += tok
            else:
                self._rule_body += tok
        else:
            self._rule.set_body(self._rule_body)
            self._intprtr._rules.add_rule(self._rule)
            _debug("Compiled regex for rule: %s" % self._rule.name())
            self._intprtr.enter_state(LiminalState(self._intprtr))


class EnteringRuleState(InterpretterState):
    def __init__(self, intprtr):
        InterpretterState.__init__(self, intprtr)
        self._name_frozen = False
        self._rule_name = ""

    def analyze_token(self,tok):
        if tok.isspace():
            if not self._name_frozen:
                self._name_frozen = True
                _debug("Entering rule type: %s" % self._rule_name)
            # Consume remaining whitespace
            else:
                pass
        elif re.match(VALID_NAME_CHAR, tok):
            if not self._name_frozen:
                self._rule_name += tok
            else:
                self._die("Unexpected token %s at line %s, char %s"
                    %  (tok.encode('string_escape', self._intprtr.lineno(),
                    self._intprtr.charno())))
        elif tok == '=':
            if not self._name_frozen:
                self._die("Unexpected token %s at line %s, char %s"
                    %  (tok.encode('string_escape', self._intprtr.lineno(), 
                    self._intprtr.charno())))
            else:
                rule = Rule(self._rule_name)
                self._intprtr.enter_state(InRuleState(self._intprtr, rule))
        else:
                self._die("Unexpected token %s at line %s, char %s"
                    %  (tok.encode('string_escape', self._intprtr.lineno(), 
                    self._intprtr.charno())))


class InCommentState(InterpretterState):
    def analyze_token(self,tok):
        if tok == '\n':
            self._intprtr.enter_state(LiminalState(self._intprtr))
        else:
            pass


# The transitional state. We are not in a rule or a comment. It's our initial
# state. All it does is consume whitespace, transition to beefier states,
# or barf if it sees a token that violates the internal grammar rules
class LiminalState(InterpretterState):
    def analyze_token(self,tok):
        if tok == '@':
            self._intprtr.enter_state(EnteringRuleState(self._intprtr))
        elif tok == '#':
            self._intprtr.enter_state(InCommentState(self._intprtr))
        elif tok.isspace():
            pass
        else:
            self._die("Unexpected token %s at line %s, char %s"
                    %  (tok.encode('string_escape'), self._intprtr.lineno(),
                    self._intprtr.charno()))


# The rule interpretter. Reads the rules does some lexing, delegates actions
# to its internal states
class RuleInterpretter:
    def __init__(self, grammar):
        self._charn = 0
        self._linen = 0
        self._curr_tok = None
        self._grammar = grammar
        self._rules = TheRules(self)
        self._state = LiminalState(self)

    # we delegate analysis to our current state
    def _analyze_token(self,tok):
        self._state.analyze_token(tok)

    # pass the current token along for analysis. Escaped chars are considered
    # single tokens, so we need to lex them as such, and we do that here
    def tokenize_line(self, line):

        _debug("Tokenizing line %s" % str(self.lineno()))

        self._charn = 0
        for tok in line:

            if self._curr_tok is None:
                self._curr_tok = tok

                # we found an escape, we need to grab the next token to know
                # if we got ourselves an escape char or a literal escape char
                # sequence (ie a newline '\n' -> one tok vs. '\\n' -> two tok:
                # '\', 'n'
                # so let's get the next token to see...
                if self._curr_tok == '\\':
                    continue

            # so we have already have a stored escape char. what to do with it?
            elif self._curr_tok == '\\':

                # the new token is another escape char. we are dealing with
                # a literal escape char, so pass that along as such, use
                # analyze the original escape char as an individual token,
                if tok == '\\':
                    pass
                # we are escaping some char in the rule. so treat the saved
                # escape and this token as a single unit, incr the char counter
                # only by one, analyze this as a single token
                else:
                    self._curr_tok += tok
            self._charn += 1
            self._analyze_token(self._curr_tok)
            # reset current tok for state purity
            self._curr_tok = None

    # the internal driver
    def interpret(self):
        _debug("Initiating grammar analysis")
        for line in self._grammar:
            self._linen += 1
            self.tokenize_line(line)
        _debug("EOF reached")
        return self._rules

    def lineno(self):
        return str(self._linen)

    def charno(self):
        return str(self._charn)

    def add_rule(self, rule):
        self._rules.add_rule(rule)

    # this is implemented with a state pattern. the states will do the analysis,
    # we just need to check our state transitions are valid
    def enter_state(self, state):
        if not issubclass(state.__class__, InterpretterState):
            raise TypeError(state.__class__ + " is not a type of InterpretterState")
        elif isinstance(state, self._state.__class__):
            _debug("The current RuleInterpretter is already in a %s No action will be taken"
                    % state.classname())
        else:
            _debug("Entering: %s" % state.__class__.__name__)
            self._state = state


def main(args):
    usage = '''%s: [-h] rule_file''' % args[0]
    if '-h' in args or len(args) < 2:
        print >> sys.stderr, usage
        sys.exit(EXIT_TEMP)
    try:
        with open(args[1], 'r') as fo:
            interpretter = RuleInterpretter(fo.readlines())
            rules = interpretter.interpret()
            print "Compiled the following rules:"
            for rule in rules:
                print "name: %s\ndef: %s\nregex: %s" % (rule.name(), rule.string(), rule.regex())
    except Exception, e:
        print >> sys.stderr, "[ERROR]: %s" % str(e)
        _get_trace()
        sys.exit(EXIT_PERM)


if __name__ == '__main__':
    main(sys.argv)


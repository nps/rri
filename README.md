== rri, a regex rule interpreter ==

= Description =
This is an exercise in writing a simple interpreter. Given a rule file that
follows the BNF described below, the interpreter will compile valid rule
definitions into python RegexObjects. Implementing richer interpreter actions
would likely require additional modifications to the rules interface, but
should nevertheless be relatively straightforward.

= Package contents =
regex_rule_interpreter.py: Defines rule and interpreter classes and internal
states. Provides a main method with which one can test interpreter functionality.

sample_rules: text file, containing a sample valid rule definition

= Rule definition (pseudo) BNF =
regex_rule = <regex_rule_start_sym><regex_rule_name> <regex_rule_definition_sym> <regex_rule_body>

regex_rule_start_sym = '@'
regex_rule_name = [a-zA-Z0-9_]+
regex_rule_definition_sym = '='
regex_rule_body = <meta_sym>? <quote> <python_regex> <quote>
meta_sym = 's'
quote = '"'
python_regex = (Consult the python language reference for this).

meta_sym definitions :
s = ignore whitespace in python_regex body. this allows for (somewhat) legible
 regex definitions, but also requires that any whitespace in the intended
 to be present in the regex needs to be escaped or reference by a special
 char (e.g. \n, \t, \s)



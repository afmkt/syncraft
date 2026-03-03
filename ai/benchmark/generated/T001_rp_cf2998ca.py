from syncraft import Syntax

# Parse a single integer
number = Syntax.rp(r'\d+').map(int)

# Separator: comma with optional surrounding whitespace
sep = Syntax.rp(r'\s*,\s*')

# List of one or more numbers separated by the separator
list_ = number.sep_by1(sep)

# Top-level grammar: parse to a tuple, generate a string representation
grammar = list_.map(tuple).to(lambda lst: '(' + ', '.join(map(str, lst)) + ')')

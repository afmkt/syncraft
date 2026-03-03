from syncraft import Syntax

grammar = Syntax.rp(r'\d+(?:\s*,\s*\d+)*').transform(
    lambda s: f"({', '.join(x.strip() for x in s.split(','))})"
)

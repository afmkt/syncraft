from syncraft import Syntax

S = Syntax.set()
number = S.rp(r"[0-9]+").bimap(int, str)
comma = S.rp(r"\s*,\s*")
grammar = number.sep_by(comma).bimap(tuple, list)

from syncraft import Syntax

S = Syntax.set()
number = S.rp(r"[0-9]+").map(int)
comma = S.rp(r"\s*,\s*")
grammar = number.sep_by(comma).bimap(tuple, lambda t: ", ".join(map(str, t)))

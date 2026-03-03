from syncraft import Grammar, Syntax, grammar, rule

S = Syntax.set()

@grammar
class NumberListGrammar(Grammar):
    number = S.rp(r"[0-9]+").map(int)
    comma = S.rp(r"\s*,\s*")
    root = rule(number.sep_by(comma).map(lambda xs: tuple(xs)), is_root=True)

grammar = NumberListGrammar.root

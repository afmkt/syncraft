from syncraft import Syntax

grammar = Syntax.rp(r"""
    start = list
    list = int (ws? ',' ws? int)*
    int = /\d+/
    ws = /\s*/
""").map(lambda items: tuple([int(items[0])] + [int(group[-1]) for group in items[1]]))

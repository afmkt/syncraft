from __future__ import annotations

from syncraft.syntax import Syntax as S














if __name__ == "__main__":
    
    g = S.re(r"'([^'\\]|\\.)*'|\"([^\"\\]|\\.)*\"")
    print(g.parse('"a a a"'))
    print(g.parse('"a "a a"'))
    print(g.parse('"a \'a a"'))

    print(g.parse("'a a a'"))
    print(g.parse("'a \'a a'"))
    print(g.parse("'a \"a a'"))

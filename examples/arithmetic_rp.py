from syncraft.syntax import Syntax as S


num = S.rp(r"[0-9]+").bimap(int, str)
op = S.rp(r"[+\-*/]")

expr: S = S.success(None)
expr = S.lazy(lambda: S.rp(
    r"(?&num)|(\((?&expr)\s*(?&op)\s*(?&expr)\))",
    num=num,
    op=op,
    expr=expr,
))


if __name__ == "__main__":
    print(expr.parse("7"))
    print(expr.parse("(2+3)"))
    print(expr.parse("((1+2)*3)"))

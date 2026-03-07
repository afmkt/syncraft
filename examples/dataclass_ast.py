from dataclasses import dataclass

from syncraft.syntax import Syntax as S


@dataclass
class Number:
    value: int


number = S.rp(r"[0-9]+")
typed_number = number.bimap(lambda s: Number(int(s)), lambda n: str(n.value))


if __name__ == "__main__":
    ast = typed_number.parse("42")
    print(ast)
    print(typed_number.generate(ast).render())

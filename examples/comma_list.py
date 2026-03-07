from syncraft.syntax import Syntax as S


word = S.rp(r"[a-zA-Z_]+")
comma = S.lit(",")
csv = word.sep_by(comma)


if __name__ == "__main__":
    print(csv.parse("alpha,beta,gamma"))

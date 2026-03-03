from syncraft.syntax import Syntax as S
from syncraft.parser import parse_string

ident = S.rp(r"[A-Za-z_][A-Za-z0-9_]*", name="ident")
integer = S.rp(r"[0-9]+", name="integer")
quoted_string = S.rp(r'"[^"]*"', name="quoted_string")
value = S.rp(r"(?&integer)|(?&quoted_string)", name="value", integer=integer, quoted_string=quoted_string)
pair = S.rp(r"(?&ident)\s*:\s*(?&value)", name="pair", ident=ident, value=value)

grammar = pair

if __name__ == "__main__":
    examples = ["count:42", "name : \"mike\""]
    for ex in examples:
        print(ex, "->", parse_string(grammar, ex))

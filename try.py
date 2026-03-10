from dataclasses import dataclass
from syncraft.syntax import Syntax as S
from syncraft.generator import generate_with
from syncraft.ast import Many
from rich import print
@dataclass(frozen=True)
class Factor:
    char: str
    op: str

# Core combinators only (no rp)
char = S.lit("a") | S.lit("b")
op = S.lit("+") | S.lit("*")
factor_pair_syn = char + op

# Case-based transform (same family as EBNF uses)
factor_syn = factor_pair_syn.case(
    (lambda env: (env.char, env.op), 
     lambda env: Factor(char=env.char, op=env.op)),
)

# Many repetition
rule_syn = factor_syn.many(at_least=2, at_most=2)

# Input: two distinct factors
test_input = (
    Factor(char="a", op="*"),
    Factor(char="b", op="+"),
)

result = generate_with(rule_syn, test_input, replay=True)
# Expected: [('a', '*'), ('b', '+')]
# Actual:   [('a', '*'), ('a', '*')]  ❌ BUG!

if __name__ == "__main__":
    print("Input:", test_input)
    print("Generated result:", result)
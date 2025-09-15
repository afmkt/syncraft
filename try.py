from dataclasses import dataclass
from typing import Any, Dict, Tuple, List

@dataclass
class Result:
    node: Any
    pos: int
    success: bool

    def __repr__(self):
        if not self.success:
            return "Fail"
        return f"({self.node}, pos={self.pos})"

@dataclass
class LeftRecEntry:
    in_progress: bool
    result: Result

class Parser:
    def __init__(self, tokens: List[str]):
        self.tokens = tokens
        self.cache: Dict[Tuple[str, int], LeftRecEntry] = {}

    def parse(self, rule: str, pos: int) -> Result:
        key = (rule, pos)

        # already cached?
        if key in self.cache:
            entry = self.cache[key]
            if entry.in_progress:
                # recursion without progress: return current seed
                return entry.result
            else:
                return entry.result

        # initialize with seed + in-progress flag
        seed = Result(node=None, pos=pos, success=False)
        self.cache[key] = LeftRecEntry(in_progress=True, result=seed)

        # first attempt
        result = self.run_rule(rule, pos)
        if result.success:
            self.cache[key].result = result

            # growth loop: keep improving while progress
            while True:
                new_result = self.run_rule(rule, pos)
                if new_result.success and new_result.pos > self.cache[key].result.pos:
                    self.cache[key].result = new_result
                else:
                    break

        # mark as finished
        self.cache[key].in_progress = False
        return self.cache[key].result

    def run_rule(self, rule: str, pos: int) -> Result:
        if rule == "Expr":
            # Expr -> Expr "+" Term | Term
            # Try left recursion first
            left = self.parse("Expr", pos)
            if left.success and left.pos < len(self.tokens) and self.tokens[left.pos] == "+":
                right = self.parse("Term", left.pos + 1)
                if right.success:
                    return Result(
                        node=("Add", left.node, right.node),
                        pos=right.pos,
                        success=True
                    )
            # Fallback: Term
            return self.parse("Term", pos)

        elif rule == "Term":
            # Term -> number
            if pos < len(self.tokens) and self.tokens[pos].isdigit():
                return Result(node=int(self.tokens[pos]), pos=pos + 1, success=True)
            return Result(node=None, pos=pos, success=False)

        raise ValueError(f"Unknown rule {rule}")

# ------------------------------
# Demo
# ------------------------------
def test(expr: str):
    tokens = expr.split()
    parser = Parser(tokens)
    result = parser.parse("Expr", 0)
    print(expr, "=>", result)

if __name__ == "__main__":
    test("42")
    test("42 + 7")
    test("42 + 7 + 3")
    test("1 + 2 + 3 + 4")

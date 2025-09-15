from __future__ import annotations
from syncraft.parser import parse_word
from syncraft.generator import generate_with
from syncraft.syntax import Syntax
import pytest
from syncraft.cache import LeftRecursionError
import re
from syncraft.ast import TokenClass
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
from rich import print
from syncraft.algebra import Error



literal = Syntax.config(token_class = TokenClass.simple()).literal
token = Syntax.config(token_class = TokenClass.simple()).token

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

        if key in self.cache:
            entry = self.cache[key]
            if entry.in_progress:
                return entry.result
            return entry.result

        seed = Result(node=None, pos=pos, success=False)
        self.cache[key] = LeftRecEntry(in_progress=True, result=seed)

        result = self.run_rule(rule, pos)
        if result.success:
            self.cache[key].result = result
            while True:
                new_result = self.run_rule(rule, pos)
                if new_result.success and new_result.pos > self.cache[key].result.pos:
                    self.cache[key].result = new_result
                else:
                    break

        self.cache[key].in_progress = False
        return self.cache[key].result

    def run_rule(self, rule: str, pos: int) -> Result:
        if rule == "Expr":
            # Expr -> Expr '+' Term
            left = self.parse("Expr", pos)
            if left.success and left.pos < len(self.tokens) and self.tokens[left.pos] == "+":
                right = self.parse("Term", left.pos + 1)
                if right.success:
                    return Result(("Add", left.node, right.node), right.pos, True)
            return Result(None, pos, False)

        elif rule == "Term":
            if pos < len(self.tokens) and self.tokens[pos].isdigit():
                return Result(int(self.tokens[pos]), pos + 1, True)
            return Result(None, pos, False)

        raise ValueError(f"Unknown rule {rule}")

# ------------------------------
# Demo
# ------------------------------
def test(expr: str):
    tokens = expr.split()
    parser = Parser(tokens)
    result = parser.parse("Expr", 0)
    print(expr, "=>", result)




def test_direct_left_recursion()->None:
    Term = literal('n').named("Term")
    Expr = Syntax.lazy(lambda: Expr + literal('+') + Term).named("Expr")
    
    v, s = parse_word(Expr, 'n + n + n')
    match v:
        case Error(error=LeftRecursionError() as lftr):
            print("Left recursion detected:", lftr)
        case _:
            print(v, s)
            assert False, "Should have detected left recursion"



def test_indirect_left_recursion()->None:
    NUMBER = literal(re.compile(r'\d+')).map(lambda x: int(x.text))
    PLUS = token(text='+')
    STAR = token(text='*')
    A = Syntax.lazy(lambda: (B >> PLUS >> A) | B).named("A")
    B = Syntax.lazy(lambda: (A >> STAR >> NUMBER) | NUMBER).named("B")
    v, s = parse_word(A, '1 + 2 * 3')
    print(v, s)

if __name__ == "__main__":
    test_direct_left_recursion()

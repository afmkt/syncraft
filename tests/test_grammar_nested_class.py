from __future__ import annotations

from syncraft.grammar import Grammar, grammar, rule
from syncraft.syntax import Syntax

S = Syntax


def test_grammar_decorator_works_for_function_scoped_class() -> None:
    def build_grammar() -> type[Grammar]:
        @grammar
        class LocalGrammar(Grammar):
            a = S.tok("a")
            root = rule(a, is_root=True)

        return LocalGrammar

    local_grammar = build_grammar()
    result = local_grammar.parse("a")

    assert result == "a"
    assert local_grammar._root_rule is not None
    assert local_grammar._rules["a"].location is not None

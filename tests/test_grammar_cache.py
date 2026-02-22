from __future__ import annotations

from syncraft.ast import Token
from syncraft.grammar import Grammar, grammar, rule
from syncraft.syntax import Syntax

S = Syntax.set(terminal_cls=Token)


@grammar
class GrammarA(Grammar):
    a = S.tok("a")
    root = rule(a, is_root=True)


@grammar
class GrammarB(Grammar):
    b = S.tok("b")
    root = rule(b, is_root=True)


def test_grammar_subclass_state_isolated() -> None:
    assert GrammarA._rules is not GrammarB._rules
    assert GrammarA._parser is not GrammarB._parser
    assert GrammarA._generator is not GrammarB._generator
    assert GrammarA._root_rule is not GrammarB._root_rule

    GrammarA.parser()
    GrammarB.parser()

    assert set(GrammarA._parser.keys()) == {GrammarA._root_rule}
    assert set(GrammarB._parser.keys()) == {GrammarB._root_rule}

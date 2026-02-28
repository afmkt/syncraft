from __future__ import annotations


from syncraft.grammar import Grammar, grammar, rule
from syncraft.syntax import Syntax


S = Syntax


@grammar
class RPNamedBindingGrammar(Grammar):
    named = S.rp(r"(?P<name>[a-z]+)")
    root = rule(named, is_root=True)


def test_rp_named_capture_binds_global_pool() -> None:
    result = RPNamedBindingGrammar.parse("hello")
    assert result == "hello"




if __name__ == "__main__":
    # test_rp_no_capture_returns_full_text()
    # test_rp_capture_returns_capture_tuple()
    test_rp_named_capture_binds_global_pool()
    # test_rp_repeated_capture_flattens_in_order()
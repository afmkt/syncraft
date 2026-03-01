from __future__ import annotations

import pytest


from syncraft.algebra import Error
from syncraft.grammar import Grammar, grammar, rule
from syncraft.regex import RegexError
from syncraft.syntax import Syntax


S = Syntax


@grammar
class RPNoCaptureGrammar(Grammar):
    word = S.rp(r"[a-z]+")
    root = rule(word, is_root=True)


@grammar
class RPCaptureGrammar(Grammar):
    pair = S.rp(r"(ab)(?P<tail>cd)")
    root = rule(pair, is_root=True)


@grammar
class RPNamedBindingGrammar(Grammar):
    named = S.rp(r"(?P<name>[a-z]+)")
    root = rule(named, is_root=True)


@grammar
class RPRepeatedCaptureGrammar(Grammar):
    repeated = S.rp(r"(a|bc)+")
    root = rule(repeated, is_root=True)


@grammar
class RPTrailingEmptyAltGrammar(Grammar):
    value = S.rp(r"a|")
    root = rule(value, is_root=True)


@grammar
class RPLeadingEmptyAltGrammar(Grammar):
    value = S.rp(r"|a")
    root = rule(value, is_root=True)


@grammar
class RPMixedGroupEmptyAltGrammar(Grammar):
    value = S.rp(r"(ab)|")
    root = rule(value, is_root=True)


@grammar
class RPExternalSyntaxRefGrammar(Grammar):
    num = S.rp(r"[0-9]+")
    pair = S.rp(r"(?&num)-(?&num)", num=num)
    root = rule(pair, is_root=True)


def test_rp_no_capture_returns_full_text() -> None:
    result = RPNoCaptureGrammar.parse("abc")
    assert result == "abc"


def test_rp_capture_returns_capture_tuple() -> None:
    result = RPCaptureGrammar.parse("abcd")
    assert result == ("ab", "cd")


def test_rp_named_capture_binds_global_pool() -> None:
    result = RPNamedBindingGrammar.parse("hello")
    assert result == "hello"


def test_rp_repeated_capture_flattens_in_order() -> None:
    result = RPRepeatedCaptureGrammar.parse("abcabca")
    assert result == ("a", "bc", "a", "bc", "a")


def test_rp_trailing_empty_alternative_supports_empty_input() -> None:
    assert RPTrailingEmptyAltGrammar.parse("a") == "a"
    assert isinstance(RPTrailingEmptyAltGrammar.parse(""), Error)


def test_rp_leading_empty_alternative_supports_empty_input() -> None:
    assert RPLeadingEmptyAltGrammar.parse("a") == "a"
    assert isinstance(RPLeadingEmptyAltGrammar.parse(""), Error)


def test_rp_mixed_group_and_empty_alternative() -> None:
    assert RPMixedGroupEmptyAltGrammar.parse("ab") == "ab"
    assert RPMixedGroupEmptyAltGrammar.parse("") == ""


def test_rp_external_syntax_reference() -> None:
    assert RPExternalSyntaxRefGrammar.parse("12-34") == ("12", "34")


def test_rp_external_syntax_reference_missing_name() -> None:
    with pytest.raises(RegexError):
        S.rp(r"(?&missing)")

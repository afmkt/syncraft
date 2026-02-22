from __future__ import annotations

from syncraft.ast import Token
from syncraft.grammar import Grammar, grammar, rule
from syncraft.syntax import Syntax


S = Syntax.set(terminal_cls=Token)


@grammar
class SimpleTokenGrammar(Grammar):
    word = S.re(r"[a-z]+")
    root = rule(word, is_root=True)


@grammar
class WordNumberGrammar(Grammar):
    word = S.re(r"[a-z]+")
    number = S.re(r"\d+")
    root = rule(word + number, is_root=True)


@grammar
class CaseInsensitiveKeywordGrammar(Grammar):
    keyword = S.re(r"(?i:if)")
    root = rule(keyword, is_root=True)


def test_regex_lexer_single_token() -> None:
    result = SimpleTokenGrammar.parse("abc")
    assert result == Token(text="abc")


def test_regex_lexer_sequence() -> None:
    result = WordNumberGrammar.parse("abc123")
    assert result == (Token(text="abc"), Token(text="123"))


def test_regex_lexer_case_insensitive_scoped() -> None:
    result = CaseInsensitiveKeywordGrammar.parse("IF")
    assert result == Token(text="IF")

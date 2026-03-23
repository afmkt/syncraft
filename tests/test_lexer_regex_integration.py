from __future__ import annotations


from syncraft.grammar import Grammar, grammar, rule
from syncraft.syntax import Syntax


S = Syntax


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
    assert result == "abc"


def test_regex_lexer_sequence() -> None:
    result = WordNumberGrammar.parse("abc123")
    assert result == ("abc", "123")


def test_regex_lexer_case_insensitive_scoped() -> None:
    result = CaseInsensitiveKeywordGrammar.parse("IF")
    assert result == "IF"

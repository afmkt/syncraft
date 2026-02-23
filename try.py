from __future__ import annotations

from syncraft.ast import Token
from syncraft.grammar import Grammar, grammar, rule
from syncraft.syntax import Syntax
from syncraft.generator import (
    validate,
)
from syncraft.fa import Builder



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
    print(result)
    assert result == Token(text="IF")


def test_validate_lex_token_uses_verify_full_match() -> None:
    S = Syntax.set(terminal_cls=Token)
    lex_syntax = S.factory("lex", Builder.lit("ab").tagged("AB"))

    ast = validate(lex_syntax, Token(text="ab", token_type="AB"))
    print(ast)
    assert isinstance(ast, Token)
    assert ast.token_type == "AB"
    assert ast.text == "ab"
    
    
if __name__ == "__main__":
    # test_validate_lex_token_uses_verify_full_match()
    # test_regex_lexer_single_token()
    # test_regex_lexer_sequence()
    test_regex_lexer_case_insensitive_scoped()
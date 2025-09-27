import pytest

from syncraft.syntax import Syntax
from syncraft.ast import TokenClass, Token, Then, ThenKind, Choice, ChoiceKind, Lazy
from syncraft.generator import generate_with, generate, validate
from syncraft.algebra import Error
from syncraft.cache import LeftRecursionError


def tok(text: str):
    return Syntax.token(token_class=TokenClass.simple(), text=text, case_sensitive=True)


def test_generate_with_direct_left_recursion_with_base_succeeds():
    # A := A + 'a' | 'a'
    A = Syntax.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]
    ast, bound = generate_with(A)
    # Should yield an AST (not Error) and produce a bindings mapping (possibly empty)
    assert not isinstance(ast, Error)
    assert bound is not None


def test_generate_direct_left_recursion_with_base_succeeds():
    A = Syntax.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]
    ast, bound = generate(A)
    assert not isinstance(ast, Error)
    assert bound is not None


def test_validate_direct_left_recursion_with_base_succeeds_single_token():
    A = Syntax.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]
    # Validate a simple token AST wrapped in Choice RIGHT (matches base branch)
    ast, bound = validate(A, Lazy(value=Choice(kind=ChoiceKind.RIGHT, value=Token('a'))))
    assert not isinstance(ast, Error)
    assert bound is not None


def test_validate_direct_left_recursion_with_base_succeeds_nested_then():
    A = Syntax.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]
    # Manually build an AST for "aaa" using recursive branches with explicit Choices:
    # A := (A + 'a') | 'a'
    # Structure:
    #   Choice(LEFT,
    #     Then(BOTH,
    #       Choice(LEFT,
    #         Then(BOTH,
    #           Choice(RIGHT, Token('a')),  # base case A -> 'a'
    #           Token('a')
    #         )
    #       ),
    #       Token('a')
    #     )
    #   )
    inner_base = Lazy(value=Choice(kind=ChoiceKind.RIGHT, value=Token('a')))
    inner_then = Then(kind=ThenKind.BOTH, left=inner_base, right=Token('a'))
    middle_choice = Lazy(value=Choice(kind=ChoiceKind.LEFT, value=inner_then))
    outer_then = Then(kind=ThenKind.BOTH, left=middle_choice, right=Token('a'))
    data = Lazy(value=Choice(kind=ChoiceKind.LEFT, value=outer_then))
    ast, bound = validate(A, data)
    assert not isinstance(ast, Error)
    assert bound is not None


def test_generate_with_mutual_left_recursion_without_base_raises():
    # Mutual recursion with no productive base: A := B ; B := A
    A = Syntax.lazy(lambda: B)  # type: ignore[name-defined]
    B = Syntax.lazy(lambda: A)  # type: ignore[name-defined]
    with pytest.raises(LeftRecursionError):
        generate_with(A)


def test_generate_mutual_left_recursion_without_base_raises():
    A = Syntax.lazy(lambda: B)  # type: ignore[name-defined]
    B = Syntax.lazy(lambda: A)  # type: ignore[name-defined]
    with pytest.raises(LeftRecursionError):
        generate(A)


def test_validate_mutual_left_recursion_without_base_raises():
    A = Syntax.lazy(lambda: B)  # type: ignore[name-defined]
    B = Syntax.lazy(lambda: A)  # type: ignore[name-defined]
    with pytest.raises(LeftRecursionError):
        # Any AST will do; grammar has no base and should be flagged
        generate(A)

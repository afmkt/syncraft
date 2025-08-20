from typing import Any
from syncraft.parser import parse, until, literal, Parser
from syncraft.ast import AST

# Define common pair DSLs
LP, RP = literal("("), literal(")")
LB, RB = literal("["), literal("]")


def test_until_accepts_proper_nesting() -> None:
    sql = "([])"
    syntax = until((LP, RP), (LB, RB))
    ast: AST[Any] | Any = parse(syntax, sql, dialect="sqlite")
    assert isinstance(ast, AST), f"Expected AST for proper nesting, got {ast}"


def test_until_rejects_mismatched_pairs() -> None:
    # Mismatched: ( ] should fail immediately
    sql = "(]"
    syntax = until((LP, RP), (LB, RB))
    res = parse(syntax, sql, dialect="sqlite")
    from syncraft.algebra import Error
    assert isinstance(res, Error), "Mismatched pairs should be rejected with an Error"

def test_until_rejects_unterminated_group() -> None:
    # Unterminated: ( ... EOF
    sql = "("
    syntax = until((LP, RP))
    res = parse(syntax, sql, dialect="sqlite")
    from syncraft.algebra import Error
    assert isinstance(res, Error), "Unterminated group should be rejected with an Error"

def test_until_rejects_crossing_pairs() -> None:
    # Crossing/interleaved: ([)] should be rejected
    sql = "([)]"
    syntax = until((LP, RP), (LB, RB))
    # Use postgres dialect so [ and ] are tokenized distinctly (not as bracketed identifier)
    res = parse(syntax, sql, dialect="postgres")
    from syncraft.algebra import Error
    assert isinstance(res, Error), "Crossing pairs should be rejected with an Error"

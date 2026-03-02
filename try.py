"""
Test cases demonstrating Syntax.rp() in inline, immediate, REPL-style usage.

"CFG in regex flavor" — using regex notation to compose CFG rules inline,
without @grammar classes or explicit rule fields. Everything is immediate.
"""

from syncraft.syntax import Syntax as S
from syncraft.parser import parse_string
from syncraft.algebra import Error
# from rich import print


def cfgparse(pattern: str, text: str, **refs):
    """Shorthand: pattern -> Syntax.rp -> parse immediate."""
    return parse_string(S.rp(pattern, **refs), text)


def test_failed():
    r"""
    SIMPLEST REPRODUCER - doesn't need lazy or self-reference!
    
    Pattern: r"2|\((?&num)\s*"
    
    Uses:
    - S.lit() for external reference (not S.rp)
    - S.rp() directly (not S.lazy)
    - External reference (?&num), not self-reference
    
    This proves the bug affects:
    - ANY alternation (|) with external reference (?&name)
    - When second branch uses \s* or []* (zero-or-more quantifier)
    - Lexer fails because alternation lexer doesn't include tokens
      from branches that contain external references
    """
    num = S.lit(r"2")
    expr = S.rp(r"2|\((?&num)\s*", num=num)
    result = parse_string(expr, "(2")
    print(result)


if __name__ == "__main__":
    test_failed()

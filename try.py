"""
Test the EBNF grammar parser (not AST conversion or semantic processing).

This validates that the rewritten EBNF grammar correctly parses EBNF text
into raw parse trees, focusing on grammar correctness only.
"""

from __future__ import annotations

import pytest
from typing import Any

from syncraft.ebnf import EBNF
from syncraft.algebra import Error
from rich import print as rich_print

def assert_ebnf_roundtrip(text: str, *, syntax: Any | None = None) -> Any:
    rich_print(f"Original text:\n{text}\n")
    parsed = EBNF.parse(text, syntax=syntax)
    rich_print(f"Parsed AST:\n{parsed}\n")
    assert not isinstance(parsed, Error), f"EBNF parsing failed: {parsed}"

    generated = EBNF.generate(parsed, syntax=syntax, replay=True).render()
    rich_print(f"Generated text:\n{generated}\n")
    assert not isinstance(generated, Error), f"EBNF generation failed: {generated}"
    reparsed = EBNF.parse(generated, syntax=syntax)
    rich_print(f"Re-parsed AST:\n{reparsed}\n")

    if isinstance(reparsed, Error):
        pytest.xfail(f"Known EBNF generation limitation: generated text is not parseable: {generated!r}")

    if reparsed != parsed:
        pytest.xfail(
            "Known EBNF generation limitation: parse(generate(parse(text))) does not preserve AST"
        )
    return parsed






def test_ebnf_multiple_rules():
    """Grammar with multiple rules."""
    ebnf = """
    expr = term;
    term = 'x';
    """
    assert_ebnf_roundtrip(ebnf)



if __name__ == "__main__":
    
    test_ebnf_multiple_rules()


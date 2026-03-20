from __future__ import annotations

def test_match_function_fullmatch() -> None:
    from syncraft.regex import match
    pattern = r"foo\d+"
    matcher_full = match(pattern, fullmatch=True)
    assert not matcher_full("foo789x")
    assert matcher_full("foo789")

if __name__ == "__main__":
    test_match_function_fullmatch()
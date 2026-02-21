from __future__ import annotations

import pytest

from syncraft.ast import SyncraftError
from syncraft.regex import Regex, parse


def _parse(pattern: str) -> Regex:
    parsed = parse(pattern)
    assert isinstance(parsed, Regex), f"Parse failed for {pattern!r}: {parsed!r}"
    return parsed


def test_validate_accepts_basic_subset() -> None:
    _parse(r"ab|c\d+").validate()


def test_validate_rejects_anchor() -> None:
    regex = _parse(r"^abc")
    with pytest.raises(SyncraftError):
        regex.validate()


def test_validate_rejects_lookahead() -> None:
    regex = _parse(r"(?=a)b")
    with pytest.raises(SyncraftError):
        regex.validate()


def test_validate_rejects_capturing_group() -> None:
    regex = _parse(r"(ab)+")
    with pytest.raises(SyncraftError):
        regex.validate()


def test_validate_allows_capturing_group_with_flag() -> None:
    regex = _parse(r"(ab)+")
    regex.validate(allow_captures=True)


def test_validate_rejects_inline_flags() -> None:
    regex = _parse(r"(?i:ab)")
    with pytest.raises(SyncraftError):
        regex.validate()


def test_validate_allows_inline_flags_with_flag() -> None:
    regex = _parse(r"(?i:ab)")
    regex.validate(allow_inline_flags=True)


def test_validate_rejects_reversed_range() -> None:
    regex = _parse(r"[z-a]")
    with pytest.raises(SyncraftError):
        regex.validate()

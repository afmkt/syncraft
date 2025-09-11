from __future__ import annotations

import pytest

from syncraft.charset import (
    CharClass,
    CodeUniverse,
    MixedUniverseError,
    CodepointError,
)


def test_charset_basic_matches() -> None:
    cc: CharClass[str] = CharClass.create("abc", universe=CodeUniverse.ASCII)
    assert cc("a")
    assert cc("b")
    assert cc("c")
    assert not cc("d")
    # interval should have one entry per distinct char, sorted
    assert cc.interval == tuple((ord(c), ord(c)) for c in "abc")


def test_charset_union_and_interval_merge() -> None:
    a: CharClass[str] = CharClass.create("A", universe=CodeUniverse.ASCII)
    b: CharClass[str] = CharClass.create("B", universe=CodeUniverse.ASCII)
    c: CharClass[str] = CharClass.create("C", universe=CodeUniverse.ASCII)
    merged = a | b | c  # contiguous -> single merged interval
    assert merged("A") and merged("B") and merged("C")
    assert merged.interval == ((ord("A"), ord("C")),)

    d: CharClass[str] = CharClass.create("D", universe=CodeUniverse.ASCII)
    # gap between C and D? they are contiguous (C=67, D=68) so still merge
    merged2 = merged | d
    assert merged2.interval == ((ord("A"), ord("D")),)

    # Non-contiguous example to ensure separation: 'A' and 'F'
    f: CharClass[str] = CharClass.create("F", universe=CodeUniverse.ASCII)
    separate = a | f
    assert separate.interval == ((ord("A"), ord("A")), (ord("F"), ord("F")))


def test_charset_intersection_difference() -> None:
    letters: CharClass[str] = CharClass.create("ABCD", universe=CodeUniverse.ASCII)
    mid: CharClass[str] = CharClass.create("BC", universe=CodeUniverse.ASCII)
    left = letters - mid
    assert left.interval == (
        (ord("A"), ord("A")),
        (ord("D"), ord("D")),
    )
    inter = letters & mid
    assert inter.interval == (
        (ord("B"), ord("B")),
        (ord("C"), ord("C")),
    )
    empty = mid & CharClass.create("Z", universe=CodeUniverse.ASCII)
    assert empty.interval == tuple()
    assert not empty("B")


def test_charset_complement() -> None:
    a: CharClass[str] = CharClass.create("A", universe=CodeUniverse.ASCII)
    comp = ~a
    assert not comp("A")
    assert comp("B")
    # Expect two intervals excluding 'A'
    assert comp.interval == ((0, ord("A") - 1), (ord("A") + 1, 0x7F))


def test_charset_universe_mismatch() -> None:
    ascii_a: CharClass[str] = CharClass.create("A", universe=CodeUniverse.ASCII)
    uni_a: CharClass[str] = CharClass.create("A", universe=CodeUniverse.UNICODE)
    with pytest.raises(MixedUniverseError):
        _ = ascii_a | uni_a
    with pytest.raises(MixedUniverseError):
        _ = ascii_a & uni_a
    with pytest.raises(MixedUniverseError):
        _ = ascii_a - uni_a


def test_charset_bytes_mode() -> None:
    b1: CharClass[bytes] = CharClass.create(b"\x00\x10\x20", universe=CodeUniverse.BYTE)
    assert b1(b"\x00")
    assert not b1(b"\x01")
    assert b1.interval == ((0x00, 0x00), (0x10, 0x10), (0x20, 0x20))
    comp = ~b1
    assert comp(b"\x01")
    assert not comp(b"\x10")


def test_charset_invalid_length_error() -> None:
    cc: CharClass[str] = CharClass.create("A", universe=CodeUniverse.ASCII)
    with pytest.raises(CodepointError):
        cc("AB")  # multi-character should raise
    cc_bytes: CharClass[bytes] = CharClass.create(b"A", universe=CodeUniverse.BYTE)
    with pytest.raises(CodepointError):
        cc_bytes(b"AB")


def test_charset_any() -> None:
    any_uni: CharClass[str] = CharClass.any(CodeUniverse.UNICODE)
    # spot check a few codepoints
    assert any_uni("A")
    assert any_uni("\u2603")  # snowman
    assert any_uni.interval == CodeUniverse.UNICODE.interval

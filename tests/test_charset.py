from __future__ import annotations

import pytest

from syncraft.charset import (
    CharSet,
    CodeUniverse,
    MixedUniverseError,
    CodepointError,
)


def test_charset_basic_matches() -> None:
    cc: CharSet[str] = CharSet.create("abc", universe=CodeUniverse.ascii())
    assert cc("a")
    assert cc("b")
    assert cc("c")
    assert not cc("d")
    # interval should have one entry per distinct char, sorted
    assert cc.interval == tuple((ord(c), ord(c)) for c in "abc")


def test_charset_union_and_interval_merge() -> None:
    a: CharSet[str] = CharSet.create("A", universe=CodeUniverse.ascii())
    b: CharSet[str] = CharSet.create("B", universe=CodeUniverse.ascii())
    c: CharSet[str] = CharSet.create("C", universe=CodeUniverse.ascii())
    merged = a | b | c  # contiguous -> single merged interval
    assert merged("A") and merged("B") and merged("C")
    assert merged.interval == ((ord("A"), ord("C")),)

    d: CharSet[str] = CharSet.create("D", universe=CodeUniverse.ascii())
    # gap between C and D? they are contiguous (C=67, D=68) so still merge
    merged2 = merged | d
    assert merged2.interval == ((ord("A"), ord("D")),)

    # Non-contiguous example to ensure separation: 'A' and 'F'
    f: CharSet[str] = CharSet.create("F", universe=CodeUniverse.ascii())
    separate = a | f
    assert separate.interval == ((ord("A"), ord("A")), (ord("F"), ord("F")))


def test_charset_intersection_difference() -> None:
    letters: CharSet[str] = CharSet.create("ABCD", universe=CodeUniverse.ascii())
    mid: CharSet[str] = CharSet.create("BC", universe=CodeUniverse.ascii())
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
    empty = mid & CharSet.create("Z", universe=CodeUniverse.ascii())
    assert empty.interval == tuple()
    assert not empty("B")


def test_charset_complement() -> None:
    a: CharSet[str] = CharSet.create("A", universe=CodeUniverse.ascii())
    comp = ~a
    assert not comp("A")
    assert comp("B")
    # Expect two intervals excluding 'A'
    assert comp.interval == ((0, ord("A") - 1), (ord("A") + 1, 0x7F))


def test_charset_universe_mismatch() -> None:
    ascii_a: CharSet[str] = CharSet.create("A", universe=CodeUniverse.ascii())
    uni_a: CharSet[str] = CharSet.create("A", universe=CodeUniverse.unicode())
    with pytest.raises(MixedUniverseError):
        _ = ascii_a | uni_a
    with pytest.raises(MixedUniverseError):
        _ = ascii_a & uni_a
    with pytest.raises(MixedUniverseError):
        _ = ascii_a - uni_a


def test_charset_bytes_mode() -> None:
    b1: CharSet[bytes] = CharSet.create(b"\x00\x10\x20", universe=CodeUniverse.byte())
    assert b1(b"\x00")
    assert not b1(b"\x01")
    assert b1.interval == ((0x00, 0x00), (0x10, 0x10), (0x20, 0x20))
    comp = ~b1
    assert comp(b"\x01")
    assert not comp(b"\x10")


def test_charset_invalid_length_error() -> None:
    cc: CharSet[str] = CharSet.create("A", universe=CodeUniverse.ascii())
    with pytest.raises(CodepointError):
        cc("AB")  # multi-character should raise
    cc_bytes: CharSet[bytes] = CharSet.create(b"A", universe=CodeUniverse.byte())
    with pytest.raises(CodepointError):
        cc_bytes(b"AB")


def test_charset_any() -> None:
    any_uni: CharSet[str] = CharSet.any(CodeUniverse.unicode())
    # spot check a few codepoints
    assert any_uni("A")
    assert any_uni("\u2603")  # snowman
    assert any_uni.interval == CodeUniverse.unicode().interval

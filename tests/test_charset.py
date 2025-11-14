from __future__ import annotations

import pytest

from syncraft.charset import (
    CharSet,
    MixedUniverseError,
 
)
from syncraft.alphabet import Alphabet
from syncraft.alphabet import Symbol, CodepointError
from syncraft.algebra import SyncraftError
import enum


def test_charset_basic_matches() -> None:
    cc: CharSet[str] = CharSet.create("abc", alphabet=Alphabet.get(str))
    assert cc("a")
    assert cc("b")
    assert cc("c")
    assert not cc("d")
    # interval should have one entry per distinct char, sorted
    assert cc.interval == tuple((ord(c), ord(c)) for c in "abc")


def test_charset_union_and_interval_merge() -> None:
    a: CharSet[str] = CharSet.create("A", alphabet=Alphabet.get(str))
    b: CharSet[str] = CharSet.create("B", alphabet=Alphabet.get(str))
    c: CharSet[str] = CharSet.create("C", alphabet=Alphabet.get(str))
    merged = a | b | c  # contiguous -> single merged interval
    assert merged("A") and merged("B") and merged("C")
    assert merged.interval == ((ord("A"), ord("C")),)

    d: CharSet[str] = CharSet.create("D", alphabet=Alphabet.get(str))
    # gap between C and D? they are contiguous (C=67, D=68) so still merge
    merged2 = merged | d
    assert merged2.interval == ((ord("A"), ord("D")),)

    # Non-contiguous example to ensure separation: 'A' and 'F'
    f: CharSet[str] = CharSet.create("F", alphabet=Alphabet.get(str))
    separate = a | f
    assert separate.interval == ((ord("A"), ord("A")), (ord("F"), ord("F")))


def test_charset_intersection_difference() -> None:
    letters: CharSet[str] = CharSet.create("ABCD", alphabet=Alphabet.get(str))
    mid: CharSet[str] = CharSet.create("BC", alphabet=Alphabet.get(str))
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
    empty = mid & CharSet.create("Z", alphabet=Alphabet.get(str))
    assert empty.interval == tuple()
    assert not empty("B")


def test_charset_complement() -> None:
    a: CharSet[str] = CharSet.create("A", alphabet=Alphabet.get(str))
    comp = -a
    assert not comp("A")
    assert comp("B")
    # Expect two intervals excluding 'A'
    assert comp.interval == ((0, ord("A") - 1), (ord("A") + 1, 0x10FFFF))


def test_charset_universe_mismatch() -> None:
    ascii_a: CharSet[str] = CharSet.create(b"\x00", alphabet=Alphabet.get(bytes))
    uni_a: CharSet[str] = CharSet.create("A", alphabet=Alphabet.get(str))
    with pytest.raises(MixedUniverseError):
        _ = ascii_a | uni_a
    with pytest.raises(MixedUniverseError):
        _ = ascii_a & uni_a
    with pytest.raises(MixedUniverseError):
        _ = ascii_a - uni_a


def test_charset_bytes_mode() -> None:
    b1: CharSet[int] = CharSet.create(b"\x00\x10\x20", alphabet=Alphabet.get(bytes))
    assert b1(0x00)
    assert not b1(0x01)
    assert b1.interval == ((0x00, 0x00), (0x10, 0x10), (0x20, 0x20))
    comp = -b1
    assert comp(0x01)
    assert not comp(0x10)


def test_charset_invalid_length_error() -> None:
    cc_bytes: CharSet[int] = CharSet.create(b"A", alphabet=Alphabet.get(bytes))
    with pytest.raises(CodepointError):
        cc_bytes(b"AB")


def test_charset_any() -> None:
    any_uni: CharSet[str] = CharSet.any(Alphabet.get(str))
    # spot check a few codepoints
    assert any_uni("A")
    assert any_uni("\u2603")  # snowman
    assert any_uni.interval == Alphabet.get(str).codes



def test_codeuniverse_unicode():
    u = Alphabet.get(str)
    assert u.codes == ((0, 0x10FFFF),)
    assert u.space is str
    assert u.decode(0x2603) == '\u2603'
    assert u.encode('\u2603') == 0x2603
    assert u.codes == ((0, 0x10FFFF),)

def test_codeuniverse_byte():
    u = Alphabet.get(bytes)
    assert u.codes == ((0, 0xFF),)
    assert u.space is bytes
    assert u.decode(0x41) == b'A'
    assert u.encode(b'A') == 0x41
    assert u.codes == ((0, 0xFF),)
    with pytest.raises(CodepointError):
        u.encode(b'AB')
    with pytest.raises(ValueError):
        u.decode(0x100)





from __future__ import annotations

import pytest

from syncraft.charset import (
    CharSet,
    MixedUniverseError,
 
)
from syncraft.alphabet import Alphabet
from syncraft.alphabet import  CodepointError
from syncraft.algebra import SyncraftError
from syncraft.charset import CharSetFactory
import enum


def test_charset_basic_matches() -> None:
    cs_factory = CharSetFactory(alphabet=Alphabet(str))
    cc: CharSet = cs_factory.create("abc")
    assert cs_factory.matches(cc, "a")
    assert cs_factory.matches(cc, "b")
    assert cs_factory.matches(cc, "c")
    assert not cs_factory.matches(cc, "d")
    # interval should have one entry per distinct char, sorted
    assert cc == tuple((ord(c), ord(c)) for c in "abc")


def test_charset_union_and_interval_merge() -> None:
    cs_factory = CharSetFactory(alphabet=Alphabet(str))
    a: CharSet = cs_factory.create("A")
    b: CharSet = cs_factory.create("B")
    c: CharSet = cs_factory.create("C")
    merged = cs_factory.union_many(a, b, c)  # contiguous -> single merged interval
    assert cs_factory.matches(merged, "A") and cs_factory.matches(merged, "B") and cs_factory.matches(merged, "C")
    assert merged == ((ord("A"), ord("C")),)

    d: CharSet = cs_factory.create("D")
    # gap between C and D? they are contiguous (C=67, D=68) so still merge
    merged2 = cs_factory.union(merged, d)
    assert merged2 == ((ord("A"), ord("D")),)

    # Non-contiguous example to ensure separation: 'A' and 'F'
    f: CharSet = cs_factory.create("F")
    separate = cs_factory.union(a, f)
    assert separate == ((ord("A"), ord("A")), (ord("F"), ord("F")))


def test_charset_intersection_difference() -> None:
    cs_factory = CharSetFactory(alphabet=Alphabet(str))
    letters: CharSet = cs_factory.create("ABCD")
    mid: CharSet = cs_factory.create("BC")
    left = cs_factory.difference(letters, mid)
    assert left == (
        (ord("A"), ord("A")),
        (ord("D"), ord("D")),
    )
    inter = cs_factory.intersect(letters, mid)
    assert inter == (
        (ord("B"), ord("B")),
        (ord("C"), ord("C")),
    )
    empty = cs_factory.intersect(mid, cs_factory.create("Z"))
    assert empty == tuple()
    assert not cs_factory.matches(empty, "B")


def test_charset_complement() -> None:
    cs_factory = CharSetFactory(alphabet=Alphabet(str))
    a: CharSet = cs_factory.create("A")
    comp = cs_factory.complement(a)
    assert not cs_factory.matches(comp, "A")
    assert cs_factory.matches(comp, "B")
    # Expect two intervals excluding 'A'
    assert comp == ((0, ord("A") - 1), (ord("A") + 1, 0x10FFFF))



def test_charset_bytes_mode() -> None:
    cs_factory = CharSetFactory(alphabet=Alphabet(bytes))
    b1: CharSet = cs_factory.create(b"\x00\x10\x20")
    assert cs_factory.matches(b1, b'\x00')
    assert not cs_factory.matches(b1, b'\x01')
    comp = cs_factory.complement(b1)
    assert cs_factory.matches(comp, b'\x01')
    assert not cs_factory.matches(comp, b'\x10')


def test_charset_invalid_length_error() -> None:
    cs_factory = CharSetFactory(alphabet=Alphabet(bytes))
    cc_bytes: CharSet = cs_factory.create(b"A")
    with pytest.raises(CodepointError):
        cs_factory(cc_bytes, b"AB")

def test_charset_any() -> None:
    cs_factory = CharSetFactory(alphabet=Alphabet(str))
    any_uni: CharSet = cs_factory.any()
    # spot check a few codepoints
    assert cs_factory.matches(any_uni, "A")
    assert cs_factory.matches(any_uni, "\u2603")  # snowman
    assert any_uni == cs_factory.any()



def test_codeuniverse_unicode():
    u = Alphabet(str)
    assert u.codes == ((0, 0x10FFFF),)
    assert u.space is str
    assert u.decode(0x2603) == '\u2603'
    assert u.encode('\u2603') == 0x2603
    assert u.codes == ((0, 0x10FFFF),)

def test_codeuniverse_byte():
    u = Alphabet(bytes)
    assert u.codes == ((0, 0xFF),)
    assert u.space is bytes
    assert u.decode(0x41) == b'A'
    assert u.encode(b'A') == 0x41
    assert u.codes == ((0, 0xFF),)
    with pytest.raises(CodepointError):
        u.encode(b'AB')





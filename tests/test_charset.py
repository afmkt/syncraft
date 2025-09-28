from __future__ import annotations

import pytest

from syncraft.charset import (
    CharSet,
    CodeUniverse,
    MixedUniverseError,
    CodepointError,
)
from syncraft.algebra import SyncraftError
import enum


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
    comp = -a
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
    b1: CharSet[int] = CharSet.create(b"\x00\x10\x20", universe=CodeUniverse.byte())
    assert b1(0x00)
    assert not b1(0x01)
    assert b1.interval == ((0x00, 0x00), (0x10, 0x10), (0x20, 0x20))
    comp = -b1
    assert comp(0x01)
    assert not comp(0x10)


def test_charset_invalid_length_error() -> None:
    cc: CharSet[str] = CharSet.create("A", universe=CodeUniverse.ascii())
    with pytest.raises(CodepointError):
        cc("AB")  # multi-character should raise
    cc_bytes: CharSet[int] = CharSet.create(b"A", universe=CodeUniverse.byte())
    with pytest.raises(CodepointError):
        cc_bytes(b"AB")


def test_charset_any() -> None:
    any_uni: CharSet[str] = CharSet.any(CodeUniverse.unicode())
    # spot check a few codepoints
    assert any_uni("A")
    assert any_uni("\u2603")  # snowman
    assert any_uni.interval == CodeUniverse.unicode().interval


# --- Enum support tests ---
 

class Color(enum.Enum):
    RED = 1
    GREEN = 2
    BLUE = 3

def test_charset_enum_basic():
    universe = CodeUniverse.enum(Color)
    cs = CharSet.create([Color.RED, Color.BLUE], universe=universe)
    assert cs(Color.RED)
    assert cs(Color.BLUE)
    assert not cs(Color.GREEN)
    # Interval should match Enum indices
    assert cs.interval == ((0,0),(2,2))

def test_charset_enum_error():
    universe = CodeUniverse.enum(Color)
    cs = CharSet.create([Color.RED], universe=universe)
    class Fake(enum.Enum):
        FAKE = 99
    with pytest.raises(CodepointError):
        cs(Fake.FAKE)

def test_charset_enum_empty():
    class Empty(enum.Enum):
        pass
    with pytest.raises(SyncraftError):
        CodeUniverse.enum(Empty)


# --- CodeUniverse tests ---
def test_codeuniverse_ascii():
    u = CodeUniverse.ascii()
    assert u.value == (0, 0x7F)
    assert u.space is str
    assert u.int2code(65) == 'A'
    assert u.code2int('A') == 65
    assert u.interval == ((0, 0x7F),)
    with pytest.raises(CodepointError):
        u.code2int('AB')
    with pytest.raises(CodepointError):
        u.int2code(0x80)

def test_codeuniverse_unicode():
    u = CodeUniverse.unicode()
    assert u.value == (0, 0x10FFFF)
    assert u.space is str
    assert u.int2code(0x2603) == '\u2603'
    assert u.code2int('\u2603') == 0x2603
    assert u.interval == ((0, 0x10FFFF),)

def test_codeuniverse_byte():
    u = CodeUniverse.byte()
    assert u.value == (0, 0xFF)
    assert u.space is bytes
    assert u.int2code(0x41) == b'A'
    assert u.code2int(b'A') == 0x41
    assert u.interval == ((0, 0xFF),)
    with pytest.raises(CodepointError):
        u.code2int(b'AB')
    with pytest.raises(CodepointError):
        u.int2code(0x100)

def test_codeuniverse_enum():
    class Fruit(enum.Enum):
        APPLE = 1
        BANANA = 2
    u = CodeUniverse.enum(Fruit)
    assert u.value == (0, 1)
    assert u.space is Fruit
    assert u.int2code(0) == Fruit.APPLE
    assert u.int2code(1) == Fruit.BANANA
    assert u.code2int(Fruit.APPLE) == 0
    assert u.code2int(Fruit.BANANA) == 1
    assert u.interval == ((0, 1),)
    with pytest.raises(CodepointError):
        u.int2code(2)
    class Other(enum.Enum):
        ORANGE = 3
    with pytest.raises(CodepointError):
        u.code2int(Other.ORANGE)


def test_codeuniverse_enum_nonint():
    class StrEnum(enum.Enum):
        ALPHA = 'a'
        BETA = 'b'
    u = CodeUniverse.enum(StrEnum)
    assert u.value == (0, 1)
    assert u.space is StrEnum
    assert u.int2code(0) == StrEnum.ALPHA
    assert u.int2code(1) == StrEnum.BETA
    assert u.code2int(StrEnum.ALPHA) == 0
    assert u.code2int(StrEnum.BETA) == 1
    assert u.interval == ((0, 1),)


def test_codeuniverse_to_dict_and_from_dict_ascii():
    u = CodeUniverse.ascii()
    d = u.to_dict()
    assert d == {'type': 'ASCII'}
    u2 = CodeUniverse.from_dict(d)
    assert u2.value == u.value and u2.space is str

def test_codeuniverse_to_dict_and_from_dict_unicode():
    u = CodeUniverse.unicode()
    d = u.to_dict()
    assert d == {'type': 'UNICODE'}
    u2 = CodeUniverse.from_dict(d)
    assert u2.value == u.value and u2.space is str

def test_codeuniverse_to_dict_and_from_dict_byte():
    u = CodeUniverse.byte()
    d = u.to_dict()
    assert d == {'type': 'BYTE'}
    u2 = CodeUniverse.from_dict(d)
    assert u2.value == u.value and u2.space is bytes

def test_codeuniverse_to_dict_and_from_dict_enum():
    class Fruit(enum.Enum):
        APPLE = 1
        BANANA = 2
    u = CodeUniverse.enum(Fruit)
    d = u.to_dict()
    assert d['type'] == 'ENUM'
    assert d['enum_class'] == 'Fruit'
    assert set(d['members']) == {'APPLE', 'BANANA'}
    u2 = CodeUniverse.from_dict(d, enum_classes={'Fruit': Fruit})
    assert u2.value == u.value and u2.space is Fruit

def test_codeuniverse_to_dict_and_from_dict_set():
    u = CodeUniverse.set(frozenset({'A', 'B', 'C'}))
    d = u.to_dict()
    assert d['type'] == 'SET'
    assert set(d['members']) == {'A', 'B', 'C'}
    u2 = CodeUniverse.from_dict(d)
    assert u2.value == (0, 2)
    assert u2.space == frozenset({'A', 'B', 'C'})

from __future__ import annotations

from typing import (
    TypeVar, Generic, Tuple, List, Callable, Type, ClassVar
)
from syncraft.constraint import FrozenDict
from dataclasses import dataclass, field
from syncraft.algebra import (
    SyncraftError
)
import random
from functools import cached_property
from enum import Enum


class MixedUniverseError(SyncraftError):
    pass

class CodepointError(SyncraftError):
    pass

C = TypeVar('C', bound=str | int | Enum)


@dataclass(frozen=True)
class CodeUniverse(Generic[C]):
    ASCII: ClassVar[Tuple[int, int]] = (0, 0x7F)
    UNICODE: ClassVar[Tuple[int, int]] = (0, 0x10FFFF)
    BYTE: ClassVar[Tuple[int, int]] = (0, 0xFF)
    value: Tuple[int, int]
    space: Type[C]
    int2c: FrozenDict[int, C] = field(default_factory=FrozenDict, repr=False)
    c2int: FrozenDict[C, int] = field(default_factory=FrozenDict, repr=False)
    @cached_property
    def interval(self) -> Tuple[Tuple[int, int],...]:
        return (self.value,)
    
    def __str__(self) -> str:
        if self.value == self.ASCII:
            return "ASCII"
        elif self.value == self.UNICODE:
            return "UNICODE"
        elif self.value == self.BYTE:
            return "BYTE"
        else:
            return f"{self.space.__name__}({self.value[0]}-{self.value[1]})"

    def __repr__(self) -> str:
        return self.__str__()
    
    def to_int(self, c: C) -> int:
        if isinstance(c, str):
            if len(c) != 1:
                raise CodepointError(f"Expected single character, got {c!r}", offender=c, expect="single character")
            cp = ord(c)
        elif isinstance(c, bytes):
            if len(c) != 1:
                raise CodepointError(f"Expected single byte, got {c!r}", offender=c, expect="single byte")
            cp = c[0]
        elif self.space is bytes and isinstance(c, int):
            cp = c
        elif isinstance(c, Enum):
            if c not in self.c2int:
                raise CodepointError(f"Enum value {c!r} not in universe {self}", offender=c, expect=f"Enum in {list(self.c2int.keys())}")
            cp = self.c2int[c]
        else:
            raise CodepointError(f"Expected str, bytes, or Enum, got {type(c)}", offender=c, expect="str, bytes, or Enum")
        if not (self.value[0] <= cp <= self.value[1]):
            raise CodepointError(f"Character {c!r} (codepoint {cp}) out of bounds for universe {self}", offender=c, expect=f"codepoint in range {self.value}")
        return cp
    
    def from_int(self, cp: int) -> C:
        if not (self.value[0] <= cp <= self.value[1]):
            raise CodepointError(f"Codepoint {cp} out of bounds for universe {self}", offender=cp, expect=f"codepoint in range {self.value}")
        if cp in self.int2c:
            return self.int2c[cp]
        if self.space is str:
            return chr(cp)  # type: ignore
        elif self.space is bytes:
            return bytes([cp])  # type: ignore
        else:
            raise CodepointError(f"Cannot convert codepoint {cp} to {self.space}", offender=cp, expect=self.space)

    @classmethod
    def ascii(cls) -> CodeUniverse[C]:
        return cls(value=cls.ASCII, space=str) # type: ignore
    
    @classmethod
    def unicode(cls) -> CodeUniverse[C]:
        return cls(value=cls.UNICODE, space=str) # type: ignore
    
    @classmethod
    def byte(cls) -> CodeUniverse[C]:
        return cls(value=cls.BYTE, space=bytes) # type: ignore
    
    @classmethod
    def enum(cls, enum_type: Type[Enum]) -> CodeUniverse[C]:
        members = list(enum_type)
        if not members:
            raise SyncraftError(f"Cannot create CodeUniverse from empty Enum {enum_type}", offender=enum_type, expect="non-empty Enum")
        int2c: FrozenDict[int, Enum] = FrozenDict({i: m for i, m in enumerate(members)})
        c2int: FrozenDict[Enum, int] = FrozenDict({m: i for i, m in enumerate(members)})
        return cls(value=(0, len(members)-1), space=enum_type, int2c=int2c, c2int=c2int) # type: ignore

@dataclass(frozen=True)
class CharSet(Generic[C]):
    predicate: Callable[[int], bool] = field(repr=False)      
    interval: Tuple[Tuple[int, int], ...] 
    universe: CodeUniverse


    @staticmethod
    def partition_charsets(intervals: list[Tuple[int, int]]) -> list[Tuple[int, int]]:
        """Given a list of intervals, return sorted list of disjoint intervals covering all points."""
        events = []
        for start, end in intervals:
            events.append((start, 1))      # interval starts
            events.append((end + 1, -1))   # interval ends (exclusive)
        
        events.sort()
        pieces = []
        active = 0
        piece_start = None
        
        for point, delta in events:
            prev_active = active
            active += delta
            if prev_active == 0 and active > 0:
                piece_start = point
            elif prev_active > 0 and active == 0:
                assert piece_start is not None
                pieces.append((piece_start, point - 1))
                piece_start = None
        return pieces    


    @staticmethod
    def difference_interval(a: List[Tuple[int, int]], b: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        result = []
        i = j = 0
        while i < len(a):
            a_start, a_end = a[i]
            current_start = a_start
            while j < len(b) and b[j][1] < current_start:
                j += 1
            while j < len(b) and b[j][0] <= a_end:
                b_start, b_end = b[j]
                if b_start > current_start:
                    result.append((current_start, b_start - 1))
                current_start = max(current_start, b_end + 1)
                if current_start > a_end:
                    break
                j += 1
            if current_start <= a_end:
                result.append((current_start, a_end))
            i += 1
        return result


    @staticmethod
    def intersect_interval(a: List[Tuple[int, int]], b: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        result = []
        i = j = 0
        while i < len(a) and j < len(b):
            a_start, a_end = a[i]
            b_start, b_end = b[j]
            # overlap?
            start = max(a_start, b_start)
            end = min(a_end, b_end)
            if start <= end:
                result.append((start, end))
            if a_end < b_end:
                i += 1
            else:
                j += 1
        return result
    
    @staticmethod
    def merge_intervals(intv: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        if not intv:
            return []
        intv = sorted(intv)
        merged = [intv[0]]
        for start, end in intv[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end + 1:
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))
        return merged

    @classmethod
    def create(cls, char: str | bytes | List[Enum], universe: CodeUniverse) -> CharSet[C]:
        cs: frozenset[int] = frozenset(universe.to_int(x) for x in char)
        intv = tuple((c, c) for c in sorted(cs))
        return cls(
            predicate=lambda c: c in cs, 
            interval=intv,
            universe=universe)
    
    @classmethod
    def from_interval(cls, intv: List[Tuple[int, int]], universe: CodeUniverse) -> CharSet[C]:
        merged = tuple(cls.merge_intervals(intv))
        return cls(
            predicate=lambda c: any(start <= c <= end for start, end in merged), 
            interval=merged,
            universe=universe)

    @classmethod
    def any(cls, universe: CodeUniverse) -> CharSet[C]:
        return cls(
            predicate=lambda c: True, 
            interval=universe.interval,
            universe=universe)
    
    @classmethod
    def none(cls, universe: CodeUniverse) -> CharSet[C]:
        return cls(
            predicate=lambda c: False, 
            interval=tuple(),
            universe=universe)

    def sample(self, rnd: random.Random) -> C:
        range = rnd.choice(self.interval)
        point = rnd.randint(range[0], range[1])
        return self.universe.from_int(point)

    def overlaps(self, intv: Tuple[int, int]) -> bool:
        for start, end in self.interval:
            if (end >= intv[0] and start <= intv[1]):
                return True
        return False

    def matches_interval(self, cc: C) -> bool:
        c = self.universe.to_int(cc)
        return any(start <= c <= end for start, end in self.interval)

    def matches(self, c: C) -> bool:
        return self.predicate(self.universe.to_int(c))
        
    def __call__(self, c: C) -> bool:
        assert self.matches(c) == self.matches_interval(c)
        return self.matches(c)

    def __contains__(self, c: C) -> bool:
        assert self.matches(c) == self.matches_interval(c)
        return self.matches_interval(c)
        
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CharSet):
            return NotImplemented
        return self.interval == other.interval and self.universe == other.universe

    def __hash__(self) -> int:
        return hash((self.interval, self.universe))


    def union(self, other: CharSet[C]) -> CharSet[C]:
        if self is other:
            return self
        if self.interval == ():
            return other
        if other.interval == ():
            return self
        if self.universe != other.universe:
            raise MixedUniverseError(f"Cannot union char classes with different universes: {self.universe} and {other.universe}", offender=other.universe, expect=self.universe)
        intv = tuple(self.merge_intervals(list(self.interval) + list(other.interval)))
        return CharSet(
            lambda c: self.predicate(c) or other.predicate(c), 
            intv,
            universe=self.universe)
    def __or__(self, other: CharSet[C]) -> CharSet[C]:
        return self.union(other)
    
    def intersect(self, other: CharSet[C]) -> CharSet[C]:
        if self is other:
            return self
        if self.interval == ():
            return self
        if other.interval == ():
            return other
        if self.universe != other.universe:
            raise MixedUniverseError(f"Cannot union char classes with different universes: {self.universe} and {other.universe}", offender=other.universe, expect=self.universe)
        intv = tuple(self.intersect_interval(list(self.interval), list(other.interval)))
        
        return CharSet(
            lambda c: self.predicate(c) and other.predicate(c), 
            intv,
            universe=self.universe)
    def __and__(self, other: CharSet[C]) -> CharSet[C]:
        return self.intersect(other)

    def difference(self, other: CharSet[C]) -> CharSet[C]:
        if self is other:
            return CharSet.none(universe=self.universe)
        if self.interval == ():
            return self
        if other.interval == ():
            return self
        if self.universe != other.universe:
            raise MixedUniverseError(f"Cannot union char classes with different universes: {self.universe} and {other.universe}", offender=other.universe, expect=self.universe)
        intv = tuple(self.difference_interval(list(self.interval), list(other.interval)))
        return CharSet(
            lambda c: self.predicate(c) and not other.predicate(c), 
            intv,
            universe=self.universe)
    def __sub__(self, other: CharSet[C]) -> CharSet[C]:
        return self.difference(other)
    
    @property
    def complement(self) -> CharSet[C]:
        if self.interval == ():
            return CharSet.any(universe=self.universe)
        intv = tuple(self.difference_interval(list(self.universe.interval), list(self.interval)))
        return CharSet(
            lambda c: not self.predicate(c), 
            intv,
            universe=self.universe)
    
    def __neg__(self) -> CharSet[C]:
        return self.complement

    def __bool__(self) -> bool:
        return self.interval != ()
    
    def __repr__(self) -> str:
        parts = []
        for start, end in self.interval:
            if start == end:
                parts.append(f"{self.universe.from_int(start)!r}")
            else:
                parts.append(f"{self.universe.from_int(start)!r}-{self.universe.from_int(end)!r}")
        return f"CharSet({', '.join(parts)}).{self.universe}"
    def __str__(self) -> str:
        return self.__repr__()
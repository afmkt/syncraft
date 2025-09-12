from __future__ import annotations

from typing import (
    TypeVar, Generic, Tuple, List, Callable
)
from dataclasses import dataclass
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

C = TypeVar('C', bound=str | bytes)


class CodeUniverse(Enum):
    ASCII = (0, 0x7F)
    UNICODE = (0, 0x10FFFF)
    BYTE = (0, 0xFF)    

    @cached_property
    def interval(self) -> Tuple[Tuple[int, int],...]:
        return (self.value,)

@dataclass(frozen=True)
class CharSet(Generic[C]):
    predicate: Callable[[int], bool]       
    interval: Tuple[Tuple[int, int], ...] 
    universe: CodeUniverse
    name: str

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
    def create(cls, char: str | bytes, universe: CodeUniverse = CodeUniverse.UNICODE) -> CharSet[C]:
        cs: frozenset[int] = frozenset(ord(x) if isinstance(x, str) else x for x in char)
        intv = tuple((c, c) for c in sorted(cs))
        return cls(
            predicate=lambda c: c in cs, 
            interval=intv,
            universe=universe,
            name=f"'{cs}'")
    
    @classmethod
    def from_interval(cls, intv: List[Tuple[int, int]], universe: CodeUniverse = CodeUniverse.UNICODE) -> CharSet[C]:
        merged = tuple(cls.merge_intervals(intv))
        return cls(
            predicate=lambda c: any(start <= c <= end for start, end in merged), 
            interval=merged,
            universe=universe,
            name=f"{merged}")

    @classmethod
    def any(cls, universe: CodeUniverse = CodeUniverse.UNICODE) -> CharSet[C]:
        return cls(
            predicate=lambda c: True, 
            interval=universe.interval,
            universe=universe,
            name=".")
    
    @classmethod
    def none(cls, universe: CodeUniverse = CodeUniverse.UNICODE) -> CharSet[C]:
        return cls(
            predicate=lambda c: False, 
            interval=tuple(),
            universe=universe,
            name="∅")

    def sample(self, rnd: random.Random) -> C:
        range = rnd.choice(self.interval)
        point = rnd.randint(range[0], range[1])
        if self.universe == CodeUniverse.BYTE:
            return bytes([point])  # type: ignore
        else:
            return chr(point)  # type: ignore

    def overlaps(self, intv: Tuple[int, int]) -> bool:
        for start, end in self.interval:
            if (end >= intv[0] and start <= intv[1]):
                return True
        return False

    def matches_interval(self, cc: C) -> bool:
        if len(cc) != 1:
            raise CodepointError(f"Expected single character, got {cc!r}", offending=cc, expect="single character")
        if isinstance(cc, str):
            c = ord(cc)
            return any(start <= c <= end for start, end in self.interval)
        elif isinstance(cc, bytes):
            c = cc[0]
            return any(start <= c <= end for start, end in self.interval)
        else:
            raise CodepointError(f"Expected str, bytes, got {type(cc)}", offending=cc, expect="str, bytes")

    def matches(self, c: C) -> bool:
        if len(c) != 1:
            raise CodepointError(f"Expected single character, got {c!r}", offending=c, expect="single character")
        if isinstance(c, str):
            return self.predicate(ord(c))
        elif isinstance(c, bytes):
            return self.predicate(c[0])
        else:
            raise CodepointError(f"Expected str, bytes, got {type(c)}", offending=c, expect="str, bytes")
        
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
            raise MixedUniverseError(f"Cannot union char classes with different universes: {self.universe} and {other.universe}", offending=other.universe, expect=self.universe)
        intv = tuple(self.merge_intervals(list(self.interval) + list(other.interval)))
        return CharSet(
            lambda c: self.predicate(c) or other.predicate(c), 
            intv,
            universe=self.universe,
            name=f"({self.name} | {other.name})")
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
            raise MixedUniverseError(f"Cannot union char classes with different universes: {self.universe} and {other.universe}", offending=other.universe, expect=self.universe)
        intv = tuple(self.intersect_interval(list(self.interval), list(other.interval)))
        
        return CharSet(
            lambda c: self.predicate(c) and other.predicate(c), 
            intv,
            universe=self.universe,
            name=f"({self.name} & {other.name})")
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
            raise MixedUniverseError(f"Cannot union char classes with different universes: {self.universe} and {other.universe}", offending=other.universe, expect=self.universe)
        intv = tuple(self.difference_interval(list(self.interval), list(other.interval)))
        return CharSet(
            lambda c: self.predicate(c) and not other.predicate(c), 
            intv,
            universe=self.universe,
            name=f"({self.name} - {other.name})")
    def __sub__(self, other: CharSet[C]) -> CharSet[C]:
        return self.difference(other)
    
    def complement(self) -> CharSet[C]:
        if self.interval == ():
            return CharSet.any(universe=self.universe)
        intv = tuple(self.difference_interval(list(self.universe.interval), list(self.interval)))
        return CharSet(
            lambda c: not self.predicate(c), 
            intv,
            universe=self.universe,
            name=f"~{self.name}")
    def __invert__(self) -> CharSet[C]:
        return self.complement()



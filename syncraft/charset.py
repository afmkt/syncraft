from __future__ import annotations

from typing import (
    TypeVar, Generic, Tuple, List, Callable
)
from dataclasses import dataclass
from syncraft.algebra import (
    SyncraftError
)
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
class CharClass(Generic[C]):
    predicate: Callable[[int], bool]       
    interval: Tuple[Tuple[int, int], ...] 
    universe: CodeUniverse
    name: str

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
    def create(cls, char: str | bytes, universe: CodeUniverse = CodeUniverse.UNICODE) -> CharClass[C]:
        cs: frozenset[int] = frozenset(ord(x) if isinstance(x, str) else x for x in char)
        intv = tuple((c, c) for c in sorted(cs))
        return cls(
            predicate=lambda c: c in cs, 
            interval=intv,
            universe=universe,
            name=f"'{cs}'")
    
    @classmethod
    def any(cls, universe: CodeUniverse = CodeUniverse.UNICODE) -> CharClass[C]:
        return cls(
            predicate=lambda c: True, 
            interval=universe.interval,
            universe=universe,
            name=".")
    
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
            raise CodepointError(f"Expected str, bytes, got {type(c)}", offending=c, expect="str, bytes")

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
        if not isinstance(other, CharClass):
            return NotImplemented
        return self.interval == other.interval and self.universe == other.universe

    def __hash__(self) -> int:
        return hash((self.interval, self.universe))


    def union(self, other: CharClass[C]) -> CharClass[C]:
        if self.universe != other.universe:
            raise MixedUniverseError(f"Cannot union char classes with different universes: {self.universe} and {other.universe}", offending=other.universe, expect=self.universe)
        intv = tuple(self.merge_intervals(list(self.interval) + list(other.interval)))
        return CharClass(
            lambda c: self.predicate(c) or other.predicate(c), 
            intv,
            universe=self.universe,
            name=f"({self.name} | {other.name})")
    def __or__(self, other: CharClass[C]) -> CharClass[C]:
        return self.union(other)
    
    def intersect(self, other: CharClass[C]) -> CharClass[C]:
        if self.universe != other.universe:
            raise MixedUniverseError(f"Cannot union char classes with different universes: {self.universe} and {other.universe}", offending=other.universe, expect=self.universe)
        intv = tuple(self.intersect_interval(list(self.interval), list(other.interval)))
        
        return CharClass(
            lambda c: self.predicate(c) and other.predicate(c), 
            intv,
            universe=self.universe,
            name=f"({self.name} & {other.name})")
    def __and__(self, other: CharClass[C]) -> CharClass[C]:
        return self.intersect(other)

    def difference(self, other: CharClass[C]) -> CharClass[C]:
        if self.universe != other.universe:
            raise MixedUniverseError(f"Cannot union char classes with different universes: {self.universe} and {other.universe}", offending=other.universe, expect=self.universe)
        intv = tuple(self.difference_interval(list(self.interval), list(other.interval)))
        return CharClass(
            lambda c: self.predicate(c) and not other.predicate(c), 
            intv,
            universe=self.universe,
            name=f"({self.name} - {other.name})")
    def __sub__(self, other: CharClass[C]) -> CharClass[C]:
        return self.difference(other)
    
    def complement(self) -> CharClass[C]:
        intv = tuple(self.difference_interval(list(self.universe.interval), list(self.interval)))
        return CharClass(
            lambda c: not self.predicate(c), 
            intv,
            universe=self.universe,
            name=f"~{self.name}")
    def __invert__(self) -> CharClass[C]:
        return self.complement()



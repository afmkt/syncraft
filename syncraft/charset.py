from __future__ import annotations

from typing import (
    TypeVar, Generic, Tuple, ClassVar, Any, Iterable, Sequence, Hashable
)
from syncraft.alphabet import AlphabetProtocol
from dataclasses import dataclass, field
from syncraft.algebra import (
    SyncraftError
)
import random
from functools import lru_cache

class MixedUniverseError(SyncraftError):
    pass



C = TypeVar('C', bound=Hashable)


CharSet = Tuple[Tuple[int, int], ...]

@dataclass(frozen=True, slots=True)
class CharSetFactory(Generic[C]):
    START_CP: ClassVar[int] = -1
    END_CP: ClassVar[int] = -2
    alphabet: AlphabetProtocol[C]


    @staticmethod
    def partition_charsets(intervals: Sequence[Tuple[int, int]]) -> Sequence[Tuple[int, int]]:
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
    def difference_interval(a: Sequence[Tuple[int, int]], b: Sequence[Tuple[int, int]]) -> Sequence[Tuple[int, int]]:
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
    def intersect_interval(a: Sequence[Tuple[int, int]], b: Sequence[Tuple[int, int]]) -> Sequence[Tuple[int, int]]:
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
    def merge_intervals(intv: Sequence[Tuple[int, int]]) -> Sequence[Tuple[int, int]]:
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

    def create_one(self, c: C) -> CharSet:
        codepoint = self.alphabet.encode(c)
        return ((codepoint, codepoint),)

    def create(self, chars: Sequence[C] | bytes) -> CharSet:
        if not chars:
            return self.none()
        else:
            # for bytes the c is an int, Alphabet.encode handles that
            codepoints = {self.alphabet.encode(c) for c in chars} # type: ignore
            return tuple((cp, cp) for cp in sorted(codepoints))
        

    
    def from_interval(self, intv: Sequence[Tuple[int, int]]) -> CharSet:
        merged = tuple(self.merge_intervals(intv))
        return merged
        

    
    def start(self) -> CharSet:
        return ((self.START_CP, self.START_CP),)

    def end(self) -> CharSet:
        return ((self.END_CP, self.END_CP),)

    
    def is_start(self, cs: CharSet) -> bool:
        return cs == ((self.START_CP, self.START_CP),)

    def is_end(self, cs: CharSet) -> bool:
        return cs == ((self.END_CP, self.END_CP),)

    def is_anchor(self, cs: CharSet) -> bool:
        anchor_set = (self.START_CP, self.END_CP)
        return any(start in anchor_set or end in anchor_set for start, end in cs)

    def any(self) -> CharSet:
        return self.alphabet.codes
        
    
    def none(self) -> CharSet:
        return tuple()
        

    def sample(self, cs: CharSet | int, rnd: random.Random) -> C:
        if isinstance(cs, int):
            return self.alphabet.decode(cs)
        range = rnd.choice(cs)
        point = rnd.randint(range[0], range[1])
        return self.alphabet.decode(point)

    def overlaps(self, cs: CharSet, intv: Tuple[int, int]) -> bool:
        for start, end in cs:
            if (end >= intv[0] and start <= intv[1]):
                return True
        return False


    def match_codepoint(self, cs: CharSet, codepoint: int) -> bool:
        return any(start <= codepoint <= end for start, end in cs)    

    def matches(self, cs: CharSet, cc: C) -> bool:
        c = self.alphabet.encode(cc)
        return any(start <= c <= end for start, end in cs)

        
    def __call__(self, cs: CharSet, c: C) -> bool:

        return self.matches(cs, c)



    def union(self, this: CharSet, other: CharSet) -> CharSet:
        if this is other:
            return this
        if this == ():
            return other
        if other == ():
            return this
        intv = tuple(self.merge_intervals(list(this) + list(other)))
        return intv
        
    def union_many(self, *charsets: CharSet) -> CharSet:
        intervals: list[Tuple[int, int]] = []
        for cs in charsets:
            if cs == ():
                continue
            intervals.extend(cs)
        if not intervals:
            return self.none()
        merged = tuple(self.merge_intervals(intervals))
        return merged

    def intersect(self, this: CharSet, other: CharSet) -> CharSet:
        if this is other:
            return this
        if this == ():
            return this
        if other == ():
            return other
        return tuple(self.intersect_interval(list(this), list(other)))
    
    def intersect_many(self, *charsets: CharSet) -> CharSet:
        if not charsets:
            return self.any()
        result = charsets[0]
        for cs in charsets[1:]:
            result = self.intersect(result, cs)
            if result == ():
                break
        return result
        

    def difference(self, this: CharSet, other: CharSet) -> CharSet:
        if this is other:
            return self.none()
        if this == ():
            return this
        if other == ():
            return this
        return tuple(self.difference_interval(list(this), list(other)))
        
            
    def complement(self, cs: CharSet) -> CharSet:
        if cs == ():
            return self.any()
        return tuple(self.difference_interval(list(self.alphabet.codes), list(cs)))
    
    def str(self, cs: CharSet) -> str:
        parts = []
        START_CP = self.START_CP
        END_CP = self.END_CP
        alphabet = self.alphabet
        for start, end in cs:
            def fmt(cp: int) -> str:
                if cp == START_CP:
                    return "<START>"
                if cp == END_CP:
                    return "<END>"
                try:
                    return str(alphabet.decode(cp))
                except Exception:
                    return f"<{cp}>"
            if start == end:
                parts.append(fmt(start))
            else:
                parts.append(f"{fmt(start)}-{fmt(end)}")
        return f"{', '.join(parts)}"
    
    

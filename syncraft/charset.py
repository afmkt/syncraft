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


    

@dataclass(frozen=True, slots=True)
class CharSet(Generic[C]):
    START_CP: ClassVar[int] = -1
    END_CP: ClassVar[int] = -2

    interval: Tuple[Tuple[int, int], ...]
    alphabet: AlphabetProtocol[C]

    @classmethod
    def new(cls, interval: Tuple[Tuple[int, int], ...], alphabet: AlphabetProtocol[C]) -> 'CharSet[C]':
        c = cls.__new__(cls)
        object.__setattr__(c, 'interval', interval)
        object.__setattr__(c, 'alphabet', alphabet)
        return c

    @staticmethod
    @lru_cache(maxsize=4096)  
    def _build(alphabet: AlphabetProtocol[Any], codepoints: Tuple[int, ...]) -> 'CharSet':

        intv: Tuple[Tuple[int, int], ...] = tuple((c, c) for c in codepoints)

        return CharSet.new(interval=intv, alphabet=alphabet)


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

    @classmethod
    def create(cls, char: str | bytes | Sequence[C], alphabet: AlphabetProtocol) -> 'CharSet[C]':
        # Fast path: single character string
        if isinstance(char, str) and len(char) == 1:
            cp = alphabet.encode(char)
            return cls._build(alphabet, (cp,))
        # Fast path: single byte
        if isinstance(char, bytes) and len(char) == 1:
            cp = alphabet.encode(char)
            return cls._build(alphabet, (cp,))

        # Normalize input to iterable of elements
        if isinstance(char, (str, bytes)):
            iterable: Iterable[Any] = char  # iterate over characters
        else:
            raise SyncraftError(f"Expected str, bytes, or list/tuple of Enum or characters, got {type(char)}", offender=char, expect="str, bytes, or list/tuple of Enum or characters")

        codepoints_set = {alphabet.encode(x) for x in iterable}
        if not codepoints_set:
            # Preserve earlier semantics: represent empty via none()
            return CharSet.none(alphabet)
        codepoints = tuple(sorted(codepoints_set))
        return cls._build(alphabet, codepoints)

    @classmethod
    def from_interval(cls, intv: Sequence[Tuple[int, int]], alphabet: AlphabetProtocol) -> CharSet[C]:
        merged = tuple(cls.merge_intervals(intv))
        return cls(interval=merged, alphabet=alphabet)

    @classmethod
    def start(cls, alphabet: AlphabetProtocol) -> CharSet[C]:
        return cls.from_interval([(cls.START_CP, cls.START_CP)], alphabet=alphabet)

    @classmethod
    def end(cls, alphabet: AlphabetProtocol) -> CharSet[C]:
        return cls.from_interval([(cls.END_CP, cls.END_CP)], alphabet=alphabet)

    @classmethod
    def is_start(cls, cs: 'CharSet') -> bool:
        return cs.interval == ((cls.START_CP, cls.START_CP),)

    @classmethod
    def is_end(cls, cs: 'CharSet') -> bool:
        return cs.interval == ((cls.END_CP, cls.END_CP),)

    def is_anchor(self) -> bool:
        return any(start in (self.START_CP, self.END_CP) or end in (self.START_CP, self.END_CP)
                   for start, end in self.interval)

    @classmethod
    def any(cls, alphabet: AlphabetProtocol) -> CharSet[C]:
        return cls.new(interval=alphabet.codes, alphabet=alphabet)
        
    
    @classmethod
    def none(cls, alphabet: AlphabetProtocol) -> CharSet[C]:
        return cls.new(interval=tuple(), alphabet=alphabet)
        

    def sample(self, rnd: random.Random) -> C:
        range = rnd.choice(self.interval)
        point = rnd.randint(range[0], range[1])
        return self.alphabet.decode(point)

    def overlaps(self, intv: Tuple[int, int]) -> bool:
        for start, end in self.interval:
            if (end >= intv[0] and start <= intv[1]):
                return True
        return False


    def matches(self, cc: C) -> bool:
        c = self.alphabet.encode(cc)
        return any(start <= c <= end for start, end in self.interval)
    
        
    def __call__(self, c: C) -> bool:

        return self.matches(c)

    def __contains__(self, c: C) -> bool:
        return self.matches(c)
        
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CharSet):
            return NotImplemented
        return self.interval == other.interval and self.alphabet == other.alphabet

    def __hash__(self) -> int:
        return hash((self.interval, self.alphabet))


    def union(self, other: CharSet[C]) -> CharSet[C]:
        if self is other:
            return self
        if self.interval == ():
            return other
        if other.interval == ():
            return self
        if self.alphabet != other.alphabet:
            raise MixedUniverseError(f"Cannot union char classes with different universes: {self.alphabet} and {other.alphabet}", offender=other.alphabet, expect=self.alphabet)
        intv = tuple(self.merge_intervals(list(self.interval) + list(other.interval)))
        return CharSet.new(interval=intv, alphabet=self.alphabet)
        
    
    def __or__(self, other: CharSet[C]) -> CharSet[C]:
        return self.union(other)
    
    def intersect(self, other: CharSet[C]) -> CharSet[C]:
        if self is other:
            return self
        if self.interval == ():
            return self
        if other.interval == ():
            return other
        if self.alphabet != other.alphabet:
            raise MixedUniverseError(f"Cannot union char classes with different universes: {self.alphabet} and {other.alphabet}", offender=other.alphabet, expect=self.alphabet)
        intv = tuple(self.intersect_interval(list(self.interval), list(other.interval)))
        return CharSet.new(interval=intv, alphabet=self.alphabet)
        
    
    def __and__(self, other: CharSet[C]) -> CharSet[C]:
        return self.intersect(other)

    def difference(self, other: CharSet[C]) -> CharSet[C]:
        if self is other:
            return CharSet.none(alphabet=self.alphabet)
        if self.interval == ():
            return self
        if other.interval == ():
            return self
        if self.alphabet != other.alphabet:
            raise MixedUniverseError(f"Cannot union char classes with different universes: {self.alphabet} and {other.alphabet}", offender=other.alphabet, expect=self.alphabet)
        intv = tuple(self.difference_interval(list(self.interval), list(other.interval)))
        return CharSet.new(interval=intv, alphabet=self.alphabet)
        
    
    def __sub__(self, other: CharSet[C]) -> CharSet[C]:
        return self.difference(other)
    
    @property
    def complement(self) -> CharSet[C]:
        if self.interval == ():
            return CharSet.any(alphabet=self.alphabet)
        intv = tuple(self.difference_interval(list(self.alphabet.codes), list(self.interval)))
        return CharSet.new(interval=intv, alphabet=self.alphabet)
        
    
    def __neg__(self) -> CharSet[C]:
        return self.complement

    def __bool__(self) -> bool:
        return self.interval != ()
    
    def __str__(self) -> str:
        parts = []
        for start, end in self.interval:
            def fmt(cp: int) -> str:
                if cp == CharSet.START_CP:
                    return "<START>"
                if cp == CharSet.END_CP:
                    return "<END>"
                try:
                    return str(self.alphabet.decode(cp))
                except Exception:
                    return f"<{cp}>"
            if start == end:
                parts.append(fmt(start))
            else:
                parts.append(f"{fmt(start)}-{fmt(end)}")
        return f"{', '.join(parts)}"
    
    

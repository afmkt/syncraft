from __future__ import annotations

from typing import (
    TypeVar, Generic, Tuple, Type, ClassVar, Any, Iterable, Sequence, Optional
)

from syncraft.utils import FrozenDict
from dataclasses import dataclass, field
from syncraft.algebra import (
    SyncraftError
)
import random
from functools import cached_property, lru_cache
from enum import Enum

class MixedUniverseError(SyncraftError):
    pass

class CodepointError(SyncraftError):
    pass

C = TypeVar('C', bound=str | int | Enum | bytes | Any)


@dataclass(frozen=True)
class CodeUniverse(Generic[C]):
    ASCII: ClassVar[Tuple[int, int]] = (0, 0x7F)
    UNICODE: ClassVar[Tuple[int, int]] = (0, 0x10FFFF)
    BYTE: ClassVar[Tuple[int, int]] = (0, 0xFF)
    value: Tuple[int, int]
    space: Type[C] | frozenset[str | int]
    int2c: FrozenDict[int, C] = field(default_factory=FrozenDict, repr=False)
    c2int: FrozenDict[C, int] = field(default_factory=FrozenDict, repr=False)

    def to_dict(self) -> dict:
        if self.value == self.ASCII and self.space is str:
            return {'type': 'ASCII'}
        elif self.value == self.UNICODE and self.space is str:
            return {'type': 'UNICODE'}
        elif self.value == self.BYTE and self.space is bytes:
            return {'type': 'BYTE'}
        elif isinstance(self.space, type) and issubclass(self.space, Enum):
            return {
                'type': 'ENUM',
                'enum_class': self.space.__name__,
                'members': [e.name for e in self.space]
            }
        elif isinstance(self.space, frozenset):
            # Only allow str or int in sets
            members = []
            for m in self.space:
                if isinstance(m, (str, int)):
                    members.append(m)
                else:
                    raise ValueError(f"SET universes must only contain str or int, got {type(m)}: {m}")
            return {
                'type': 'SET',
                'members': members
            }
        # If we reach here, the universe type is unsupported/illegal.
        raise ValueError(f"Unsupported CodeUniverse type: value={self.value}, space={self.space}")

    @classmethod
    def from_dict(cls, d: dict, enum_classes: 'Optional[dict]' = None) -> 'CodeUniverse':
        t = d['type']
        if t == 'ASCII':
            return cls.ascii()
        elif t == 'UNICODE':
            return cls.unicode()
        elif t == 'BYTE':
            return cls.byte()
        elif t == 'ENUM':
            if enum_classes is None or d['enum_class'] not in enum_classes:
                raise ValueError(f"Enum class {d['enum_class']} not provided in enum_classes dict")
            enum_type = enum_classes[d['enum_class']]
            return cls.enum(enum_type)
        elif t == 'SET':
            members = set()
            for m in d['members']:
                if isinstance(m, (str, int)):
                    members.add(m)
                else:
                    raise ValueError(f"SET universes must only contain str or int, got {type(m)}: {m}")
            return cls.set(frozenset(members))
        # No 'CUSTOM' case: all valid universes are handled above.
        else:
            raise ValueError(f"Unknown CodeUniverse type: {t}")

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
            if isinstance(self.space, (frozenset)):
                return f"FROZENSET({self.value[0]}-{self.value[1]})"
            else:
                return f"{self.space.__name__}({self.value[0]}-{self.value[1]})"
    
    def concat(self, cs: Sequence[C]) -> str | bytes | Tuple[C, ...]:
        space = self.space
        if len(cs) == 0:
            if space is str:
                return ''
            elif space is bytes:
                return b''
            else:
                return ()
        else:
            if space is str:
                return ''.join(cs)  # type: ignore
            elif space is bytes:
                first = cs[0]
                if isinstance(first, int):
                    return bytes(list(cs))  # type: ignore
                elif isinstance(first, (bytes, bytearray, memoryview)):
                    return b''.join(cs)  # type: ignore
                else:
                    raise CodepointError(
                        f"Expected bytes or int for byte universe, got {type(first)}", 
                        offender=first, 
                        expect="bytes or int")
            else:
                return tuple(cs)  

    def code2int(self, c: C) -> int:
        if isinstance(c, str):
            if len(c) != 1:
                raise CodepointError(f"Expected single character, got {c!r}", offender=c, expect="single character")
            if self.space is not str:
                raise CodepointError(f"Expected character from universe {self}, got str {c!r}", offender=c, expect=f"character in {self.space}")
            cp = ord(c)
        elif isinstance(c, bytes):
            if len(c) != 1:
                raise CodepointError(f"Expected single byte, got {c!r}", offender=c, expect="single byte")
            if self.space is not bytes:
                raise CodepointError(f"Expected character from universe {self}, got bytes {c!r}", offender=c, expect=f"byte in {self.space}")
            cp = c[0]
        elif self.space is bytes and isinstance(c, int):
            cp = c
        elif self.space is str and isinstance(c, int):
            cp = c
        elif isinstance(c, Enum):
            if c not in self.c2int:
                raise CodepointError(f"Enum value {c!r} not in universe {self}", offender=c, expect=f"Enum in {list(self.c2int.keys())}")
            cp = self.c2int[c]
        elif isinstance(self.space, frozenset):
            if c not in self.space or c not in self.c2int:
                raise CodepointError(f"Expected single character, got set {c!r}", offender=c, expect="single character")
            cp = self.c2int[c]
        else:
            raise CodepointError(f"Expected str, bytes, or Enum, got {type(c)}", offender=c, expect="str, bytes, or Enum")
        if not (self.value[0] <= cp <= self.value[1]):
            raise CodepointError(f"Character {c!r} (codepoint {cp}) out of bounds for universe {self}", offender=c, expect=f"codepoint in range {self.value}")
        return cp
    
    def int2code(self, cp: int) -> C:
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

    @classmethod
    def set(cls, space: frozenset[str | int]) -> CodeUniverse[C]:
        if not space:
            raise SyncraftError("Cannot create CodeUniverse from empty set", offender=space, expect="non-empty set")
        int2c: FrozenDict[int, C] = FrozenDict({i: c for i, c in enumerate(space)})
        c2int: FrozenDict[C, int] = FrozenDict({c: i for i, c in enumerate(space)})
        return cls(value=(0, len(space)-1), space=space, int2c=int2c, c2int=c2int) # type: ignore

@dataclass(frozen=True)
class CharSet(Generic[C]):
    # Internal sentinel codepoints for anchors (not part of any CodeUniverse interval)
    START_CP: ClassVar[int] = -1
    END_CP: ClassVar[int] = -2

    interval: Tuple[Tuple[int, int], ...]
    universe: CodeUniverse

    @staticmethod
    @lru_cache(maxsize=4096)  
    def _build(universe: CodeUniverse, codepoints: Tuple[int, ...]) -> 'CharSet':

        intv: Tuple[Tuple[int, int], ...] = tuple((c, c) for c in codepoints)

        return CharSet(

            interval=intv,
            universe=universe
        )

    @classmethod
    def cache_info(cls):  # pragma: no cover - utility
        """Expose LRU cache statistics (hits, misses, current size, max size)."""
        return cls._build.cache_info()  # type: ignore[attr-defined]


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
    def create(cls, char: str | bytes | Sequence[Enum] | Sequence[C], universe: CodeUniverse) -> 'CharSet[C]':
        """Create (and intern) a CharSet from a collection of literal symbols.

        Normalization steps:
          1. Interpret input as an iterable of atomic symbols (each element OR each character/byte of str/bytes).
          2. Map symbols to codepoints via universe.code2int.
          3. Deduplicate & sort to obtain a canonical tuple (ensures stable interning key).

        Fast paths handle single-element inputs to avoid tuple/list allocations.
        """
        # Fast path: single character string
        if isinstance(char, str) and len(char) == 1:
            cp = universe.code2int(char)
            return cls._build(universe, (cp,))
        # Fast path: single byte
        if isinstance(char, bytes) and len(char) == 1:
            cp = universe.code2int(char)
            return cls._build(universe, (cp,))

        # Normalize input to iterable of elements
        if isinstance(char, (str, bytearray, memoryview, bytes, list, tuple)):
            iterable: Iterable[Any] = char  # iterate over characters
        else:
            raise SyncraftError(f"Expected str, bytes, or list/tuple of Enum or characters, got {type(char)}", offender=char, expect="str, bytes, or list/tuple of Enum or characters")

        codepoints_set = {universe.code2int(x) for x in iterable}
        if not codepoints_set:
            # Preserve earlier semantics: represent empty via none()
            return CharSet.none(universe)
        codepoints = tuple(sorted(codepoints_set))
        return cls._build(universe, codepoints)

    @classmethod
    def from_interval(cls, intv: Sequence[Tuple[int, int]], universe: CodeUniverse) -> CharSet[C]:
        merged = tuple(cls.merge_intervals(intv))
        return cls(

            interval=merged,
            universe=universe)

    @classmethod
    def start(cls, universe: CodeUniverse) -> CharSet[C]:
        return cls.from_interval([(cls.START_CP, cls.START_CP)], universe)

    @classmethod
    def end(cls, universe: CodeUniverse) -> CharSet[C]:
        return cls.from_interval([(cls.END_CP, cls.END_CP)], universe)

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
    def any(cls, universe: CodeUniverse) -> CharSet[C]:
        return cls(

            interval=universe.interval,
            universe=universe)
    
    @classmethod
    def none(cls, universe: CodeUniverse) -> CharSet[C]:
        return cls(

            interval=tuple(),
            universe=universe)

    def sample(self, rnd: random.Random) -> C:
        range = rnd.choice(self.interval)
        point = rnd.randint(range[0], range[1])
        return self.universe.int2code(point)

    def overlaps(self, intv: Tuple[int, int]) -> bool:
        for start, end in self.interval:
            if (end >= intv[0] and start <= intv[1]):
                return True
        return False


    def matches(self, cc: C) -> bool:
        c = self.universe.code2int(cc)
        return any(start <= c <= end for start, end in self.interval)
    
        
    def __call__(self, c: C) -> bool:

        return self.matches(c)

    def __contains__(self, c: C) -> bool:
        return self.matches(c)
        
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

            intv,
            universe=self.universe)
    
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
                    return str(self.universe.int2code(cp))
                except Exception:
                    return f"<{cp}>"
            if start == end:
                parts.append(fmt(start))
            else:
                parts.append(f"{fmt(start)}-{fmt(end)}")
        return f"{', '.join(parts)}"
    
    def __pretty__(self) -> str:
        return str(self)    
    
    def __rich__(self) -> str:
        return str(self) 
    

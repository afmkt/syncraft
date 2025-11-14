from __future__ import annotations
from typing import Dict, Protocol, runtime_checkable, Tuple, TypeVar, Generic, Hashable, Any, ClassVar, Type, Callable,  Sequence
from dataclasses import dataclass, field
from syncraft.utils import FrozenDict
from functools import cached_property
from enum import Enum
from syncraft.algebra import SyncraftError
class CodepointError(SyncraftError):
    pass


C = TypeVar('C', bound=Hashable)

@runtime_checkable
class AlphabetProtocol(Protocol[C]):
    @cached_property
    def symbols(self) -> Tuple[Tuple[C, C], ...]:
        ret = []
        for start, end in self.codes:
            ret.append((self.decode(start), self.decode(end)))
        return tuple(ret)
    def index(self, symbol: C) -> int: 
        return self.encode(symbol)
    def symbol_at(self, index: int) -> C:
        return self.decode(index)

    def __hash__(self) -> int: ...
        
    @property
    def space(self) -> Type[C] | frozenset[C] | Type[Enum]: ...
    @property
    def codes(self) -> Tuple[Tuple[int, int], ...]: ...
    def concat(self, cs: Sequence[C]) -> C | Tuple[C, ...]: ...
    def encode(self, symbol: C) -> int: ...
    def decode(self, code: int) -> C: ...


class Alphabet(Generic[C]):
    registry: ClassVar[Dict[Type[Any], Callable[[], AlphabetProtocol[Any]]]] = dict()
    @classmethod
    def register(cls, symbol_type: Type[C]) -> Callable[[Callable[[], AlphabetProtocol[C]]], Callable[[], AlphabetProtocol[C]]]:
        def decorator(factory: Callable[[], AlphabetProtocol[C]]) -> Callable[[], AlphabetProtocol[C]]:
            cls.registry[symbol_type] = factory
            return factory
        return decorator
    
    @classmethod
    def get(cls, symbol_type: Type[C]) -> AlphabetProtocol[C]:
        if symbol_type not in cls.registry:
            raise ValueError(f"No alphabet registered for symbol type: {symbol_type}")
        return cls.registry[symbol_type]()
    


@Alphabet.register(str)
@dataclass(frozen=True)
class TextAlphabet(AlphabetProtocol[str]):
    @property
    def space(self) -> Type[str]:
        return str
    @property
    def codes(self) -> Tuple[Tuple[int, int], ...]:
        return ((0, 0x10FFFF), )
    
    def encode(self, symbol: str) -> int:
        assert len(symbol) == 1, "Text symbol must be a single character"
        return ord(symbol)
    
    def decode(self, code: int) -> str:
        return chr(code)
    
    def concat(self, cs: Sequence[str]) -> str:
        return ''.join(cs)
    
@Alphabet.register(bytes)
@dataclass(frozen=True)
class ByteAlphabet(AlphabetProtocol[bytes]):
    @property
    def space(self) -> Type[bytes]:
        return bytes
    @property
    def codes(self) -> Tuple[Tuple[int, int], ...]:
        return ((0, 255), )
    
    def encode(self, symbol: bytes | int) -> int:
        if isinstance(symbol, int):
            return symbol
        if not isinstance(symbol, bytes) or not len(symbol) == 1:
            raise CodepointError(f"Byte symbol must be of type bytes, got {symbol!r}", offender=symbol, expect="bytes")
        return symbol[0]
    
    def decode(self, code: int) -> bytes:
        return bytes([code])
    
    def concat(self, cs: Sequence[bytes]) -> bytes:
        return b''.join(cs)


@dataclass(frozen=True)
class FiniteAlphabet(AlphabetProtocol[C], Generic[C]):
    _space: Type[Enum] | frozenset[C] | Sequence[C]
    code2int: FrozenDict[C, int] = field(default_factory=FrozenDict, init=False)
    int2code: FrozenDict[int, C] = field(default_factory=FrozenDict, init=False)
    
    @cached_property
    def space(self) -> Type[Enum] | frozenset[C]:
        if isinstance(self._space, type) and issubclass(self._space, Enum):
            return self._space
        elif isinstance(self._space, frozenset):
            return self._space
        else:
            return frozenset(self._space)

    @cached_property
    def codes(self) -> Tuple[Tuple[int, int], ...]:
        return ((0, len(self.code2int) - 1), )
    
    def encode(self, symbol: C) -> int:
        return self.code2int[symbol]
    
    def decode(self, code: int) -> C:
        return self.int2code[code]
    
    def concat(self, cs: Sequence[C]) -> Tuple[C, ...]:
        return tuple(cs)
    

    def __post_init__(self) -> None:
        if isinstance(self.space, type) and issubclass(self.space, Enum):
            elements = list(self.space)
            code2int: FrozenDict[C, int] = FrozenDict({s: i for i, s in enumerate(elements)})
            int2code: FrozenDict[int, C] = FrozenDict({i: s for s, i in code2int.items()})
            object.__setattr__(self, 'code2int', code2int)
            object.__setattr__(self, 'int2code', int2code)
        else:
            _elements = list(self.space)
            _code2int: FrozenDict[C, int] = FrozenDict({s: i for i, s in enumerate(_elements)})
            _int2code: FrozenDict[int, C] = FrozenDict({i: s for s, i in _code2int.items()})
            object.__setattr__(self, 'code2int', _code2int)
            object.__setattr__(self, 'int2code', _int2code)
    

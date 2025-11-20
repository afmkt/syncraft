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


class Alphabet(AlphabetProtocol[C]):
    registry: ClassVar[Dict[Type[Any] | frozenset[Any], AlphabetProtocol[Any]]] = dict()
    
    @property
    def space(self) -> Type[C] | frozenset[C] | Type[Enum]:
        return self.inner.space
    @property
    def codes(self) -> Tuple[Tuple[int, int], ...]:
        return self.inner.codes
    def concat(self, cs: Sequence[C]) -> C | Tuple[C, ...]:
        return self.inner.concat(cs)
    def encode(self, symbol: C) -> int:
        return self.inner.encode(symbol)
    def decode(self, code: int) -> C:
        return self.inner.decode(code)
    
    def __hash__(self) -> int:
        return hash(self.inner)
    
    def __eq__(self, other: object, /) -> bool:
        if not isinstance(other, Alphabet):
            return False
        return self.inner is other.inner

    def __init__(self, symbol_type: Type[C] | Sequence[C] | Type[Enum]) -> None:
        self.inner = Alphabet._get(symbol_type)
    
    @classmethod
    def register(cls, symbol_type: Type[C]) -> Callable[[Callable[[], AlphabetProtocol[C]]], Callable[[], AlphabetProtocol[C]]]:
        def decorator(factory: Callable[[], AlphabetProtocol[C]]) -> Callable[[], AlphabetProtocol[C]]:
            cls.registry[symbol_type] = factory()
            return factory
        return decorator
    
    @classmethod
    def finite(cls, symbols: Type[Enum] | Sequence[C]) -> AlphabetProtocol[C]:
        try:
            return cls._get(symbols)
        except ValueError:
            pass
        alphabet = FiniteAlphabet.create(symbols)
        cls.registry[alphabet.space] = alphabet
        return alphabet

    @classmethod
    def _get(cls, symbol_type: Type[C] | Type[Enum] | Sequence[C]) -> AlphabetProtocol[C]:
        if isinstance(symbol_type, type):
            if symbol_type in cls.registry:
                return cls.registry[symbol_type]                
        else:
            key = frozenset(symbol_type)
            if key in cls.registry:
                return cls.registry[key]
        raise ValueError(f"No alphabet registered for symbol type: {symbol_type}")
    


@Alphabet.register(str)
@dataclass(frozen=True, slots=True)
class TextAlphabet(AlphabetProtocol[str]):
    @property
    def space(self) -> Type[str]:
        return str
    @property
    def codes(self) -> Tuple[Tuple[int, int], ...]:
        return ((0, 0x10FFFF), )
    
    def encode(self, symbol: str) -> int:
        try:
            return ord(symbol)
        except Exception:
            raise CodepointError(f"Text symbol must be a single character, got {symbol!r}", offender=symbol, expect=str)

    def decode(self, code: int) -> str:
        try:
            return chr(code)
        except Exception:
            raise CodepointError(f"Code {code!r} is not a valid Unicode code point", offender=code, expect=self.codes)

    def concat(self, cs: Sequence[str]) -> str:
        return ''.join(cs)
    
@Alphabet.register(bytes)
@dataclass(frozen=True, slots=True)
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
        else:
            try:
                assert len(symbol) == 1
                return symbol[0] # type: ignore
            except Exception:
                raise CodepointError(f"Byte symbol must be of type bytes, got {symbol!r}", offender=symbol, expect="bytes")
    
    def decode(self, code: int) -> bytes:
        try:
            return bytes([code])
        except Exception:
            raise CodepointError(f"Code {code!r} is not a valid byte", offender=code, expect=self.codes)

    def concat(self, cs: Sequence[bytes]) -> bytes:
        return b''.join(cs)


@dataclass(frozen=True, slots=True)
class FiniteAlphabet(AlphabetProtocol[C], Generic[C]):
    _space: Type[Enum] | frozenset[C]
    code2int: FrozenDict[C, int] = field(default_factory=FrozenDict)
    int2code: FrozenDict[int, C] = field(default_factory=FrozenDict)

    @property
    def space(self) -> Type[Enum] | frozenset[C]:
        return self._space
    
    @property
    def codes(self) -> Tuple[Tuple[int, int], ...]:
        return ((0, len(self.code2int) - 1), )
    
    def encode(self, symbol: C) -> int:
        try:
            return self.code2int[symbol]
        except Exception:
            raise CodepointError(f"Symbol {symbol!r} not in alphabet", offender=symbol, expect=self.space)

    def decode(self, code: int) -> C:
        try:
            return self.int2code[code]
        except Exception:
            raise CodepointError(f"Code {code!r} not in alphabet", offender=code, expect=self.codes)

    def concat(self, cs: Sequence[C]) -> Tuple[C, ...]:
        return tuple(cs)
    
    @classmethod
    def create(cls, symbols: Type[Enum] | Sequence[C]) -> AlphabetProtocol[C]:
        if isinstance(symbols, type) and issubclass(symbols, Enum):
            elements = list(symbols)
            code2int: FrozenDict[C, int] = FrozenDict({s: i for i, s in enumerate(elements)})
            int2code: FrozenDict[int, C] = FrozenDict({i: s for s, i in code2int.items()})
            return cls(_space=symbols, code2int=code2int, int2code=int2code)
        else:
            _elements = list(symbols)
            _code2int: FrozenDict[C, int] = FrozenDict({s: i for i, s in enumerate(_elements)})
            _int2code: FrozenDict[int, C] = FrozenDict({i: s for s, i in _code2int.items()})
            return cls(_space=frozenset(_elements), code2int=_code2int, int2code=_int2code)
    

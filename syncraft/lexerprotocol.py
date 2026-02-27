from __future__ import annotations

from typing import Protocol, runtime_checkable, Generic, Tuple, Dict, Optional, Hashable, Any, TypeVar, Callable
from dataclasses import dataclass, field
from enum import Enum
import random
from pathlib import Path
from abc import ABC, abstractmethod

Tag = str | Enum | None
C = TypeVar('C', bound=Hashable)


@dataclass(frozen=True, slots=True)
class LexerError:
    message: str
    index: int
    offender: Hashable
    expect: frozenset[Hashable]
    @classmethod
    def new(cls, message: str, index: int, offender: Hashable, expect: frozenset[Hashable]) -> LexerError:
        obj = cls.__new__(cls)
        object.__setattr__(obj, 'message', message)
        object.__setattr__(obj, 'index', index)
        object.__setattr__(obj, 'offender', offender)
        object.__setattr__(obj, 'expect', expect)
        return obj

    @classmethod
    def message_only(cls, message: str) -> "LexerError":
        return cls(message=message, index=-1, offender=None, expect=frozenset())


@dataclass(frozen=True, slots=True)
class LexerResult(Generic[C]):
    tag: Tag
    start: int
    end: int
    skip: bool 
    value: Any | None = None
    

    @classmethod
    def new(cls, tag: Tag, start: int, end: int, skip: bool, value: Any | None = None) -> "LexerResult[C]":
        obj = cls.__new__(cls)
        object.__setattr__(obj, 'tag', tag)
        object.__setattr__(obj, 'start', start)
        object.__setattr__(obj, 'end', end)
        object.__setattr__(obj, 'skip', skip)
        object.__setattr__(obj, 'value', value)
        return obj



@runtime_checkable
class LexerProtocol(Protocol, Generic[C]):
    def reset(self) -> None: ...

    def match(self, tag: frozenset[Tag], char: C, index: int) -> LexerError | None | LexerResult[C]: ...

    def verify(self, tag: frozenset[Tag], value: Any) -> bool: ...

    def tags(self) -> frozenset[str|Enum|None]: ...

    def gen(self, tag: Tag, rng: random.Random) -> Tuple[Tuple[Any, ...], Dict[str, Any]]: ...

    def candidate(self) -> LexerError | LexerResult[C]: ...
    
    @classmethod
    def create(cls, *args: Any, **kwargs: Any) -> Optional[LexerProtocol[C]]: ...


    @classmethod
    def from_kwargs(cls, *args: Any, **kwargs: Any) -> Tuple[Optional[LexerProtocol[C]], Dict[str, Any]]: ...

    @property
    def filepath(self) -> Optional[Path]: ...



class LexerBuilder(ABC, Generic[C]):
    @abstractmethod
    def __call__(self, arg: Any, **kwargs: Any) -> LexerBuilder[C]: ...
    @abstractmethod
    def resolve(self) -> LexerProtocol[C]: ...



    
from __future__ import annotations
from enum import Enum
from dataclasses import dataclass
from typing import List, Callable, Any, TypeVar, Generic, Hashable, Type, ClassVar


H = TypeVar('H', bound=Hashable)
T = TypeVar('T', bound=Enum)
@dataclass(frozen=True)
class Adapter(Generic[T, H]):
    TokenType: Type[T]  # The Enum type representing token types in the backend
    default_token_type: T  # Default token type to use when none is specified
    lex: Callable[[str, Any], List[H]]  # Function to lex text into tokens
    parse_expr: Callable[[List[H], str], List[Any]]  # Function to parse tokens into expressions


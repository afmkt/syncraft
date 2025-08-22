

from __future__ import annotations
import re
from typing import (
    Optional, Any, TypeVar, Tuple, runtime_checkable, 
    Protocol, Generic, Callable, Union, cast
)
from syncraft.algebra import (
    OrResult,ThenResult, ManyResult, ThenKind,NamedResult, StructuralResult
)
from dataclasses import dataclass, replace, is_dataclass, asdict
from enum import Enum
from functools import cached_property

@runtime_checkable
class TokenProtocol(Protocol):
    @property
    def token_type(self) -> Enum: ...
    @property
    def text(self) -> str: ...
    

@dataclass(frozen=True)
class Token:
    token_type: Enum
    text: str
    def __str__(self) -> str:
        return f"{self.token_type.name}({self.text})"
    
    def __repr__(self) -> str:
        return self.__str__()

    

@dataclass(frozen=True)
class TokenSpec:
    token_type: Optional[Enum] = None
    text: Optional[str] = None
    case_sensitive: bool = False
    regex: Optional[re.Pattern[str]] = None
        
    def is_valid(self, token: TokenProtocol) -> bool:
        type_match = self.token_type is None or token.token_type == self.token_type
        value_match = self.text is None or (token.text.strip() == self.text.strip() if self.case_sensitive else 
                                                    token.text.strip().upper() == self.text.strip().upper())
        value_match = value_match or (self.regex is not None and self.regex.fullmatch(token.text) is not None)
        return type_match and value_match




T = TypeVar('T', bound=TokenProtocol)  


ParseResult = Union[
    ThenResult['ParseResult[T]', 'ParseResult[T]'], 
    NamedResult['ParseResult[T]'],
    ManyResult['ParseResult[T]'],
    OrResult['ParseResult[T]'],
    T,
]
@dataclass(frozen=True)
class AST(Generic[T]):
    focus: ParseResult[T]
    pruned: bool = False
    parent: Optional[AST[T]] = None

    def bimap(self)->Tuple[Any, Callable[[Any], AST[T]]]:
        if isinstance(self.focus, StructuralResult):
            b = self.focus.bimap() 
            s, v = b.forward(None, self.focus)
            def inverse(data: Any) -> AST[T]:
                s1, v1 = b.inverse(None, data)
                return replace(self, focus=v1)
            return v, inverse
        else:
            return self.focus, lambda x: replace(self, focus=x)
        
    def wrapper(self)-> Callable[[Any], Any]:
        if isinstance(self.focus, NamedResult):
            focus = cast(NamedResult[Any], self.focus)
            return lambda x: NamedResult(name = focus.name, value = x)
        else:
            return lambda x: x
        
    def is_named(self) -> bool: 
        return isinstance(self.focus, NamedResult)

    def left(self) -> Optional[AST[T]]:
        match self.focus:
            case ThenResult(left=left, kind=kind):
                return replace(self, focus=left, parent=self, pruned = self.pruned or kind == ThenKind.RIGHT)
            case _:
                raise TypeError(f"Invalid focus type({self.focus}) for left traversal")

    def right(self) -> Optional[AST[T]]:
        match self.focus:
            case ThenResult(right=right, kind=kind):
                return replace(self, focus=right, parent=self, pruned = self.pruned or kind == ThenKind.LEFT)
            case _:
                raise TypeError(f"Invalid focus type({self.focus}) for right traversal")


    def down(self, index: int) -> Optional[AST[T]]:
        match self.focus:
            case ManyResult(value=children):
                if 0 <= index < len(children):
                    return replace(self, focus=children[index], parent=self, pruned=self.pruned)
                else:
                    raise IndexError(f"Index {index} out of bounds for ManyResult with {len(children)} children")
            case OrResult(value=value):
                if index == 0:
                    return replace(self, focus=value, parent=self, pruned=self.pruned)
                else:
                    raise IndexError(f"Index {index} out of bounds for OrResult")
            case NamedResult(value=value):
                return replace(self, focus=value, parent=self, pruned=self.pruned)
            case _:
                raise TypeError(f"Invalid focus type({self.focus}) for down traversal")

    def how_many(self)->int:
        focus = self.focus.value if isinstance(self.focus, NamedResult) else self.focus
        match focus:
            case ManyResult(value=children):
                return len(children)
            case _:
                raise TypeError(f"Invalid focus type({self.focus}) for how_many")
            
    

    @cached_property
    def root(self) -> AST[T]:
        while self.parent is not None:
            self = self.parent  
        return self
    

from __future__ import annotations
from typing import (
    Optional, List, Any, TypeVar, Generic, Callable, Tuple, cast, Mapping,
    Type, Generator, Union, Hashable, TYPE_CHECKING
)
from syncraft.ast import AST, Ignore
from dataclasses import dataclass, replace, field
from syncraft.ast import ThenKind, Lazy, Then, Choice, Many, ChoiceKind, SyncraftError
from syncraft.cache import Cache, LeftRecursionError, Right, Left, Incomplete, Either
from syncraft.constraint import Bindable
if TYPE_CHECKING:
    from syncraft.syntax import Syntax


@dataclass(frozen=True)
class Error:
    this: Optional[Any] = None    
    message: Optional[str] = None
    error: Optional[Any] = None    
    state: Optional[Any] = None
    committed: bool = field(default=False)
    previous: Optional[Error] = field(default=None)
    
    def push(self, 
            *,
            this: Optional[Any] = None, 
            message: Optional[str] = None,
            error: Optional[Any] = None, 
            state: Optional[Any] = None) -> Error:
        new = Error(
            this=this,
            error=error,
            message=message,
            state=state
        )
        return replace(new, previous=self)
    
    def to_list(self)->List[Error]:
        lst = []
        current: Optional[Error] = self
        while current is not None:
            lst.append(current)
            current = current.previous
        return lst
    @property
    def deepest(self) -> Error:
        current: Error = self
        while current.previous is not None:
            current = current.previous
        return current

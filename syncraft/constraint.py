from __future__ import annotations
from typing import (
    Callable, Any, Self, 
    Protocol, runtime_checkable
)
from dataclasses import dataclass

from syncraft.utils import FrozenDict

    
@dataclass(frozen=True, slots=True)
class Binding:
    bindings : FrozenDict[str, Any] = FrozenDict()
    
    def bind(self, name: str, node: Any) -> Binding:
        return Binding(bindings=self.bindings.set(name, node))



@runtime_checkable
class Bindable(Protocol):
    @property
    def cache_key(self) -> int: ...

    @property
    def all_bindings(self) -> FrozenDict[str, Any]: ...

    def unused_cache_key(self) -> int: ...

    def map(self, f: Callable[[Any], Any])->Self: ...
    
    def bind(self, name: str, node:Any)->Self: ...
    
    def get(self, name: str) -> Any: ...

    def enter(self) -> Self: ...
    
    def leave(self) -> Self: ...
    
    @property
    def ended(self) -> bool: ...

    def str_input(self, ul: bool) -> str: ...

        


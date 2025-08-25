from __future__ import annotations

from typing import (
    Optional, Any, TypeVar, Generic
)
from syncraft.algebra import StructuralResult, NamedResult
from dataclasses import dataclass, field, replace
from functools import reduce




A = TypeVar('A')  # Result type

@dataclass(frozen=True)
class Variable(Generic[A]):

    def __init__(self, name: Optional[str] = None):
        self.name = name
        self.initialized = False
        self._value = None
    def __call__(self, a: Any) -> Any:
        if self.initialized:
            if self._value != a:
                raise ValueError(f"Variable {self.name or ''} is already initialized")
            else:
                return a
        elif self.name is not None and isinstance(a, NamedResult):
            if a.name == self.name:
                self._value = a.value
                self.initialized = True
        else:
            self._value = a
            self.initialized = True
        return a
    @property
    def value(self) -> A:
        if self.initialized is False or self._value is None:
            raise ValueError(f"Variable {self.name or ''} is not initialized")
        return self._value

from __future__ import annotations


from typing import  Any, TYPE_CHECKING, TypeVar
if TYPE_CHECKING:
    from syncraft.cache import Rule
from syncraft.constraint import Bindable


S = TypeVar('S', bound=Bindable)

class Tracer:
    def trace(self, 
            *, 
            rule: Any, 
            parent: Any | None, 
            start_time: int,
            end_time: int,
            start: S,
            end: S | None,
            result: Any | None,
            consumed: int | None
        ) -> None:
        pass

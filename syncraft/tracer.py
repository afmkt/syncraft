from __future__ import annotations
from typing import Any, overload, Optional, Iterator, Callable, Protocol, Literal
from dataclasses import dataclass, field
from contextlib import contextmanager
import contextvars
import time
from syncraft.bimap import Bindable


Site = Literal[
    'cache-hit', 
    'cache-inprogress', 
    'recursion-detected',
    'parsing-normal',
    'group-resolution', 
    'agenda-reprocess'
]




@dataclass
class ParseNode:
    """A node in the reconstructed parse tree."""
    rule: Any
    location: str | None
    site: Site
    cache_key: Any
    input: Bindable
    push_time_ns: int
    pop_time_ns: int | None = None
    parent_id: int | None = field(default=None, repr=False)
    result: Any = None
    children: list[ParseNode] = field(default_factory=list)
    
    def duration_ns(self) -> int | None:
        """Return parse duration in nanoseconds, or None if not yet popped."""
        if self.pop_time_ns is None:
            return None
        return self.pop_time_ns - self.push_time_ns


@dataclass(frozen=True, slots=True)
class TraceEvent:
    tracer: Tracer | None
    timestamp_ns: int


class EventProtocol(Protocol):
    def pop(self, *args, **kwargs) -> Any: ...
@dataclass(frozen=True, slots=True)
class PushEvent(TraceEvent, EventProtocol):
    rule: Any
    parent: Any | None
    state: Bindable
    site: Site
    
    @overload
    def pop(self, result: Any, error: None, state: Bindable) -> PopEvent: ...
    @overload
    def pop(self, result: None, error: Any, state: None) -> PopEvent: ...

    def pop(self, result: Any | None = None, error: Any | None = None, state: Bindable | None = None) -> PopEvent:
        ret = PopEvent(
            tracer=self.tracer,
            timestamp_ns=time.perf_counter_ns(),
            push_event=self,
            result=result,
            error=error,
            state=state
        )
        if self.tracer and self.tracer.on_pop_f:
            self.tracer.on_pop_f(ret)
        return ret  



@dataclass(frozen=True, slots=True)
class PopEvent(TraceEvent):
    push_event: PushEvent
    result: Any | None
    error: Any | None
    state: Bindable | None
    


class Tracer:
    def __enter__(self) -> Tracer:
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        pass

    def __init__(self, url: None | str = None) -> None:
        self.on_push_f: Optional[Callable[[PushEvent], None]] = None
        self.on_pop_f: Optional[Callable[[PopEvent], None]] = None

    def on_push(self, f: Callable[[PushEvent], None]) -> Tracer:
        self.on_push_f = f
        return self
    
    def on_pop(self, f: Callable[[PopEvent], None]) -> Tracer:
        self.on_pop_f = f
        return self

    def push(self, 
             rule: Any, 
             parent: Any | None,
             state: Bindable,
             site: Site) -> PushEvent: 
        ret = PushEvent(
            tracer=self,
            timestamp_ns=time.perf_counter_ns(),
            rule=rule,
            parent=parent,
            state=state,
            site=site,
        )
        if self.on_push_f:
            self.on_push_f(ret)
        return ret
        
        

class Dummy(EventProtocol):
    def pop(self, *args, **kwargs) -> None:
        pass

dummy = Dummy()

def trace_push(rule: Any, parent: Any | None, state: Bindable, site: Site) -> EventProtocol:
    tracer = _CURRENT_TRACER.get()
    if tracer is None:
        return dummy
    return tracer.push(rule=rule, parent=parent, state=state, site=site)
    


_CURRENT_TRACER: contextvars.ContextVar[Optional[Tracer]] = contextvars.ContextVar(
    "syncraft_current_tracer",
    default=None,
)


@contextmanager
def tracer() -> Iterator[Tracer]:
    tracer = Tracer()
    token = _CURRENT_TRACER.set(tracer)
    try:
        yield tracer
    finally:
        _CURRENT_TRACER.reset(token)
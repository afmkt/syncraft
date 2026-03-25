from __future__ import annotations
from typing import Any, overload, Optional, Callable, Protocol, Literal
from dataclasses import dataclass, field

from contextvars import ContextVar, Token
import time
from syncraft.bimap import Bindable
from syncraft.ast import SyncraftError

Site = Literal[
    'cache-hit', 
    'cache-inprogress', 
    'recursion-detected',
    'parsing-normal',
    'group-resolution', 
    'agenda-reprocess'
]

@dataclass(frozen=True, slots=True)
class TraceEvent:
    tracer: Tracer | None
    timestamp_ns: int




class EventProtocol(Protocol):
    def pop(self, *args, **kwargs) -> None: ...
@dataclass(frozen=True, slots=True)
class PushEvent(TraceEvent, EventProtocol):
    rule: Any
    parent: Any | None
    state: Bindable
    site: Site
    
    @overload
    def pop(self, result: Any, error: None, state: Bindable) -> None: ...
    @overload
    def pop(self, result: None, error: Any, state: None) -> None: ...

    def pop(self, result: Any | None = None, error: Any | None = None, state: Bindable | None = None) -> None:
        ret = PopEvent(
            tracer=self.tracer,
            timestamp_ns=time.perf_counter_ns(),
            push_event=self,
            result=result,
            error=error,
            state=state
        )
        if self.tracer:
            self.tracer.close(ret)
        



@dataclass(frozen=True, slots=True)
class PopEvent(TraceEvent):
    push_event: PushEvent
    result: Any | None
    error: Any | None
    state: Bindable | None
    



@dataclass(slots=True)
class Node:
    rule: Any
    parent: Optional[Node]
    push_event: PushEvent
    pop_event: Optional[PopEvent] = None
    children: list[Node] = field(default_factory=list)

    @property
    def site(self) -> Site:
        return self.push_event.site
    
    @property
    def state_in(self) -> Bindable:
        return self.push_event.state
    
    @property
    def state_out(self) -> Bindable | None:
        return self.pop_event.state if self.pop_event else None
    
    @property
    def duration_ns(self) -> Optional[int]:
        if self.pop_event:
            return self.pop_event.timestamp_ns - self.push_event.timestamp_ns
        return None
    
    @property
    def error(self) -> Any | None:
        return self.pop_event.error if self.pop_event else None
    
    @property
    def result(self) -> Any | None:
        return self.pop_event.result if self.pop_event else None
    
    @property
    def success(self) -> Optional[bool]:
        return self.state_out is not None

    @property
    def finished(self) -> bool:
        return self.pop_event is not None
    



_CURRENT_TRACER: ContextVar[Optional[Tracer]] = ContextVar(
    "syncraft_current_tracer",
    default=None,
)


class Tracer:
    def __enter__(self) -> Tracer:
        self._token = _CURRENT_TRACER.set(self)
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._token is not None:
            _CURRENT_TRACER.reset(self._token)
            self._token = None # type: ignore

    def __init__(self, url: None | str = None) -> None:
        self.on_push_f: Optional[Callable[[PushEvent], None]] = None
        self.on_pop_f: Optional[Callable[[PopEvent], None]] = None
        self._token: Optional[Token[Optional[Tracer]]] = None # type: ignore
        self.root: Optional[Node] = None
        self.top: Optional[Node] = None

    def open(self, event: PushEvent) -> None:
        node = Node(
            rule=event.rule,
            parent=self.top,
            push_event=event,
        )
        if self.top is not None:
            self.top.children.append(node)
        else:
            self.root = node
        self.top = node
        if self.on_push_f:
            # We want to be robust against errors in the callback, so we catch and ignore any exceptions it raises.
            try:
                self.on_push_f(event)
            except Exception:
                pass

    def close(self, event: PopEvent) -> None:
        if self.top is None:
            raise SyncraftError("No open node to close", offender=event)
        if self.top.push_event is not event.push_event:
            raise SyncraftError("Mismatched push/pop events", offender=event)
        self.top.pop_event = event
        self.top = self.top.parent
        if self.on_pop_f:
            # We want to be robust against errors in the callback, so we catch and ignore any exceptions it raises.
            try:
                self.on_pop_f(event)
            except Exception:
                pass

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
        self.open(ret)
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
    


class TracePath:
    def __init__(self, segments: list[Any]) -> None:
        self.segments = segments or []
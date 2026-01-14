from __future__ import annotations
from typing import  Any, Literal
from dataclasses import dataclass, field
import time
from syncraft.constraint import Bindable
from syncraft.ast import AST


@dataclass
class ParseNode:
    """A node in the reconstructed parse tree."""
    rule: Any
    location: str | None
    cache_key: Any
    input_snapshot: str
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



@dataclass
class TracerEvent:
    id: int
    timestamp_ns: int
    rule: Any
    parent: Any | None
    cache_key: int | None
    input_snapshot: str | None
    result: Any | None
    which: int | None
    kind: Literal['push', 'pop']

class Tracer:
    def __enter__(self) -> Tracer:
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        pass

    def __init__(self, url: None | str = None) -> None:
        self.log: list[Any] = []

    def push(self, 
             rule: Any, 
             parent: Any | None,
             state: Bindable) -> int: 
        self.log.append(TracerEvent(
            id=len(self.log),
            timestamp_ns=time.perf_counter_ns(),
            rule=rule,
            parent=parent,
            cache_key=state.cache_key,
            input_snapshot=state.str_input(ul=False),
            result=None,
            which=None,
            kind='push'
        ))
        return len(self.log) - 1
        
    
    def pop(self,
            which: int,
            state: Bindable | None,
            result: Any) -> None:
        if hasattr(result, 'compact') and hasattr(result, '__class__') and result.__class__.__name__ == 'Error':
            result = result.compact
            
        self.log.append(TracerEvent(
            id=len(self.log),
            timestamp_ns=time.perf_counter_ns(),
            rule=None,
            parent=None,
            cache_key=state.cache_key if state is not None else None,
            input_snapshot=state.str_input(ul=False) if state is not None else None,
            result=result,
            which=which,
            kind='pop'
        ))
        
    def traces(self) -> list[Any]:
        return self.log
    
    def tree(self) -> list[ParseNode]:
        """
        Reconstruct the parse tree from trace events using a parse stack.
        
        Handles recursive/looping rules correctly by tracking the active
        parse context at each moment via push/pop events.
        
        Returns a list of root nodes (nodes with no parent).
        Each node contains children, forming a tree structure.
        """
        
        nodes: dict[int, ParseNode] = {}  # log_index (from push return) -> ParseNode
        stack: list[int] = []  # Stack of log indices for active (unpoped) nodes
        
        for i, event in enumerate(self.log):
            if event.kind == 'push':
                parent_idx = stack[-1] if stack else None
                node = ParseNode(
                    rule=str(event.rule),
                    location=event.rule.location if hasattr(event.rule, 'location') else None,
                    parent_id=parent_idx,  # Store parent's log index, not id(parent)
                    cache_key=event.cache_key,
                    input_snapshot=event.input_snapshot,
                    push_time_ns=event.timestamp_ns,
                )
                nodes[i] = node
                stack.append(i)  # Push this node onto the parse stack
                # assert node.location is not None, f"Rule must have a location, {repr(event.rule)}"
                
            elif event.kind == 'pop' and event.which is not None:
                if event.which in nodes:
                    nodes[event.which].pop_time_ns = event.timestamp_ns
                    nodes[event.which].result = event.result
                else:
                    raise ValueError(f"Pop event refers to unknown push id {event.which}")
                # Pop from stack - remove the most recent occurrence of 'which'
                if event.which in stack:
                    stack.remove(event.which)
        
        # Build parent-child relationships using parent_id (which is now a log index)
        roots: list[ParseNode] = []
        for node in nodes.values():
            if node.parent_id is None:
                roots.append(node)
            else:
                parent = nodes.get(node.parent_id)
                if parent:
                    parent.children.append(node)
        
        return roots

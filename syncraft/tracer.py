"""
# Bidirectional Parser Debugging System

## Overview

This module provides a declarative, stream-based debugging system for a
bidirectional parser combinator library. It allows grammar authors to
observe, filter, and react to parsing or generation events using a
path-based query DSL inspired by XPath.

The system operates on a stream of parsing events and incrementally
constructs a partial tree based on user-defined queries, without
materializing the full parse tree.

## Core Concepts

1. Event Model

---

Parsing or generation emits a linear stream of events:

* PushEvent: emitted when entering a grammar rule
* PopEvent: emitted when exiting a grammar rule

A PushEvent/PopEvent pair represents a Node. Only completed Nodes
(i.e., at PopEvent) are exposed to the debugging system.

Backtracking is handled by the main parser and is not visible here.
All Nodes (both success and failure) are final and processed once.

2. Node

---

A Node represents a completed evaluation of a grammar rule.

Each Node provides:

* rule: the grammar rule (Syntax object)
* success(): whether the rule succeeded
* parent: reference to the parent Node
* (optional) children, span, text, etc.

Nodes form a conceptual tree via parent links, but the debugging system
only materializes relevant portions of this tree.

3. Streaming Reducer

---

The system processes events in a single pass and maintains:

* an active stack of Nodes (root → current)
* a partial result tree containing only matched Nodes and their ancestors

The reducer incrementally builds the result tree by including:

* Nodes that match a query
* all their ancestors up to the root (structural closure)

4. Query DSL

---

Queries are defined using a Path, optional Predicate, and Action:

```
Path(...).where(predicate).do(action)
```

## 4.1 Path

A Path is an expression of grammar rules:

```
root / ... / A / ... / B
```

Semantics:

* The path is matched against the current stack (root → current node)
* Matching is defined as an ordered subsequence over the stack
* `...` matches any number of intermediate nodes
* All paths are implicitly anchored at the root

A path matches when all its segments appear in order in the stack.

## 4.2 Predicate

A Predicate is a function applied to the current Node:

```
.where(lambda node: node.success())
```

* Evaluated only at PopEvent (i.e., on completed Nodes)
* Filters which matched Nodes trigger actions

## 4.3 Action

An Action is executed when a Node satisfies both Path and Predicate:

```
.do(lambda node: ...)
```

* Triggered only at PopEvent
* The input is the current Node (the terminal segment of the Path)
* Actions are side-effect only (must not modify parser state)

Examples:

* print(node)
* pause execution (e.g., via input)
* logging or assertions

## Execution Semantics

For each PopEvent of a Node `N` with current stack `S`:

```
if path_matches(S) and predicate(N):
    action(N)
```

Where:

* `S` is the stack from root to `N`
* `path_matches` checks whether the Path is an ordered subsequence of `S`

If a Node matches:

* It is included in the result tree
* All its ancestors are also included (if not already present)

## Design Principles

* Streaming: single-pass processing, no full tree construction required
* Deterministic: no backtracking or event rollback in the debug layer
* Post-order: only completed Nodes are visible
* Minimal API: actions operate on a single Node
* Structural context: ancestor relationships preserved via parent links
* Declarative: users specify *what* to observe, not *how*

## Tradeoffs

* Only the terminal Node of a matched Path is passed to actions
* Ancestor Nodes must be accessed via `node.parent`
* If multiple matching ancestors exist, users must resolve them explicitly
* Path matching is evaluated at each PopEvent (O(depth))

## Intended Use Cases

* Debugging rule failures and successes
* Inspecting specific patterns in grammar execution
* Setting breakpoints at structural positions
* Understanding parse behavior without full tree inspection

This system provides a structured alternative to ad-hoc logging,
enabling precise and composable debugging of parser behavior.

"""
from __future__ import annotations
from typing import Any, overload, Optional, Callable, Protocol, Literal, Tuple, TypeVar, Generic, List
from types import EllipsisType
from dataclasses import dataclass, field, replace

from contextvars import ContextVar, Token
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

@dataclass(frozen=True, slots=True)
class TraceEvent:
    tracer: Tracer | None
    timestamp_ns: int




class EventProtocol(Protocol):
    def pop(self, *args, **kwargs) -> None: ...
@dataclass(frozen=True, slots=True)
class PushEvent(TraceEvent, EventProtocol):
    rule: Any
    state: Bindable
    site: Site
    node: Node | None
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
        self.stack: List[Node] = []

    def open(self, event: PushEvent) -> None:
        if self.on_push_f:
            # We want to be robust against errors in the callback, so we catch and ignore any exceptions it raises.
            try:
                self.on_push_f(event)
                assert event.node is not None, "PushEvent must have an associated Node"
                self.stack.append(event.node) 
            except Exception:
                pass

    def close(self, event: PopEvent) -> None:
        if self.on_pop_f:
            # We want to be robust against errors in the callback, so we catch and ignore any exceptions it raises.
            try:
                self.stack.pop()
                self.on_pop_f(event)
            except Exception:
                pass

    def push(self, 
             rule: Any, 
             state: Bindable,
             site: Site) -> PushEvent: 
        ret = PushEvent(
            tracer=self,
            timestamp_ns=time.perf_counter_ns(),
            rule=rule,
            state=state,
            site=site,
            node = None
        )
        ret = replace(ret, 
                      node = Node(
                            push_event=ret,
                            parent=self.stack[-1] if self.stack else None
                    ))
        self.open(ret)
        return ret
        
        

class Dummy(EventProtocol):
    def pop(self, *args, **kwargs) -> None:
        pass

dummy = Dummy()

def trace_push(rule: Any, state: Bindable, site: Site) -> EventProtocol:
    tracer = _CURRENT_TRACER.get()
    if tracer is None:
        return dummy
    return tracer.push(rule=rule, state=state, site=site)
    



@dataclass(slots=True)
class Node:
    """
    A Node represents a completed evaluation of a grammar rule, corresponding to a PushEvent/PopEvent pair.
    rule: the grammar rule (Syntax object)
    push_event: the PushEvent that initiated this Node (e.g., entering a rule) 
    pop_event: the PopEvent that completed this Node (optional, may be None if the Node is still active)
    ancestors: a list of ancestor Nodes from the root to the parent (ordered from root to parent)
    children: a list of child Nodes (optional, may be empty if no children or if children are not tracked)
    pinned: a boolean flag indicating whether this Node is pinned (i.e., should be kept in the result tree)
            Call pin() to mark this Node as pinned, which will ensure it is included in the result tree, 
            otherwise it will be discarded after the evaluation.
    """
    
    push_event: PushEvent
    pop_event: Optional[PopEvent] = None
    parent: Optional[Node] = None
    children: list[Node] = field(default_factory=list)
    pinned: bool = False 

    @property
    def ancestors(self) -> list[Node]:
        return self.push_event.tracer.stack if self.push_event.tracer else []


    @property
    def rule(self) -> Any:
        return self.push_event.rule

    def pin(self) -> None:
        self.pinned = True


    def close(self) -> None:
        if self.pinned or self.children:
            return
        parent = self.parent
        if parent:
            parent.children.remove(self)
                

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
    
@dataclass(slots=True)
class Tree:
    root: Optional[Node] = None
    top: Optional[Node] = None


Reducer = Callable[[Tree, Node], Tree]
Transducer = Callable[[Reducer], Reducer]



def map(f: Callable[[Node], Any]) -> Transducer:
    """
    Create a transducer that applies a function to each item before reducing it.
    Args:
    f: A function that takes an item and returns a transformed item.
    Returns:
    A transducer function that can be used to create a new reducer that applies the transformation before reducing.
    """
    def transducer(reducer: Reducer) -> Reducer:
        """
        Wrap the original reducer to apply the transformation function `f` to each item before reducing it.
        Args:
        reducer: The original reducer function that takes an accumulator and an item and returns a new accumulator.
        Returns:
        A new reducer function that applies the transformation function `f` to each item before reducing it
        """
        def wrapped(acc: Tree, item: Node) -> Tree:
            return reducer(acc, f(item))
        return wrapped
    return transducer

def filter(pred: Callable[[Node], bool]) -> Transducer:
    """
    Create a transducer that filters items based on a predicate function.
    
    Args:
        pred: A function that takes an item and returns True if the item should be kept, False otherwise.
        
    Returns:
        A transducer function that can be used to create a new reducer that only processes items that satisfy the predicate.
    """
    def transducer(reducer: Reducer) -> Reducer:
        """
        Wrap the original reducer to only apply it to items that satisfy the predicate function `pred`.
        Args:
            reducer: The original reducer function that takes an accumulator and an item and returns a new accumulator.
        Returns:
            A new reducer function that only applies the original reducer to items that satisfy the predicate function `
        """
        def wrapped(acc: Tree, item: Node) -> Any:
            if pred(item):
                return reducer(acc, item)
            return acc
        return wrapped
    return transducer


def compose(*transducers: Transducer) -> Transducer:
    """Compose multiple transducers into a single transducer that applies them in sequence."""
    def composed(reducer: Reducer) -> Reducer:
        for transducer in reversed(transducers):
            reducer = transducer(reducer)
        return reducer
    return composed




def only_pop()-> Transducer:
    return filter(lambda node: node.pop_event is not None)

def pop(evt: PopEvent | PushEvent) -> Node:
    if isinstance(evt, PushEvent):
        assert evt.node is not None, "PushEvent must have an associated Node"
        return evt.node
    elif isinstance(evt, PopEvent):
        assert evt.push_event.node is not None, "PopEvent's PushEvent must have an associated Node"
        return evt.push_event.node
    raise SyntaxError("Event must be either PushEvent or PopEvent")



def path(*segments: Any | EllipsisType) -> Callable[[Node], bool]:
    """Create a predicate function that checks if a Node matches a given path of grammar rules.
    Args:
        *segments: A variable number of grammar rule segments that define the path to match.
                   Each segment can be a specific rule or Ellipsis (`...`) to match any number of intermediate nodes.
    Returns:    
        A predicate function that takes a Node and returns True if the Node matches the specified path, False otherwise.
    """
    return lambda node: True

def where(p: Callable[[Node], bool] = lambda _: True, 
          **field: Any | Callable[[Any], bool]) -> Callable[[Node], bool]:
    """
    Create a predicate function that checks if a Node matches the specified field values or conditions.
    Args:
        p: An optional predicate function that takes a Node. Used for complex conditions that can't be expressed as simple field checks. 
           Defaults to a function that always returns True.
        **field: Keyword arguments where the key is the field name and the value is either a specific value
                 to match or a callable that takes the field value and returns True if it matches.
    Returns:
        A predicate function that takes a Node and returns True if the Node matches all specified field conditions, False otherwise.
    """
    def predicate(node: Node) -> bool:
        if not p(node):
            return False
        for key, value in field.items():
            node_value = getattr(node, key)
            if callable(value):
                if not value(node_value):
                    return False
            else:
                if node_value != value:
                    return False
        return True
    return predicate

def action(act: Callable[[Node], None]) -> Reducer:
    """
    Create an action function that executes a given callable on a Node.
    Args:
        act: A callable that takes a Node and performs some side effect (e.g., printing, logging, etc.).

    Returns:
        A reducer function that takes a Tree and a Node, executes the provided action on the Node, and returns the Tree.
    """
    def reducer(tree: Tree, node: Node) -> Tree:
        act(node)
        return tree
    return reducer



N = TypeVar('N')
T = TypeVar('T')
class State(Protocol, Generic[T, N]): # type: ignore
    def __call__(self, tree: T, node: N) -> Tuple[T, State[T, N]]: ...


Machine = Callable[[State[T, N]], State[T, N]]


def fail(tree: T, node: N) -> Tuple[T, State[T, N]]:
    return tree, fail

def success(tree: T, node: N) -> Tuple[T, State[T, N]]:
    return tree, success

def segment(pred: Callable[[N], bool]) -> Machine:
    def machine(k: State[T, N]) -> State[T, N]:
        def state(tree: T, node: N) -> Tuple[T, State[T, N]]:
            if pred(node):
                return tree, k
            return tree, fail
        return state
    return machine

def seq(m1: Machine, m2: Machine) -> Machine:
    def machine(k: State[T, N]) -> State[T, N]:
        return m1(m2(k))
    return machine


@dataclass(frozen=True, slots=True)
class ParallelState(State[T, N]):
    branches: Tuple[Tuple[T, State[T, N]], ...] = field(default_factory=tuple)

    def __call__(self, tree: T, node: N) -> Tuple[T, State[T, N]]:
        new_branches = []
        for t, s in self.branches:
            new_t, new_s = s(tree, node)
            if new_s is not fail:
                new_branches.append((new_t, new_s))
        if not new_branches:
            return tree, fail
        elif len(new_branches) == 1:
            return new_branches[0]
        return tree, ParallelState(tuple(new_branches))


def alt(*m: Machine, first_win: bool = False) -> Machine:
    def machine(k: State[T, N]) -> State[T, N]:
        def state(tree: T, node: N) -> Tuple[T, State[T, N]]:
            if first_win:
                for mi in m:
                    t, s = mi(k)(tree, node)
                    if s is not fail:
                        return t, s
                return tree, fail
            else:
                branches = []
                for mi in m:
                    t, s = mi(k)(tree, node)
                    if s is not fail:
                        branches.append((t, s))
                if not branches:
                    return tree, fail
                return tree, ParallelState(tuple(branches))
        return state
    return machine


def many(m: Machine, at_least: int, at_most:int | None = None) -> Machine:
    def machine(k: State[T, N]) -> State[T, N]:
        def state_builder(count: int) -> State[T, N]:
            def state(tree: T, node: N) -> Tuple[T, State[T, N]]:
                if count >= at_least:
                    t_k, s_k = k(tree, node)
                    if s_k is not fail:
                        return t_k, s_k
                if at_most is None or count < at_most:
                    t_m, s_m = m(state_builder(count + 1))(tree, node)
                    if s_m is not fail:
                        return t_m, s_m
                return tree, fail
            return state
        return state_builder(0)
    return machine

def wildcard() -> Machine:
    def machine(k: State[T, N]) -> State[T, N]:
        def state(tree: T, node: N) -> Tuple[T, State[T, N]]:
            t, s = k(tree, node)
            if s is not fail:
                return t, s
            return tree, state
        return state
    return machine

def optional(m: Machine) -> Machine:
    return alt(m, lambda k: k)

def lazy(m: Callable[[], Machine]) -> Machine:
    def machine(k: State[T, N]) -> State[T, N]:
        _resolved = None
        def state(tree: T, node: N) -> Tuple[T, State[T, N]]:
            nonlocal _resolved
            if _resolved is None:
                _resolved = m()(k)
            return _resolved(tree, node)
        return state
    return machine

def peek(m: Machine) -> Machine:
    def machine(k: State[T, N]) -> State[T, N]:
        def state(tree: T, node: N) -> Tuple[T, State[T, N]]:
            t_m, s_m = m(success)(tree, node)
            if s_m is not fail:
                return k(tree, node)
            return tree, fail
        return state
    return machine

def capture(map: Callable[[T, N], T]) -> Machine:
    def machine(k: State[T, N]) -> State[T, N]:
        def state(tree: T, node: N) -> Tuple[T, State[T, N]]:
            new_tree = map(tree, node)
            return k(new_tree, node)
        return state
    return machine
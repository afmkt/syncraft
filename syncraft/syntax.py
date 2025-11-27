from __future__ import annotations

import keyword
import re
import math

from typing import (
    Optional, Any, TypeVar, Generic, Callable, Tuple, cast, Hashable,
    Type, List, Dict, Set, Iterator, ClassVar, Protocol, Generator, MutableMapping, TYPE_CHECKING
)
from dataclasses import dataclass, field, replace

if TYPE_CHECKING:
    from syncraft.vis import SVGVisualization
from syncraft.utils import file as get_file, line as get_line, func as get_func, FrozenDict, CallWith, ThreadLocalWeakValueDict, MISSING
from syncraft.algebra import Algebra, Either, Left, Right, SYNCRAFT_CONFIG_KEY, Error
from syncraft.cache import Cache, Incomplete
from syncraft.constraint import Bindable, Constraint

from syncraft.ast import Then, ThenKind, Marked, OrElse, Many, Nothing, Collect, E, Collector, SyncraftError, Seq, Choice, AST

from syncraft.input import StreamCursor, PayloadKind
from syncraft.fa import Builder
from syncraft.token import TokenSpec, TokenSpecBase
from functools import partial
import hashlib




def valid_name(name: str) -> bool:
    return (name.isidentifier() 
            and not keyword.iskeyword(name)
            and not (name.startswith('__') and name.endswith('__')))

A = TypeVar('A')  # Result type
B = TypeVar('B')  # Result type for mapping
C = TypeVar('C')  # Result type for else branch
D = TypeVar('D')  # Result type for else branch
S = TypeVar('S', bound=Bindable)  # State type

N = TypeVar('N', bound=Hashable)  # Node type for graphs
@dataclass(frozen=True, slots=True)
class Graph(Generic[N]):
    edges: FrozenDict[N, frozenset[N]]
    root: N

    @classmethod
    def from_edges(cls, root: N, *edges: Tuple[N, N]) -> Graph[N]:
        e: Dict[N, Set[N]] = {}
        for parent, child in edges:
            e.setdefault(parent, set()).add(child)
            e.setdefault(child, set())
        return cls(edges=FrozenDict({k: frozenset(v) for k, v in e.items()}), root=root)
    
    @property
    def nodes(self) -> Set[N]:
        return set(self.edges.keys())

    @property
    def str_node(self) -> str:
        return "\n".join(sorted(str(node) for node in self.nodes))
    @property
    def str_edge(self) -> str:
        lines = []
        for parent, children in self.edges.items():
            for child in children:
                lines.append(f"{parent} -> {child}")
        return "\n".join(sorted(lines))

    def str_tree(self, root: N) -> str:
        visited: Set[N] = set()
        output_lines: List[str] = [self.__class__.__name__]
        def node_str(node: N) -> str:
            prefix = f"{id(node)}:"
            prefix = ""
            if isinstance(node, ThenSpec):
                return f"{prefix}{node}:ThenSpec({node.kind})"
            elif isinstance(node, OrElseSpec):
                return f"{prefix}{node}:OrElseSpec(|)"
            else:
                return f"{prefix}{node}"

        def _format_node(node: N, prefix: str, is_last_sibling: bool):
            if node in visited:
                output_lines.append(f"{prefix}└── [CYCLE] {node}")
                return
            visited.add(node)
            connector = "└── " if is_last_sibling else "├── "
            node_display = f"ROOT {node_str(node)}" if node == self.root else f"{node_str(node)}"
            output_lines.append(f"{prefix}{connector}{node_display}")
            new_prefix = prefix + ("    " if is_last_sibling else "│   ")
            neighbors = sorted(list(self.edges.get(node, frozenset())), key=lambda x: str(x))
            # neighbors = list(self.edges.get(node, frozenset()))
            for i, neighbor in enumerate(neighbors):
                neighbor_is_last = (i == len(neighbors) - 1)
                _format_node(neighbor, new_prefix, neighbor_is_last)
        _format_node(root, "", True)
        return "\n".join(output_lines).strip()
    
    def __str__(self) -> str:
        return self.str_tree(self.root)
        
@dataclass(frozen=True, slots=True)
class SyntaxSpec:
    name: Optional[str] = field(compare=False, hash=False)
    file: Optional[str] = field(compare=False, hash=False) 
    line: Optional[int] = field(compare=False, hash=False)
    func: Optional[str] = field(compare=False, hash=False)
    @property
    def location(self) -> Optional[str]:
        if self.file:
            return f"{self.file}:{self.line or '?'}"
        return None
    
    def syntax(self, cls: type[Syntax], cache: MutableMapping[SyntaxSpec, Syntax])-> Syntax[Any, Any]:
        if self in cache:
            return cache[self]
        raise NotImplementedError
        
    def named(self, *, name: None | str, file: None | str, line: None | int, func: None | str, _location:bool=True) -> SyntaxSpec:
        if _location:
            return replace(self, name=name, file=file, line=line, func=func)
        else:
            return replace(self, name=name)

    def format(self, tmplt: str, *args: Any, **kwargs: Any) -> str:
        tmp = {}
        if self.name:
            tmp['name'] = self.name
        if self.file:
            tmp['file'] = self.file
        if self.line:
            tmp['line'] = str(self.line)
        if self.func:
            tmp['func'] = self.func
        return tmplt.format(*args, **{**tmp, **kwargs})

    def _children(self, *, lazy_cache: MutableMapping[int, "SyntaxSpec"]) -> Tuple["SyntaxSpec", ...]:
        return ()

    @property    
    def complexity(self) -> float:
        return 0
    
    def walk(self, *, max_depth: Optional[int] = None) -> Iterator[Tuple[int, "SyntaxSpec"]]:
        lazy_cache: Dict[int, SyntaxSpec] = {}
        visited: Set[SyntaxSpec] = set()
        stack: List[Tuple[int, SyntaxSpec]] = [(0, self)]

        while stack:
            depth, node = stack.pop()
            if max_depth is not None and depth > max_depth:
                continue

            if node in visited:
                continue
            visited.add(node)

            yield depth, node

            for child in reversed(node._children(lazy_cache=lazy_cache)):
                stack.append((depth + 1, child))

    def graph(
        self,
        *,
        max_depth: Optional[int] = None,
    ) -> Graph["SyntaxSpec"]:
        """
        Build a list of edges representing the syntax graph.
        Each edge is a tuple (parent, child).
        """
        lazy_cache: Dict[int, SyntaxSpec] = {}
        edges: List[Tuple[SyntaxSpec, SyntaxSpec]] = []
        seen: Set[Tuple[SyntaxSpec, SyntaxSpec]] = set()

        for _depth, node in self.walk(max_depth=max_depth):
            for child in node._children(lazy_cache=lazy_cache):
                key = (node, child)
                if key in seen:
                    continue
                seen.add(key)
                edges.append((node, child))
        return Graph.from_edges(self, *edges)
        
    

@dataclass(frozen=True, slots=True)
class LazySpec(SyntaxSpec):
    lazy_state: LazyState[Any, Any]

    def syntax(self, cls: type[Syntax], cache: MutableMapping[SyntaxSpec, Syntax])-> Syntax[Any, Any]:
        if self in cache:
            return cache[self]
        ret = cls.lazy(self.lazy_state.thunk, flatten=self.lazy_state.flatten)._named(name=self.name, file=self.file, line=self.line, func=self.func)
        cache[self] = ret
        return ret

    def __str__(self) -> str:
        name = self.name or "lazy(...)"
        return self.format("{0}", name)
        
    @property    
    def complexity(self) -> float:
        return math.inf

    @property
    def inner_spec(self) -> SyntaxSpec:
        return self.lazy_state.cached.spec
        
    def _children(self, *, lazy_cache: MutableMapping[int, SyntaxSpec]) -> Tuple[SyntaxSpec, ...]:
        key = id(self)
        if key in lazy_cache:
            return (lazy_cache[key],)
        try:
            target = self.inner_spec
        except RecursionError:
            return ()
        lazy_cache[key] = target
        return (target,)
    
@dataclass(frozen=True, slots=True)
class MarkedSpec(SyntaxSpec):
    mname: str
    spec: SyntaxSpec
    def syntax(self, cls: type[Syntax], cache: MutableMapping[SyntaxSpec, Syntax])-> Syntax[Any, Any]:
        if self in cache:
            return cache[self]
        inner = self.spec.syntax(cls, cache=cache)
        ret = inner.mark(self.mname)
        ret = ret._named(name=self.name, file=self.file, line=self.line, func=self.func)
        cache[self] = ret
        return ret

    def __str__(self) -> str:
        if self.name:
            return self.format("{0}", self.name)
        else:
            return self.format("{spec}.mark({mname})", spec=str(self.spec), mname=self.mname)
        
    @property
    def complexity(self) -> float:
        return self.spec.complexity
    
    def _children(self,*, lazy_cache: MutableMapping[int, SyntaxSpec]) -> Tuple[SyntaxSpec, ...]:
        return (self.spec,)


@dataclass(frozen=True, slots=True)
class CollectSpec(SyntaxSpec):
    collector: Collector = field(compare=False, hash=False)
    id: Hashable
    spec: SyntaxSpec 
    kwargs: FrozenDict[str, Any] = field(compare=False, hash=False)

    def syntax(self, cls: type[Syntax], cache: MutableMapping[SyntaxSpec, Syntax])-> Syntax[Any, Any]:
        if self in cache:
            return cache[self]
        inner = self.spec.syntax(cls, cache=cache)
        ret = inner.to(self.collector, id=self.id, **self.kwargs)
        ret = ret._named(name=self.name, file=self.file, line=self.line, func=self.func)
        cache[self] = ret
        return ret

    def __str__(self) -> str:
        if self.name:
            return self.format("{0}", self.name)
        else:
            return self.format("{spec}.to{collector}", spec=str(self.spec), collector=str(self.collector))
        
    @property
    def complexity(self) -> float:
        return 1 + self.spec.complexity
    
    def _children(self,*, lazy_cache: MutableMapping[int, SyntaxSpec]) -> Tuple[SyntaxSpec, ...]:
        return (self.spec,)

@dataclass(frozen=True, slots=True)
class SeqSpec(SyntaxSpec):
    steps: Tuple[Tuple[SyntaxSpec, bool], ...]
    def syntax(self, cls: type[Syntax], cache: MutableMapping[SyntaxSpec, Syntax])-> Syntax[Any, Any]:
        if self in cache:
            return cache[self]
        steps = [(step.syntax(cls, cache=cache), keep) for step, keep in self.steps]
        ret = cls.seq(*steps)
        ret = ret._named(name=self.name, file=self.file, line=self.line, func=self.func)
        cache[self] = ret
        return ret

    def __str__(self) -> str:
        if self.name:
            return self.format("{0}", self.name)
        else:
            inner = " ".join(str(s[0]) for s in self.steps)
            return self.format("({steps})", steps=inner)
        
    @property
    def complexity(self) -> float:
        return 1 + sum(step.complexity for step, keep in self.steps)
    
    def _children(self,*, lazy_cache: MutableMapping[int, SyntaxSpec]) -> Tuple[SyntaxSpec, ...]:
        return tuple(step for step, keep in self.steps)
    
@dataclass(frozen=True, slots=True)
class ThenSpec(SyntaxSpec, Generic[A, B]):
    kind: ThenKind
    left: SyntaxSpec
    right: SyntaxSpec

    def syntax(self, cls: type[Syntax], cache: MutableMapping[SyntaxSpec, Syntax])-> Syntax[Any, Any]:
        if self in cache:
            return cache[self]
        left = self.left.syntax(cls, cache=cache)
        right = self.right.syntax(cls, cache=cache)
        match self.kind:
            case ThenKind.BOTH:
                ret = left + right
            case ThenKind.LEFT:
                ret = left // right
            case ThenKind.RIGHT:
                ret = left >> right
            case _:
                raise AssertionError(f"Unknown ThenKind: {self.kind}")
        ret = ret._named(name=self.name, file=self.file, line=self.line, func=self.func)
        cache[self] = ret
        return ret

    @classmethod
    def flatten(cls, node: SyntaxSpec) -> List[SyntaxSpec | ThenKind]:
        parts = []
        if isinstance(node, ThenSpec):
            parts.extend(cls.flatten(node.left))
            parts.append(node.kind)
            parts.extend(cls.flatten(node.right))
        else:
            parts.append(node)
        return parts

    def __str__(self) -> str:
        if self.name:
            return self.format("{0}", self.name)
        else:
            parts = ThenSpec.flatten(self)
            return  f"({' '.join(str(n) for n in parts)})"
        

    @property
    def complexity(self) -> float:
        return 1 + self.left.complexity + self.right.complexity
    
    def _children(self,*, lazy_cache: MutableMapping[int, SyntaxSpec]) -> Tuple[SyntaxSpec, ...]:
        return (self.left, self.right)

@dataclass(frozen=True, slots=True)
class ParallelSpec(SyntaxSpec):
    options: Tuple[SyntaxSpec, ...]
    reducer: Callable[[Any, List[Tuple[Any, Any]]], Either[Any, Tuple[Any, Any]]]
    def syntax(self, cls: type[Syntax], cache: MutableMapping[SyntaxSpec, Syntax]) -> Syntax[Any, Any]:
        if self in cache:
            return cache[self]
        opts = [opt.syntax(cls, cache=cache) for opt in self.options]
        ret = cls.parallel(*opts, reducer=self.reducer)
        ret = ret._named(name=self.name, file=self.file, line=self.line, func=self.func)
        cache[self] = ret
        return ret
    
    def __str__(self) -> str:
        if self.name:
            return self.name
        else:
            choices = [str(opt) for opt in self.options]
            inner = " || ".join(str(c) for c in choices)
            return self.format("({choices})", choices=inner)

    @property
    def complexity(self) -> float:
        return 1 + max(opt.complexity for opt in self.options)

    def _children(self, *, lazy_cache: MutableMapping[int, SyntaxSpec]) -> Tuple[SyntaxSpec, ...]:
        return self.options


@dataclass(frozen=True, slots=True)
class ChoiceSpec(SyntaxSpec):
    options: Tuple[SyntaxSpec, ...]
    def syntax(self, cls: type[Syntax], cache: MutableMapping[SyntaxSpec, Syntax]) -> Syntax[Any, Any]:
        if self in cache:
            return cache[self]
        opts = [opt.syntax(cls, cache=cache) for opt in self.options]
        ret = cls.choice(*opts)
        ret = ret._named(name=self.name, file=self.file, line=self.line, func=self.func)
        cache[self] = ret
        return ret

    def __str__(self) -> str:
        if self.name:
            return self.name
        else:
            choices = [str(opt) for opt in self.options]
            inner = " | ".join(str(c) for c in choices)
            return self.format("({choices})", choices=inner)

    @property
    def complexity(self) -> float:
        return 1 + max(opt.complexity for opt in self.options)

    def _children(self, *, lazy_cache: MutableMapping[int, SyntaxSpec]) -> Tuple[SyntaxSpec, ...]:
        return self.options
    
@dataclass(frozen=True, slots=True)
class OrElseSpec(SyntaxSpec, Generic[A, B]):
    left: SyntaxSpec
    right: SyntaxSpec

    def syntax(self, cls: type[Syntax], cache: MutableMapping[SyntaxSpec, Syntax])-> Syntax[Any, Any]:
        if self in cache:
            return cache[self]
        left = self.left.syntax(cls, cache=cache)
        right = self.right.syntax(cls, cache=cache)
        ret = left | right
        ret = ret._named(name=self.name, file=self.file, line=self.line, func=self.func)
        cache[self] = ret
        return ret

    @classmethod
    def flatten(cls, node: SyntaxSpec) -> List[SyntaxSpec]:
        choices = []
        if isinstance(node, OrElseSpec):
            choices.extend(cls.flatten(node.left))
            choices.extend(cls.flatten(node.right))
        else:
            choices.append(node)
        return choices


    def __str__(self) -> str:
        if self.name:
            return self.name
        else:
            choices = OrElseSpec.flatten(self)
            if len(choices) == 2:
                return self.format("({left} | {right})", left=str(choices[0]), right=str(choices[1]))
            else:
                inner = " | ".join(str(c) for c in choices)
                return self.format("({choices})", choices=inner)
            
    @property
    def complexity(self) -> float:
        return 1 + max(self.left.complexity, self.right.complexity)

    def _children(self, *, lazy_cache: MutableMapping[int, SyntaxSpec]) -> Tuple[SyntaxSpec, ...]:
        return (self.left, self.right)

@dataclass(frozen=True, slots=True)
class ManySpec(SyntaxSpec, Generic[A]):
    spec: SyntaxSpec
    at_least: int
    at_most: Optional[int]

    def syntax(self, cls: type[Syntax], cache: MutableMapping[SyntaxSpec, Syntax])-> Syntax[Any, Any]:
        if self in cache:
            return cache[self]
        inner = self.spec.syntax(cls, cache=cache)
        ret = inner.many(at_least=self.at_least, at_most=self.at_most)
        ret = ret._named(name=self.name, file=self.file, line=self.line, func=self.func)
        cache[self] = ret
        return ret

    def __str__(self) -> str:
        if self.name:
            return self.name
        else:
            return self.format("*({spec})", spec=str(self.spec))
        
    @property
    def complexity(self) -> float:
        if self.at_most is None:
            return 1 + self.spec.complexity * (self.at_least + 1)        
        else:
            return 1 + self.spec.complexity * ((self.at_least + self.at_most) // 2)
    
    def _children(self, *, lazy_cache: MutableMapping[int, SyntaxSpec]) -> Tuple[SyntaxSpec, ...]:
        return (self.spec,)



@dataclass(frozen=True, slots=True)
class LexSpec(SyntaxSpec):
    fname: str
    args: Tuple[Any, ...] = field(default_factory=tuple)
    kwargs: FrozenDict[str, Any] = field(default_factory=FrozenDict)
    def syntax(self, cls: type[Syntax], cache: MutableMapping[SyntaxSpec, Syntax])-> Syntax[Any, Any]:
        if self in cache:
            return cache[self]
        ret = cls.factory(self.fname, *self.args, **self.kwargs)
        ret = ret._named(name=self.name, file=self.file, line=self.line, func=self.func)
        cache[self] = ret
        return ret
    
    def __str__(self) -> str:
        if self.name or not self.kwargs:
            return self.name or self.fname
        else:
            parts = []
            for a in self.args:
                s = str(a)
                if len(s) > 20:
                    s = s[:17] + "..."
                parts.append(s)
            args = ','.join(parts)
            kwparts = []
            for k, v in self.kwargs.items():
                if v is not None:
                    s = str(v)
                    if len(s) > 20:
                        s = s[:17] + "..."
                    kwparts.append(f"{k}={s}")
            kwargs = ', '.join(kwparts)
            return self.format("{fname}({args}, {kwargs})", fname=self.fname, args=args, kwargs=kwargs)
    
    @property
    def complexity(self) -> float:
        return 1
    
@dataclass
class LazyState(Generic[A, S]):
    flatten: bool
    # thunk returns a Syntax[A, S], the original callable passed to Syntax.lazy
    thunk: Callable[[], Syntax[A, S]]
    # cached resolved Syntax; excluded from comparisons
    _cached_syntax: Optional[Syntax[A, S]] = field(default=None, init=False, repr=False, compare=False)
    # cache algebras per (alg, kwargs_key). excluded from comparisons
    _inner_algebras_cache: Dict[Tuple[Type[Algebra[Any, Any]], Tuple[Tuple[str, Any], ...]], Algebra[A, S]] = field(default_factory=dict, init=False, repr=False, compare=False)
    _algebras_cache: Dict[Tuple[Type[Algebra[Any, Any]], Tuple[Tuple[str, Any], ...]], Algebra[A, S]] = field(default_factory=dict, init=False, repr=False, compare=False)


    def __hash__(self) -> int:
        return hash((self.flatten, self.thunk))
    
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, LazyState):
            return False
        return self.flatten == other.flatten and self.thunk == other.thunk

    @property
    def cached(self) -> Syntax[A, S]:
        # Double-checked locking: avoid acquiring lock in the fast path.
        if self._cached_syntax is None:
            if self.thunk is None:
                raise SyncraftError("LazyState missing thunk", offender=self, expect="a thunk Callable")
            resolved = self.thunk()
            if not isinstance(resolved, Syntax):
                raise SyncraftError("Lazy thunk did not return a Syntax", offender=(self.thunk, resolved), expect="Syntax")
            # store resolved syntax into the frozen dataclass slot
            self._cached_syntax = resolved
                    
        return self._cached_syntax  # type: ignore

    def __call__(self, alg_cls: Type[Algebra[Any, Any]], **global_kwargs) -> Algebra[A, S]:
        # Create a deterministic, hashable representation of global_kwargs.
        # NOTE: this requires that keys are strings (they are) and values are hashable.
        if global_kwargs:
            try:
                kwargs_key = tuple(sorted(global_kwargs.items()))
            except TypeError:
                # If kwargs contain unhashable values, fallback to using id() for values.
                kwargs_key = tuple(sorted(
                    (k, (v if isinstance(v, (int, str, float, bool, type(None))) else id(v))) 
                    for k, v in global_kwargs.items()))
        else:
            kwargs_key = ()

        key = (alg_cls, kwargs_key)
        existing = self._algebras_cache.get(key)
        if existing is not None:
            return existing

        def algebra_lazy_f() -> Algebra[A, S]:
            if key in self._inner_algebras_cache:
                return self._inner_algebras_cache[key]
            ret = self.cached(alg_cls, **global_kwargs)
            self._inner_algebras_cache[key] = ret
            return ret
        algebra = alg_cls.lazy(algebra_lazy_f, flatten=self.flatten).flag(is_lazy=True)
        self._algebras_cache[key] = algebra
        return algebra
        



@dataclass(frozen=True, slots=True, weakref_slot=True)
class Syntax(Generic[A, S]):
    """
    The core signature of Syntax is take an Algebra Class and return an Algebra Instance.
    """
    
    alg_f: Callable[..., Algebra[A, S]]
    spec: SyntaxSpec = field(repr=False)
    _lexspec_cache: frozenset[LexSpec] = field(default = MISSING, init=False, repr=False, compare=False, hash=False)
    _lazy_facade_cache: ClassVar[ThreadLocalWeakValueDict[Callable[..., Any], Syntax[Any, Any]]] = ThreadLocalWeakValueDict()
    _syntax_cache: ClassVar[ThreadLocalWeakValueDict[SyntaxSpec, Syntax[Any, Any]]] = ThreadLocalWeakValueDict()
    
    def vis(self, depth: int = 3) -> Optional[SVGVisualization]:
        from syncraft.vis import syntax2svg
        return syntax2svg(self.spec, max_depth=depth)
        
    
       
    def as_(self, typ: Type[B]) -> B:
        return cast(typ, self)  # type: ignore
    
    @classmethod
    def config(cls, **attrs: Any) -> Type['Syntax[Any, Any]']:
        return type(cls.__name__, (cls,), {SYNCRAFT_CONFIG_KEY: attrs})


    def __call__(self, alg: Type[Algebra[Any, Any]], **global_kwargs) -> Algebra[A, S]:
        cfg = getattr(self.__class__, SYNCRAFT_CONFIG_KEY, {})
        return self.alg_f(alg, **(cfg | global_kwargs)).with_syntax(self)

    def _named(self, *, name: None | str, file: None | str, line: None | int, func: None | str) -> Syntax[A, S]:
        return replace(self, spec=self.spec.named(name=name, file=file, line=line, func=func, _location=True))         

    def named(self, name: str, *, level:int=0, _location:bool=True) -> Syntax[A, S]:
        return replace(self, spec=self.spec.named(name=name, file=get_file(level+1), line=get_line(level+1), func=get_func(level+1), _location=_location))

    ######################################################## value transformation ########################################################
    def map(self, f: Callable[[Any], B],*, raw:bool = False) -> Syntax[B, S]:
        """Map the produced value while preserving state and metadata.

        Args:
            f: Function mapping value A to B.

        Returns:
            Syntax yielding B with the same resulting state.
        """
        return replace(self, alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).map(f, raw=raw)) # type: ignore

    def walk(self, *, max_depth: Optional[int] = None) -> Iterator[Tuple[int, SyntaxSpec]]:
        return self.spec.walk(max_depth=max_depth)

    def graph(
        self,
        *,
        max_depth: Optional[int] = None,
    ) -> Graph[SyntaxSpec]:
        return self.spec.graph(max_depth=max_depth)

    def iso(self, f: Callable[[A], B], i: Callable[[B], A]) -> Syntax[B, S]:
        """Bidirectionally map values with an inverse, keeping round-trip info.

        Applies f to the value and adjusts internal state via inverse i so
        generation/parsing stay in sync.

        Args:
            f: Forward mapping A -> B.
            i: Inverse mapping B -> A applied to the state.

        Returns:
            Syntax yielding B with state alignment preserved.
        """
        return replace(self, alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).iso(f, i)) # type: ignore


    def map_all(self, f: Callable[[A, S], Tuple[B, S]]) -> Syntax[B, S]:
        """Map both value and state on success.

        Args:
            f: Function mapping (value, state) to (new_value, new_state).

        Returns:
            Syntax yielding transformed value and state.
        """
        return replace(self, alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).map_all(f)) # type: ignore

    def map_error(self, f: Callable[[Optional[Any]], Any]) -> Syntax[A, S]:
        """Transform the error payload when this syntax fails.

        Args:
            f: Function applied to the error payload of Left.

        Returns:
            Syntax that preserves successes and maps failures.
        """
        return replace(self, alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).map_error(f)) 
        

    def map_state(self, f: Callable[[S], S]) -> Syntax[A, S]:
        """Map the input state before running this syntax.

        Args:
            f: S -> S function applied to the state prior to running.

        Returns:
            Syntax that runs with f(state).
        """
        return replace(self, alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).map_state(f))
        

    def flat_map(self, f: Callable[[A], Algebra[B, S]]) -> Syntax[B, S]:
        """Chain computations where the next step depends on the value.

        Args:
            f: Function mapping value to the next algebra to run.

        Returns:
            Syntax yielding the result of the chained computation.
        """
        return replace(self, alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).flat_map(f)) # type: ignore

    def many(self, *, at_least: int = 0, at_most: Optional[int] = None) -> Syntax[Many[A], S]:
        """Repeat this syntax and collect results into Many.

        Repeats greedily until failure or no progress. Enforces bounds.

        Args:
            at_least: Minimum number of matches (default 0).
            at_most: Optional maximum number of matches.

        Returns:
            Syntax producing Many of values.
        """
        return replace(self, 
                       alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).many(at_least=at_least, at_most=at_most), # type: ignore
                       spec = ManySpec(spec=self.spec, 
                                       at_least=at_least, 
                                       at_most=at_most, 
                                       name=self.spec.name, 
                                       file=self.spec.file, 
                                       line=self.spec.line, 
                                       func=self.spec.func)
                       )
    

    def on_fail(self, f: Callable[[Optional[Syntax[A, S]], S, Any], Either[Any, Tuple[Any, S]]] | None | Any) -> Syntax[Any, S]:
        """Attach a callback to handle failure cases.

        Args:
            f: Function called on failure with (algebra, state, error).

        Returns:
            Syntax that invokes f on failure.

        """
        def _on_fail(alg: Algebra[A, S], input: S, error: Any) -> Either[Any, Tuple[Any, S]]:
            if callable(f):
                return f(alg.syntax, input, error) # type: ignore
            else:
                return Left.new(f)
        if f is None:
            return self
        return replace(self, alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).on_fail(_on_fail)) 
    
    def on_success(self, f: Callable[[Optional[Syntax[A, S]], S, Tuple[A,S]], Either[Any, Tuple[Any, S]]] | None | Any) -> Syntax[Any, S]:
        """Attach a callback to handle success cases.

        Args:
            f: Function called on success with (algebra, value, state).

        Returns:
            Syntax that invokes f on success.
        """
        def _on_success(alg: Algebra[A, S], input: S, result: Tuple[A, S]) -> Either[Any, Tuple[Any, S]]:
            if callable(f):
                return f(alg.syntax, input, result) # type: ignore
            else:
                return Right.new((f, result[1])) 
        if f is None:
            return self 
        return replace(self, alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).on_success(_on_success)) 
    
    def debug(self, 
              dbg: Callable[[Syntax[A, S], S, Optional[S], A | Any, List[Tuple[Syntax[Any, S], int]]], None] | Any = None,
              *,
              disable: bool = False,
              show_stack: bool = True,
              only_fail: bool = False,
              only_success: bool = False,
              level:int = 0) -> Syntax[A, S]:
        if disable:
            return self
        file=get_file(level+1)
        line=get_line(level+1)
        def default_dbg(syn: Syntax[A, S], input: S, new_state: Optional[S], value: A | Any, stack: List[Tuple[Syntax[Any, S], int]])->None:
            if new_state is not None and only_fail:
                return
            if new_state is None and only_success:
                return
            def fmt_input(ipt)->str:
                if hasattr(ipt, 'str_input'):
                    f = getattr(ipt, 'str_input')
                    return f(False)
                else:
                    return str(ipt)
            null = new_state is not None and new_state.cache_key == input.cache_key
            GREEN = "\033[92m"
            RESET = "\033[0m"
            RED = "\033[91m"

            sign = f"{RED}\u2718{RESET}" if new_state is None else f"{GREEN}\u2714{RESET}"
            print('=' * 20, "DEBUG", sign, dbg if dbg is not None else "@", f"{file}:{line}", '=' * 20)
            print(f"       Syntax: {syn.spec}")
            print(f"  Input State: {fmt_input(input)}")
            if new_state is not None:
                print(f"    New State: {fmt_input(new_state) if not null else '< NO CHANGE >'}")
            indent = " " * 15
            if isinstance(value, Error):
                depth: int | None = None
                if value.state:
                    depth = value.state.cache_key - input.cache_key
                depth_str=f"{depth}" if depth is not None else ""
                lns = [f"{indent if i>0 else ''}{s}" for i, s in enumerate(value.compact)]
                s = '\n'.join(lns)
                print(f"        Error: {s} --- backtrack depth: {depth_str}")
                print()
            else:
                if hasattr(value, 'mapped'):
                    print(f"        Value: {getattr(value, 'mapped')}")
                else:
                    print(f"        Value: {value}")
            if show_stack:
                print( "   Call Stack:")
                lns = Error.fmt_stack(stack, indent=" " * 13)
                print('\n'.join(lns))

        xdbg: Callable[[Syntax[A, S], S, Optional[S], A | Any, List[Tuple[Syntax[Any, S], int]]], None] | Any = dbg if callable(dbg) else default_dbg
        return replace(self, alg_f = lambda acls, **global_args: self(acls, **global_args).debug(dbg=xdbg))
            
    ############################################################### facility combinators ############################################################
    def between(self, left: Syntax[B, S], right: Syntax[C, S]) -> Syntax[Seq, S]:
        return self.seq(left , +self , right)

    def sep_by(self, sep: Syntax[B, S]) -> Syntax[Then[A, Many[Then[B, A]]], S]:
        """Parse this syntax separated by the given separator.
        
        Parses one or more occurrences of this syntax separated by the separator.
        Returns the first element and a Many containing the remaining elements
        paired with their separators.
        
        Args:
            sep: Separator syntax to use between elements.
            
        Returns:
            Syntax producing Then(first_element, Many(separator_element_pairs)).
            The result is automatically transformed via iso() to produce Many[A]
            containing all parsed elements without the separators.
            
        Example:
            >>> from syncraft.syntax import Syntax
            >>> A = Syntax.literal("a")
            >>> comma = Syntax.literal(",")
            >>> syntax = A.sep_by(comma)
            >>> # Parses "a,a,a" and produces Many containing three "a" elements
        """
        ret: Syntax[Then[A, Many[Then[B, A]]], S] = self + (sep >> self).many()

        def f(a: Then[A, Many[Then[B, A]]]) -> Many[A]:
            match a:
                case Then(
                    kind=ThenKind.BOTH,
                    left=left,
                    right=Many(value=bs),
                ):
                    return Many(value=(left,) + tuple(b.right for b in bs))
                case _:
                    raise SyncraftError(f"Bad data shape {a}", offender=a, expect="Then(BOTH) with OrElse on the right")

        def i(a: Many[A]) -> Then[A, Many[Then[B|None, A]]]:
            if not isinstance(a, Many) or len(a.value) < 1:
                raise SyncraftError(f"sep_by inverse expect Many with at least one element, got {a}", offender=a, expect="Many with at least one element")
            v: List[Then[B | None, A]] = [
                Then(kind=ThenKind.RIGHT, right=x, left=None) for x in a.value[1:]
            ]
            return Then(
                kind=ThenKind.BOTH,
                left=a.value[0],
                right=Many(value=tuple(v)),
            )
        return ret.iso(f, i)  # type: ignore

    def parens(
        self,
        sep: Syntax[C, S],
        open: Syntax[B, S],
        close: Syntax[D, S],
    ) -> Syntax[Seq, S]:
        """Parse a parenthesized, separator-delimited list.

        Shorthand for self.sep_by(sep).between(open, close).

        Args:
            sep: Separator between elements.
            open: Opening delimiter.
            close: Closing delimiter.

        Returns:
            Syntax producing all three parts with the list nested inside.
        """
        return self.sep_by(sep=sep).between(left=open, right=close)

    @property
    def optional(self) -> Syntax[OrElse[A, type[Nothing]], S]:
        """Make this syntax optional.

        Returns a OrElse of the value or Nothing when absent.

        Returns:
            Syntax producing OrElse of value or Nothing.
        """
        return (self | self.success(Nothing)).named(f"({str(self.spec)})?", _location=False)
        
    @property
    def cut(self) -> Syntax[A, S]:
        """Commit this branch: on failure, prevent trying alternatives.

        Wraps the underlying algebra's cut.

        Returns:
            Syntax that marks downstream failures as committed.
        """
        return replace(self, alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).cut())


    ###################################################### operator overloading #############################################
    def __floordiv__(self, other: Syntax[B, S]) -> Syntax[Then[A, B], S]:
        """Then-left: run both and prefer the left in the result kind.

        Returns Then(kind=LEFT) with both left and right values.

        Args:
            other: Syntax to run after this one.

        Returns:
            Syntax producing Then(left, right, kind=LEFT).
        """

        return replace(self, 
                       alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).then_left(other(cls, **global_kwargs)), # type: ignore
                       spec = ThenSpec(kind=ThenKind.LEFT, 
                                       left=self.spec, 
                                       right=other.spec, 
                                       name=None, 
                                       file=None, 
                                       line=None, 
                                       func=None)
                   )


    def __rfloordiv__(self, other: Syntax[B, S]) -> Syntax[Then[B, A], S]:

        return other.__floordiv__(self)

    def __add__(self, other: Syntax[B, S]) -> Syntax[Then[A, B], S]:
        """Then-both: run both and keep both values.

        Returns Then(kind=BOTH).

        Args:
            other: Syntax to run after this one.

        Returns:
            Syntax producing Then(left, right, kind=BOTH).
        """

        return replace(self, 
                       alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).then_both(other(cls, **global_kwargs)), # type: ignore
                       spec=ThenSpec(kind=ThenKind.BOTH, left=self.spec, right=other.spec, name=None, file=None, line=None, func=None))


    def __radd__(self, other: Syntax[B, S]) -> Syntax[Then[B, A], S]:

        return other.__add__(self)

    def __rshift__(self, other: Syntax[B, S]) -> Syntax[Then[A, B], S]:
        """Then-right: run both and prefer the right in the result kind.

        Returns Then(kind=RIGHT).

        Args:
            other: Syntax to run after this one.

        Returns:
            Syntax producing Then(left, right, kind=RIGHT).
        """

        return replace(self, 
                       alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).then_right(other(cls, **global_kwargs)),  # type: ignore
                       spec=ThenSpec(kind=ThenKind.RIGHT, left=self.spec, right=other.spec, name=None, file=None, line=None, func=None))
        

    def __rrshift__(self, other: Syntax[B, S]) -> Syntax[Then[B, A], S]:

        return other.__rshift__(self)

    def __or__(self, other: Syntax[B, S]) -> Syntax[OrElse[A, B], S]:
        """Alternative: try this syntax; if it fails uncommitted, try the other.

        Returns a OrElse indicating which branch succeeded.

        Args:
            other: Alternative syntax to try on failure.

        Returns:
            Syntax producing OrElse.LEFT or OrElse.RIGHT.
        """

        return replace(self, 
                       alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).or_else(other(cls, **global_kwargs)).flag(is_orelse=True), # type: ignore
                       spec=OrElseSpec(left=self.spec, 
                                       right=other.spec, 
                                       name=None, 
                                       file=None, 
                                       line=None, 
                                       func=None))
        

    def __ror__(self, other: Syntax[B, S]) -> Syntax[OrElse[B, A], S]:

        return other.__or__(self)
    

    def __pos__(self) -> Tuple[Syntax[A, S], bool]:
        return (self, True)

    def __neg__(self) -> Tuple[Syntax[A, S], bool]:
        return (self, False)

    def __invert__(self) -> Syntax[OrElse[A, type[Nothing]], S]:
        """Syntactic sugar for optional() (tilde operator)."""
        return self.optional

    ######################################################################## data processing combinators #########################################################
    def bind(self, 
             this_f: None | str | Callable[[Any, S], Any] = None,
             *, 
             raw:bool=False, 
             **kwargs: Callable[[Any, S], Any]) -> Syntax[A, S]:
        def bind_v(v: A, s: S) -> Tuple[A, S]:
            if isinstance(v, AST) and not raw:
                vv = v.mapped
            else:
                vv = v

            if callable(this_f):
                new_value = this_f(vv, s)
                if isinstance(v, Marked):
                    real_name = v.name
                elif isinstance(v, Collect) and isinstance(v.collector, type):
                    real_name = v.collector.__name__
                else:
                    raise SyncraftError("bind this_f requires marked or collected value", offender=v, expect="Marked or Collect")
                s = s.bind(real_name, new_value)
            elif isinstance(this_f, str):
                s = s.bind(this_f, vv)
            for real_name, f in kwargs.items():
                new_value = f(vv, s)
                s = s.bind(real_name, new_value)

            return v, s
        return self.map_all(bind_v)
    
    def update(self,
               this_f: None | str | Callable[[Any, Any], Any] = None,
               *, 
               raw:bool=False, 
               **kwargs: Callable[[Any, Any], Any]) -> Syntax[A, S]:
        def replace_v(v: A, s: S) -> tuple[A, S]:
            if isinstance(v, AST) and not raw:
                vv = v.mapped
            else:
                vv = v
            if callable(this_f):
                if isinstance(v, Marked):
                    real_name = v.name
                elif isinstance(v, Collect) and isinstance(v.collector, type):
                    real_name = v.collector.__name__
                else:
                    raise SyncraftError("update this_f requires marked or collected value", offender=v, expect="Marked or Collect")
                new_value = this_f(s.get(real_name), vv)
                s = s.replace(real_name, new_value)
            elif isinstance(this_f, str):
                s = s.replace(this_f, vv)

            for real_name, f in kwargs.items():
                new_value = f(s.get(real_name), vv)
                s = s.replace(real_name, new_value)
            return v, s
        return self.map_all(replace_v)
    
    def check(self,
              this_f: None | Callable[..., bool] | Constraint = None,
              *, 
              raw:bool=False) -> Syntax[A, S]:
        def check_v(this: Optional[Syntax[A, S]], old_s: S, result: Tuple[A, S]) -> Either[Any, Tuple[Any, S]]:
            v, s = result
            if isinstance(v, AST) and not raw:
                vv = v.mapped
            else:
                vv = v
            if isinstance(this_f, Constraint):
                check_result = this_f(vv, s.all_bindings)
                if not check_result.result:
                    return Left.new(Error.new(this=this, 
                                              message=f"Check failed for 'this' with value {vv}: {check_result}", 
                                              state=old_s))
            elif callable(this_f):
                d = s.all_bindings
                if d:
                    c = CallWith(this_f, vv, **d)
                else:
                    c = CallWith(this_f, vv)
                    if c.missing_args:
                        pesudo_args = [... for _ in c.missing_args]
                    else:
                        pesudo_args = []
                    if c.missing_kwargs:
                        pesudo_kwargs = {k: ... for k in c.missing_kwargs}
                    else:
                        pesudo_kwargs = {}
                    c = CallWith(this_f, vv, *pesudo_args, **pesudo_kwargs)
                if not c():
                    return Left.new(Error.new(this=this, 
                                              message=f"Check failed for 'this' with value {vv}", 
                                              state=old_s))

            return Right.new(result)
        return self.on_success(check_v)

    def to(self, f: Collector[E], id: Hashable = None, **kwargs: Any) -> Syntax[Collect[A, E], S]:
        """Attach a collector to the produced value.
        A collector can be a dataclass, and the Marked nodes will be 
        mapped to the fields of the dataclass.

        Wraps the value in Collect or updates an existing one.

        Args:
            f: Collector invoked during generation/printing.
            id: Optional unique identifier for the syntax node. When f is a lambda function, id should be provided to distinguish different collectors.
                When f is a lambda the same function has different identity each time it is defined, so id helps to identify the collector uniquely.

        Returns:
            Syntax producing Collect(value, collector=f).
        """
        if not callable(f):
            raise SyncraftError("Collector f must be callable", offender=f, expect="callable")
        if kwargs:
            f = partial(f, **kwargs)
            if id is None:
                id = hashlib.md5(repr(kwargs).encode('utf-8')).hexdigest()
        def to_f(v: A) -> Collect[A, E]:
            if isinstance(v, Collect):
                return replace(v, collector=f)
            else:
                return Collect(collector=f, value=v)

        def ito_f(c: Collect[A, E]) -> A:
            return c.value if isinstance(c, Collect) else c

        ret = self.iso(to_f, ito_f)
        return replace(ret, spec=CollectSpec(collector=f, 
                                             id=id,
                                             kwargs=FrozenDict(kwargs),
                                             spec=self.spec, 
                                             name=self.spec.name, 
                                             file=self.spec.file, 
                                             line=self.spec.line, 
                                             func=self.spec.func))

    def mark(self, name: str) -> Syntax[Marked[A], S]:

        assert valid_name(name), f"Invalid mark name: {name}"

        def mark_s(value: A) -> Marked[A]:
            if isinstance(value, Marked):
                return replace(value, name=name)
            else:
                return Marked(name=name, value=value)

        def imark_s(m: Marked[A]) -> A:
            return m.value if isinstance(m, Marked) else m


        ret = self.iso(mark_s, imark_s)
        spec = self.spec
        if isinstance(spec, MarkedSpec):
            spec = replace(spec, mname=name)
        return replace(ret, spec=MarkedSpec(mname=name, 
                                            name=spec.name,
                                            spec=spec, 
                                            file=spec.file, 
                                            line=spec.line, 
                                            func=spec.func))
    
    @property
    def lexspec(self) -> frozenset[LexSpec]:
        if self._lexspec_cache is MISSING:            
            result: Set[LexSpec] = set()
            for _, node in self.spec.walk():
                if isinstance(node, LexSpec):
                    result.add(node)
            object.__setattr__(self, '_lexspec_cache', frozenset(result))
        return self._lexspec_cache


    @classmethod
    def fail(cls, error: B) -> Syntax[B, S]:
        return cls.factory('fail', error=error)

    @classmethod
    def success(cls, value: B) -> Syntax[B, S]:
        return cls.factory('success', value=value)
    

    @classmethod
    def parallel(cls, 
                 *parsers: Syntax[Any, S], 
                 reducer: Callable[[S, List[Tuple[Any, S]]], Either[Any, Tuple[Any, S]]],
                 share_cache:bool=True) -> Syntax[Any, S]:
        def parallel_f(acls: Type[Algebra[Any, Any]], **global_kwargs: Any)->Algebra[Any, Any]:
            algs = [p(acls, **global_kwargs) for p in parsers]
            return acls.parallel(*algs, reducer=reducer, share_cache=share_cache)
        spec = ParallelSpec(options=tuple(p.spec for p in parsers), reducer=reducer, name=None, file=None, line=None, func=None)
        return cls(alg_f = parallel_f, spec=spec)

    @classmethod
    def choice(cls, *parsers: Syntax[Any, S]) -> Syntax[Choice[Any], S]:
        def choice_f(acls: Type[Algebra[Any, Any]], **global_kwargs: Any) -> Algebra[Any, Any]:
            algs = [p(acls, **global_kwargs) for p in parsers]
            return acls.choice(*algs).flag(is_orelse=True)
        spec = ChoiceSpec(options=tuple(p.spec for p in parsers), name=None, file=None, line=None, func=None)
        return cls(alg_f=choice_f, spec=spec) # type: ignore
    
    @classmethod
    def seq(cls, *steps: Syntax[Any, S] | Tuple[Syntax[Any, S], bool], default:bool = True) -> Syntax[Seq, S]:
        infered_default: Optional[bool] = None
        for X in steps:
            if isinstance(X, tuple):
                if len(X) != 2:
                    raise SyncraftError("Invalid tuple in seq steps", offender=X, expect="Tuple of (Syntax, bool)")
                elif infered_default is None:
                    infered_default = not bool(X[1])
                elif infered_default == bool(X[1]):
                    infered_default = None
                    break
        if infered_default is not None:
            default = infered_default
        syntaxes = []
        for X in steps:
            step, keep = X if isinstance(X, tuple) else (X, default)
            syntaxes.append((step, bool(keep)))
        def seq_f(acls: Type[Algebra[Any, Any]], **global_kwargs: Any) -> Algebra[Any, Any]:
            algs = [(step(acls, **global_kwargs), keep) for step, keep in syntaxes]
            return acls.seq(*algs)
        spec = SeqSpec(steps=tuple((step.spec, keep) for step, keep in syntaxes), name=None, file=None, line=None, func=None)
        return cls(alg_f=seq_f, spec=spec) # type: ignore


    @classmethod
    def lazy(cls, thunk: Callable[[], Syntax[A, S]], flatten: bool = False) -> Syntax[A, S]:
        facade_cache = cls._lazy_facade_cache
        existing = facade_cache.get(thunk)
        if existing is not None:
            return existing  

        helper = LazyState(flatten=flatten, thunk=thunk)

        facade = cls(alg_f=lambda acls, **global_kwargs: helper(acls, **global_kwargs), 
                     spec=LazySpec(lazy_state=helper,
                                   name=None, 
                                   file=None, 
                                   line=None, 
                                   func=None))
        facade_cache[thunk] = facade
        return facade
    

    @classmethod
    def factory(cls, name: str, *args:Any, **kwargs: Any) -> Syntax[Any, Any]:
        def factory_run(acls: Type[Algebra[Any, Any]], **global_kwargs: Any) -> Algebra[Any, Any]:
            method = getattr(acls, name, None)
            if method is None or not callable(method):
                raise SyncraftError(f"Method {name} is not defined in {acls.__name__}", offender=method, expect='callable')
            result = CallWith(method, *args, **(global_kwargs | kwargs))()
            return cast(Algebra[Any, Any], result)
        return cls(factory_run, spec=LexSpec(fname=name, 
                                             args=args,
                                             kwargs=FrozenDict(kwargs), 
                                             name=None, 
                                             file=None, 
                                             line=None, 
                                             func=None))
    @classmethod
    def eof(cls) -> Syntax[Any, Any]:
        return cls.factory('eof')

    @classmethod
    def token(cls, **kwargs: Any) -> Syntax[Any, Any]:
        tkspec: TokenSpec[Any] | None = TokenSpecBase.from_kwargs(**kwargs)
        assert tkspec is not None, "TokenSpecBase.from_kwargs returned None"
        return cls.factory('lex', tkspec=tkspec)

    @classmethod
    def lex(cls, **kwargs: Builder) -> Syntax[Any, Any]:
        return cls.factory('lex', **kwargs)
    
    @classmethod
    def literal(cls, lit: str | re.Pattern[str]) -> Syntax[Any, Any]:
        return cls.token(text=lit, case_sensitive=True)
    

    @classmethod
    def from_spec(cls, spec: SyntaxSpec)->Syntax[Any, Any]:
        c: Dict[SyntaxSpec, Syntax] = {}
        return spec.syntax(cls, cache=c)


    @classmethod
    def from_graph(cls, graph: Graph[SyntaxSpec]) -> Syntax[Any, Any]:
        c: Dict[SyntaxSpec, Syntax] = {}
        return graph.root.syntax(cls, cache=c)
    
class RunnerProtocol(Protocol, Generic[A, S]):
    def algebra(self, 
                syntax: Syntax[A, S],
                alg_cls: Type[Algebra[A, S]],
                payload_kind: Optional[PayloadKind]) -> Algebra[A, S]: ...

    def resume(self, previous: Optional[S], cursor: Optional[StreamCursor[Any]]) -> S: ...

    def finalize(self, result: Optional[Tuple[Any, None | S]]) -> None: 
        return


    def run(self, 
            parser: Algebra[A, S], 
            state: Optional[S],
            cursor: Optional[StreamCursor[Any]],
            cache: Optional[Cache[Any]],
            once: bool
            ) -> Generator[Tuple[Any, None | S], None, None]: 
        while True:
            ret = None
            state = self.resume(state, cursor)
            gen_cache: Cache[Any] = cache or Cache()
            parser_gen = parser.run(state, cache=gen_cache)
            try:
                result = next(parser_gen)
                while True:
                    if isinstance(result, Incomplete):
                        pending_state = self.resume(result.state, cursor)
                        gen_cache.gc(pending_state.unused_cache_key())                    
                        result = parser_gen.send(pending_state)
                    else:
                        raise AssertionError("Unexpected yield from algebra: expected Incomplete")  # pragma: no cover
            except StopIteration as e:
                result = e.value
                if isinstance(result, Right):
                    assert result.value is not None, "Algebra returned Right with None value"
                    ret = result.value
                elif isinstance(result, Left):
                    assert result.value is not None, "Algebra returned Left with None value"
                    ret = result.value, None
                else:
                    ret = Error.new(this=result, message="Algebra returned data that is not Left or Right"), None
            finally:
                self.finalize(ret)
            yield ret  # type: ignore
            if once:
                break

    def __call__(self, 
                 syntax: Syntax[A, S], 
                 alg_cls: Type[Algebra[A, S]],
                 state: Optional[S],
                 cursor: Optional[StreamCursor[Any]],
                 cache: Optional[Cache[Any]],
                 once: bool
                 ) -> Generator[Tuple[Any, None | S], None, None]:
        alg = self.algebra(syntax=syntax, alg_cls=alg_cls, payload_kind=cursor.payload_kind if cursor else None)  
        yield from self.run(alg, state, cursor, cache, once=once)

    def once(self, 
             syntax: Syntax[A, S], 
             alg_cls: Type[Algebra[A, S]],
             state: Optional[S],
             cursor: Optional[StreamCursor[Any]],
             cache: Optional[Cache[Any]]
             ) -> Tuple[Any, None | S]:
        gen = self.__call__(syntax, alg_cls, state, cursor, cache, once=True)
        return next(gen)
        








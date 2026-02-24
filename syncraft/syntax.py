from __future__ import annotations

import keyword

import math

from typing import (
    Optional, Any, TypeVar, Generic, Callable, Tuple, cast, Hashable,
    Type, List, Dict, Set, Iterator, ClassVar, Protocol, Generator, MutableMapping, TYPE_CHECKING,
    Pattern,
)
from dataclasses import dataclass, field, replace

if TYPE_CHECKING:
    from syncraft.vis import SVGVisualization

from syncraft.utils import file as get_file, line as get_line, func as get_func, FrozenDict, CallWith, ThreadLocalWeakValueDict, DbgPrint
from syncraft.algebra import Algebra, Either, Left, Right, SYNCRAFT_CONFIG_KEY, Error
from syncraft.cache import Cache, Incomplete
from syncraft.bimap import Bindable, Iso, DataError
from syncraft.ast import Many, Nothing, SyncraftError, Seq, Alt, Lazy, Unknown
from syncraft.input import StreamCursor
from syncraft.fa import Builder
from syncraft.token import TokenSpec, TokenSpecBase
import threading




GREEN = "\033[92m"
RESET = "\033[0m"
RED = "\033[91m"
UNDERLINE = "\033[4m"
ITALIC = "\033[3m"


def valid_name(name: str) -> bool:
    return (name.isidentifier() 
            and not keyword.iskeyword(name)
            and not (name.startswith('__') and name.endswith('__')))


class RecursionCtx:
    """Thread-local context manager for tracking specs during __str__ traversal to detect cycles."""
    _local = threading.local()
    
    @classmethod
    def get_visiting_specs(cls) -> Set[int]:
        if not hasattr(cls._local, 'visiting_specs'):
            cls._local.visiting_specs = set()
        return cls._local.visiting_specs
    
    @classmethod
    def is_visiting(cls, spec: SyntaxSpec) -> bool:
        return id(spec) in cls.get_visiting_specs()
    
    def __init__(self, spec: SyntaxSpec) -> None:
        self.spec = spec
    
    def __enter__(self) -> RecursionCtx:
        RecursionCtx.get_visiting_specs().add(id(self.spec))
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        RecursionCtx.get_visiting_specs().discard(id(self.spec))


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

    def to_str(self, highlight:int) -> str:
        return str(self)


    def iso(self, *args: Any, **kwargs: Any) -> Iso[Any, Any]:
        return Iso()
        


    @property
    def location(self) -> Optional[str]:
        if self.file:
            return f"{self.file}:{self.line or '?'}"
        return None
    
    def syntax(self, cls: type[Syntax], cache: MutableMapping[SyntaxSpec, Syntax])-> Syntax:
        if self in cache:
            return cache[self]
        raise NotImplementedError
        
    def named(self, *, name: None | str, file: None | str, line: None | int, func: None | str, _location:bool=True) -> SyntaxSpec:
        if _location:
            return replace(self, name=name, file=file, line=line, func=func)
        else:
            return replace(self, name=name)
        

    def update_meta_in_place(self, *, name: None | str, file: None | str, line: None | int, func: None | str, _location:bool) -> SyntaxSpec:
        if _location:
            object.__setattr__(self, 'name', name)
            object.__setattr__(self, 'file', file)
            object.__setattr__(self, 'line', line)
            object.__setattr__(self, 'func', func)
        else:
            object.__setattr__(self, 'name', name)
        # Invalidate str_cache when metadata is updated
        if hasattr(self, 'str_cache'):
            object.__setattr__(self, 'str_cache', None)
        return self



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
    ) -> Graph[SyntaxSpec]:
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
    lazy_state: LazyState
    creation_site: str = field(compare=False, hash=False, init=False)
    str_cache: str | None = field(default=None, compare=False, hash=False, repr=False, init=False)


    def iso(self) -> Iso[Lazy, Any]:
        def fwd(lz: Lazy, ctx: Any) -> Any:
            ret = lz.value
            return ret
        def inv(v: Any, ctx: Any) -> Lazy:
            ret = Lazy(value=v)
            return ret
        return Iso(fwd, inv)

    def __post_init__(self):
        level = 5
        file = get_file(level)
        line = get_line(level)
        object.__setattr__(self, 'creation_site', f" {file}:{line} ")

    def syntax(self, cls: type[Syntax], cache: MutableMapping[SyntaxSpec, Syntax])-> Syntax:
        if self in cache:
            return cache[self]
        ret = cls.lazy(self.lazy_state.thunk)
        cache[self] = ret = replace(ret, spec=self)
        return ret

    def to_str(self, highlight: int) -> str:
        if RecursionCtx.is_visiting(self):
            name = self.name or "lazy(UNSOLVED)"
            return self.format("{0}", name)
        with RecursionCtx(self):
            if self.str_cache is None:
                name = self.name or f"lazy({self.inner_spec})"
                ret = self.format("{0}", name)
                object.__setattr__(self, 'str_cache', ret)
                return ret
            else:
                return self.str_cache
    def __str__(self) -> str:
        return self.to_str(highlight=-1)

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
class SeqSpec(SyntaxSpec):
    steps: Tuple[Tuple[SyntaxSpec, bool], ...]
    str_cache: str | None = field(default=None, compare=False, hash=False, repr=False, init=False)
    
    def iso(self) -> Iso[Seq, Tuple[Any, ...]]:
        def inv(v: Tuple[Any, ...], ctx: Any) -> Seq:
            if not isinstance(v, tuple):
                raise DataError(f"Expected a tuple for SeqSpec value, got {v}", soft_failure=True)
            
            new_elements = []
            v_index = 0
            for spec, include in self.steps:
                if include:
                    data = v[v_index]
                    new_elements.append((data, True)) 
                    v_index += 1
                else:
                    new_elements.append((Unknown(), False))
            ret = Seq(value=tuple(new_elements))
            
            return ret
        def fwd(s: Seq, ctx: Any) -> Tuple[Any, ...]:
            vs = []
            index = 0
            for spec, include in self.steps:
                if include:
                    vs.append(s.value[index][0])
                index += 1
            ret = tuple(vs)
            
            return ret
        return Iso(fwd, inv)

    def syntax(self, cls: type[Syntax], cache: MutableMapping[SyntaxSpec, Syntax])-> Syntax:
        if self in cache:
            return cache[self]
        steps = [(step.syntax(cls, cache=cache), keep) for step, keep in self.steps]
        ret = cls.seq(*steps)
        cache[self] = ret = replace(ret, spec=self)
        return ret

    def to_str(self, highlight: int) -> str:
        if self.str_cache is None:
            if self.name:
                ret = self.name
            else:
                def format_step(s: Tuple[SyntaxSpec, bool], index: int) -> str:
                    step_str = str(s[0])
                    if s[1]:
                        step_str = f"{GREEN}{step_str}{RESET}"
                    if index == highlight:
                        step_str = f"{ITALIC}{step_str}{RESET}"
                    return step_str
                
                inner = " \u25b6 ".join(format_step(s, i) for i, s in enumerate(self.steps))
                ret = self.format("({steps})", steps=inner)
            object.__setattr__(self, 'str_cache', ret)
            return ret
        else:
            return self.str_cache

    def __str__(self) -> str:
        return self.to_str(highlight=-1)
        
    @property
    def complexity(self) -> float:
        return 1 + sum(step.complexity for step, keep in self.steps)
    
    def _children(self,*, lazy_cache: MutableMapping[int, SyntaxSpec]) -> Tuple[SyntaxSpec, ...]:
        return tuple(step for step, keep in self.steps)
    
@dataclass(frozen=True, slots=True)
class AltSpec(SyntaxSpec):
    options: Tuple[SyntaxSpec, ...]

    str_cache: str | None = field(default=None, compare=False, hash=False, repr=False, init=False)

    def iso(self, index: Optional[int] = None) -> Iso[Alt, Any]:
        def fwd(o: Alt, ctx: Any) -> Any:
            ret = o.value
            
            return ret
        def inv(v: Any, ctx: Any) -> Alt:
            ret = Alt(index=index, value=v)
            
            return ret
        return Iso(fwd, inv)



    def syntax(self, cls: type[Syntax], cache: MutableMapping[SyntaxSpec, Syntax]) -> Syntax:
        if self in cache:
            return cache[self]
        opts = [opt.syntax(cls, cache=cache) for opt in self.options]
        ret = cls.alt(*opts)
        cache[self] = ret = replace(ret, spec=self)
        return ret

    def to_str(self, highlight: int) -> str:
        if self.str_cache is None:
            if self.name:
                ret = self.name
            else:
                choices = [str(opt) if i != highlight else f"{ITALIC}{str(opt)}{RESET}" for i, opt in enumerate(self.options)]
                inner = " | ".join(str(c) for c in choices)
                ret = self.format("({choices})", choices=inner)
            object.__setattr__(self, 'str_cache', ret)
            return ret
        else:
            return self.str_cache

    def __str__(self) -> str:
        return self.to_str(highlight=-1)

    @property
    def complexity(self) -> float:
        return 1 + max(opt.complexity for opt in self.options)

    def _children(self, *, lazy_cache: MutableMapping[int, SyntaxSpec]) -> Tuple[SyntaxSpec, ...]:
        return self.options
    
@dataclass(frozen=True, slots=True)
class ManySpec(SyntaxSpec):
    spec: SyntaxSpec
    at_least: int
    at_most: Optional[int]
    str_cache: str | None = field(default=None, compare=False, hash=False, repr=False, init=False)

    def iso(self) -> Iso[Many, Tuple[Any, ...]]:
        def fwd(m: Many, ctx: Any) -> Tuple[Any, ...]:
            ret = m.value
            
            return ret
        def inv(v: Tuple[Any, ...], ctx: Any) -> Many:
            ret = Many(value=v if v is not None else tuple([]))
            
            return ret
        return Iso(fwd, inv)


    def syntax(self, cls: type[Syntax], cache: MutableMapping[SyntaxSpec, Syntax])-> Syntax:
        if self in cache:
            return cache[self]
        inner = self.spec.syntax(cls, cache=cache)
        ret = inner.many(at_least=self.at_least, at_most=self.at_most)
        cache[self] = ret = replace(ret, spec=self)
        return ret

    def to_str(self, highlight: int) -> str:
        if self.str_cache is None:
            if self.name:
                ret = self.name
            else:
                ret = self.format("*({spec})", spec=str(self.spec))
            object.__setattr__(self, 'str_cache', ret)
            return ret
        else:
            return self.str_cache
        
    def __str__(self) -> str:
        return self.to_str(highlight=-1)
    

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
    MAX_NAME_LENGTH: Optional[int] = field(compare=False, hash=False, repr=False)
    args: Tuple[Any, ...] = field(default_factory=tuple)
    kwargs: FrozenDict[str, Any] = field(default_factory=FrozenDict)
    str_cache: str | None = field(default=None, compare=False, hash=False, repr=False, init=False)

    
    def syntax(self, cls: type[Syntax], cache: MutableMapping[SyntaxSpec, Syntax])-> Syntax:
        if self in cache:
            return cache[self]
        ret = cls.factory(self.fname, *self.args, **self.kwargs)
        cache[self] = ret = replace(ret, spec=self)
        return ret
    
    def to_str(self, highlight: int) -> str:
        if self.str_cache is None:
            if self.name or not (self.kwargs or self.args):
                ret = self.name or self.fname
            else:
                parts = []
                for a in self.args:
                    s = str(a)
                    if self.MAX_NAME_LENGTH is not None and len(s) > self.MAX_NAME_LENGTH:
                        s = s[:self.MAX_NAME_LENGTH-3] + "..."
                    parts.append(s)
                args = ','.join(parts)
                kwparts = []
                for k, v in self.kwargs.items():
                    if v is not None:
                        s = str(v)
                        if self.MAX_NAME_LENGTH is not None and len(s) > self.MAX_NAME_LENGTH:
                            s = s[:self.MAX_NAME_LENGTH-3] + "..."
                        kwparts.append(f"{k}={s}")
                kwargs = ', '.join(kwparts)
                if args and kwargs:
                    ret = self.format("{fname}({args}, {kwargs})", fname=self.fname, args=args, kwargs=kwargs)
                elif args:
                    ret = self.format("{args}", args=args)
                elif kwargs:
                    ret = self.format("{kwargs}", kwargs=kwargs)
                else:
                    ret = self.fname
            object.__setattr__(self, 'str_cache', ret)
            return ret
        else:
            return self.str_cache

    def __str__(self)->str:
        return self.to_str(highlight=-1)

    @property
    def complexity(self) -> float:
        return 1
    
@dataclass
class LazyState(Generic[A, S]):
    
    # thunk returns a Syntax[A, S], the original callable passed to Syntax.lazy
    thunk: Callable[[], Syntax[A, S]]
    # cached resolved Syntax; excluded from comparisons
    _cached_syntax: Optional[Syntax[A, S]] = field(default=None, init=False, repr=False, compare=False)
    # cache algebras per (alg, kwargs_key). excluded from comparisons
    _inner_algebras_cache: Dict[Tuple[Type[Algebra], Tuple[Tuple[str, Any], ...]], Algebra[A, S]] = field(default_factory=dict, init=False, repr=False, compare=False)
    _algebras_cache: Dict[Tuple[Type[Algebra], Tuple[Tuple[str, Any], ...]], Algebra[A, S]] = field(default_factory=dict, init=False, repr=False, compare=False)


    def __hash__(self) -> int:
        return hash((self.thunk))
    
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, LazyState):
            return False
        return self.thunk == other.thunk

    @property
    def is_resolved(self) -> bool:
        return self._cached_syntax is not None

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

    def __call__(self, alg_cls: Type[Algebra], **global_kwargs) -> Algebra[A, S]:
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
        algebra = alg_cls.lazy(algebra_lazy_f)
        self._algebras_cache[key] = algebra
        
        return algebra
        

@dataclass(frozen=True, slots=True, weakref_slot=True)
class Syntax(Generic[A, S]):
    """
    The core signature of Syntax is take an Algebra Class and return an Algebra Instance.
    """
    
    alg_f: Callable[..., Algebra[A, S]]
    spec: SyntaxSpec = field(repr=False)

    is_root: bool = field(default=False, compare=False, hash=False, repr=False)



    print: ClassVar[DbgPrint] = DbgPrint.create()
    _lazy_facade_cache: ClassVar[ThreadLocalWeakValueDict[Callable[..., Any], Syntax]] = ThreadLocalWeakValueDict()

    
    @property
    def is_orelse(self) -> bool:
        return isinstance(self.spec, AltSpec)

    @property
    def is_lazy(self) -> bool:
        return isinstance(self.spec, LazySpec)

    @property
    def has_name(self) -> bool:
        return self.spec.name is not None



    @property
    def location(self) -> Optional[str]:
        return self.spec.location
    
    def __str__(self) -> str:
        return str(self.spec)

    def vis(self, depth: int = 3) -> Optional[SVGVisualization]:
        from syncraft.vis import syntax2svg
        return syntax2svg(self.spec, max_depth=depth)

    @classmethod
    def cdbg(cls, e: bool)->Any:
        # cls debug enable
        cls.print.enable(e)
        return cls

    def idbg(self, e: bool) -> Syntax[A, S]:
        # instance debug enable
        self.print.enable(e)
        return self

    
    @property
    def present(self) -> Syntax[A, S]:
        """Positive lookahead: ensure this syntax is present. Does not consume input."""
        return replace(self, alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).present)

    @property
    def absent(self) -> Syntax[type[Nothing], S]:
        """Negative lookahead: ensure this syntax is absent. Does not consume input."""
        return replace(self, alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).absent) # type: ignore


    @classmethod
    def set(cls, **attrs: Any) -> Type[Syntax]:
        return type(cls.__name__, (cls,), {SYNCRAFT_CONFIG_KEY: attrs})

    @classmethod
    def get(cls, key: str) -> Any:
        cfg = getattr(cls, SYNCRAFT_CONFIG_KEY, {})
        return cfg.get(key, None)

    def __call__(self, alg: Type[Algebra], **global_kwargs) -> Algebra[A, S]:
        cfg = getattr(self.__class__, SYNCRAFT_CONFIG_KEY, {})
        return self.alg_f(alg, **(cfg | global_kwargs)).with_syntax(self)
    

    def update_meta_in_place(self, *, name: None | str, file: None | str, line: None | int, func: None | str, _location:bool) -> Syntax[A, S]:
        """
        Update the metadata of this syntax in place. Use with caution.
        ️⚠️ Mutates the internal state of a frozen dataclass! ⚠️
        ONLY used in Grammar to set names on auto-named syntaxes.
        Args:
            name: New name to set.
            file: New file to set.
            line: New line to set.
            func: New function to set.
        """
        self.spec.update_meta_in_place(name=name, file=file, line=line, func=func, _location=_location)
        return self


    def _named(self, *, name: None | str, file: None | str, line: None | int, func: None | str) -> Syntax[A, S]:
        return replace(self, spec=self.spec.named(name=name, file=file, line=line, func=func, _location=True))         

    def as_root(self) -> Syntax[A, S]:
        return replace(self, is_root=True)


    def named(self, name: str | None, *, level:int=0, _location:bool=True) -> Syntax[A, S]:
        return replace(self, spec=self.spec.named(name=name, file=get_file(level+1), line=get_line(level+1), func=get_func(level+1), _location=_location))

    def walk(self, *, max_depth: Optional[int] = None) -> Iterator[Tuple[int, SyntaxSpec]]:
        return self.spec.walk(max_depth=max_depth)

    def graph(
        self,
        *,
        max_depth: Optional[int] = None,
    ) -> Graph[SyntaxSpec]:
        return self.spec.graph(max_depth=max_depth)

    ######################################################## value transformation ########################################################
    def map(self, f: Callable[..., B]) -> Syntax[B, S]:
        """Map the produced value while preserving state and metadata.

        Args:
            f: Function mapping value A to B.

        Returns:
            Syntax yielding B with the same resulting state.
        """
        return replace(self, alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).map(f)) # type: ignore
    
    def imap(self, f: Callable[..., A]) -> Syntax[A, S]:
        return replace(self, alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).imap(f)) # type: ignore

    def iso(self, iso: Iso[A, B]) -> Syntax[B, S]:
        """Isomorphically map values, preserving round-trip info.

        Args:
            iso: Iso mapping A <-> B.

        Returns:
            Syntax yielding B with state alignment preserved.
        """
        return replace(self, alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).iso(iso)) # type: ignore

    def bimap(self, f: Callable[..., B], i: Callable[..., A]) -> Syntax[B, S]:
        """Bidirectionally map values with an inverse, keeping round-trip info.

        Applies f to the value and adjusts internal state via inverse i so
        generation/parsing stay in sync.

        Args:
            f: Forward mapping A -> B.
            i: Inverse mapping B -> A applied to the state.

        Returns:
            Syntax yielding B with state alignment preserved.
        """
        return replace(self, alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).bimap(f, i)) # type: ignore
    
    def map_error(self, f: Callable[[Optional[Any]], Any]) -> Syntax[A, S]:
        """Transform the error payload when this syntax fails.

        Args:
            f: Function applied to the error payload of Left.

        Returns:
            Syntax that preserves successes and maps failures.
        """
        return replace(self, alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).map_error(f))         
    
    def many(self, *, at_least: int = 0, at_most: Optional[int] = None) -> Syntax[Tuple[A, ...], S]:
        """Repeat this syntax and collect results into Many.

        Repeats greedily until failure or no progress. Enforces bounds.

        Args:
            at_least: Minimum number of matches (default 0).
            at_most: Optional maximum number of matches.

        Returns:
            Syntax producing Many of values.
        """
        spec = ManySpec(spec=self.spec, 
                        at_least=at_least, 
                        at_most=at_most, 
                        name=self.spec.name, 
                        file=self.spec.file, 
                        line=self.spec.line, 
                        func=self.spec.func)
        
        def alg_f(cls: type[Algebra], **global_kwargs) -> Algebra[Many, S]:
            return self(cls, **global_kwargs).many(at_least=at_least, at_most=at_most)
        iso = Iso() if self.get('no_iso') else spec.iso()
        return replace(self, alg_f = alg_f, spec = spec).iso(iso) # type: ignore
                       
    

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
              dbg: Callable[[Syntax[A, S], S, Optional[S], A | Any, List[Tuple[Syntax[Any, S], int, int| None]]], None] | Any = None,
              *,
              show_stack: bool = True,
              only_fail: bool = False,
              only_success: bool = False,
              papuse: bool = False,
              level:int = 0) -> Syntax[A, S]:
        file=get_file(level+1)
        line=get_line(level+1)
        def default_dbg(syn: Syntax[A, S], state: S, new_state: Optional[S], value: A | Any, stack: List[Tuple[Syntax[Any, S], int, int| None]])->None:
            if new_state is not None and only_fail:
                return
            if new_state is None and only_success:
                return
            null = new_state is not None and new_state.cache_key == state.cache_key

            sign = f"{RED}\u2718{RESET}" if new_state is None else f"{GREEN}\u2714{RESET}"
            print('=' * 20, "DEBUG", sign, dbg if dbg is not None else "@", f"{file}:{line}", '=' * 20)
            print(f"       Syntax: {syn.spec}")
            print(f"  Input State: {state.str_input(False)}")
            if new_state is not None:
                print(f"    New State: {new_state.str_input(False) if not null else '< NO CHANGE >'}")
            indent = " " * 15
            if isinstance(value, Error):
                depth: int | None = None
                if value.state:
                    depth = value.state.cache_key - state.cache_key
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
            if papuse:
                input("Press Enter to continue...")


        xdbg: Callable[[Syntax[A, S], S, Optional[S], A | Any, List[Tuple[Syntax[Any, S], int, int| None]]], None] | Any = dbg if callable(dbg) else default_dbg
        return replace(self, alg_f = lambda acls, **global_args: self(acls, **global_args).debug(dbg=xdbg))
            
    ############################################################### facility combinators ############################################################
    def between(self, left: Syntax[B, S], right: Syntax[C, S]) -> Syntax[A, S]:
        return self.seq(left , +self , right).bimap(lambda t, _: t[0], lambda v, _: (v,))

    def sep_by(self, sep: Syntax[B, S]) -> Syntax[Tuple[A, ...], S]:
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
        def fwd(t: Tuple[A, Tuple[Tuple[A], ...] ], ctx: Any) -> Tuple[A, ...]:
            first, rest = t
            return tuple([first] + [x[0] for x in rest])

        def inv(v: Tuple[A, ...], ctx: Any) -> Tuple[A, Tuple[Tuple[A], ...]]:
            first, *rest = v
            return (first, tuple([ (x,) for x in rest]))            

        return (self + (sep >> self).many()).bimap(fwd, inv)


    def parens(
        self,
        sep: Syntax[C, S],
        open: Syntax[B, S],
        close: Syntax[D, S],
    ) -> Syntax[Tuple[A, ...], S]:
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
    def optional(self) -> Syntax[Alt, S]:
        """Make this syntax optional.

        Returns a OrElse of the value or Nothing when absent.

        Returns:
            Syntax producing OrElse of value or Nothing.
        """
        return (self | self.success(Nothing)).named(f"{str(self.spec)}?", _location=False)
        
    # @property
    # def cut(self) -> Syntax[A, S]:
    #     """Commit this branch: on failure, prevent trying alternatives.

    #     Wraps the underlying algebra's cut.

    #     Returns:
    #         Syntax that marks downstream failures as committed.
    #     """
    #     return replace(self, alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).cut())


    ###################################################### operator overloading #############################################
    def __floordiv__(self, other: Syntax[B, S]) -> Syntax[Tuple[A, ...], S]:
        """Then-left: run both and prefer the left in the result kind.

        Returns Then(kind=LEFT) with both left and right values.

        Args:
            other: Syntax to run after this one.

        Returns:
            Syntax producing Then(left, right, kind=LEFT).
        """
        return self.seq(+self, -other)                   


    def __rfloordiv__(self, other: Syntax[B, S]) -> Syntax[Tuple[B, ...], S]:

        return other.__floordiv__(self)

    def __add__(self, other: Syntax[B, S]) -> Syntax[Tuple[Any, ...], S]:
        """Then-both: run both and keep both values.

        Returns Then(kind=BOTH).

        Args:
            other: Syntax to run after this one.

        Returns:
            Syntax producing Then(left, right, kind=BOTH).
        """
        return self.seq(+self, +other)
    
    def __radd__(self, other: Syntax[B, S]) -> Syntax[Tuple[Any, ...], S]:

        return other.__add__(self)

    def __rshift__(self, other: Syntax[B, S]) -> Syntax[Tuple[B, ...], S]:
        """Then-right: run both and prefer the right in the result kind.

        Returns Then(kind=RIGHT).

        Args:
            other: Syntax to run after this one.

        Returns:
            Syntax producing Then(left, right, kind=RIGHT).
        """
        return self.seq(-self, +other)



    def __rrshift__(self, other: Syntax[B, S]) -> Syntax[Tuple[A, ...], S]:

        return other.__rshift__(self)

    def __or__(self, other: Syntax[B, S]) -> Syntax[Alt, S]:
        return self.alt(self, other)
        
    def __ror__(self, other: Syntax[Any, S]) -> Syntax[Alt, S]:

        return self.__or__(other)


    def __pos__(self) -> Tuple[Syntax[A, S], bool]:
        return (self, True)

    def __neg__(self) -> Tuple[Syntax[A, S], bool]:
        return (self, False)
    
    def __invert__(self) -> Syntax[Alt, S]:
        """Syntactic sugar for optional() (tilde operator)."""
        return self.optional

    ######################################################################## data processing combinators #########################################################
    
    def bind(self, **f: Callable[[Any, Any], Any]) -> Syntax[A, S]:
        return replace(self, alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).bind(**f)) 
    
    def to(self, a: Callable[..., A], b: Callable[..., B]) -> Syntax[B, S]:
        return self.iso(Iso.derive(a, b)) 

    def check(self, pred: Callable[..., bool], *, forward: bool = True, level:int = 0, message: str | None = None) -> Syntax[A, S]:
        file = get_file(level+1)        
        line = get_line(level+1)
        f = CallWith(pred)
        names = f.missing_args[1:]
        def check_preds(value: Any, ctx: FrozenDict[str, Any]) -> Any:
            vars = [ctx.get(name, ...) for name in names]
            if not pred(value, *vars):
                if message is None:
                    raise DataError(f"Predicate {pred} (at {file}:{line}) failed for value {value} with context {ctx}\n{message}", soft_failure=True)                    
                else:
                    raise DataError(message.format(value, ctx), soft_failure=False)
            return value
        return self.map(check_preds) if forward else self.imap(check_preds)
        

    @classmethod
    def fail(cls, error: B) -> Syntax[B, S]:
        return cls.factory('fail', error=error)

    @classmethod
    def success(cls, value: B) -> Syntax[B, S]:
        return cls.factory('success', value=value)


    @classmethod
    def alt(cls, *parsers: Syntax[Any, S]) -> Syntax[Alt, S]:
        all_parsers = parsers
        def alt_f(acls: Type[Algebra], **global_kwargs: Any) -> Algebra:
            algs = [p(acls, **global_kwargs) for p in all_parsers]
            return acls.alt(*algs)
        spec = AltSpec(options=tuple(p.spec for p in all_parsers), name=None, file=None, line=None, func=None)
        iso = Iso() if cls.get('no_iso') else spec.iso()
        return cls(alg_f=alt_f, spec=spec).iso(iso) # type: ignore
    
    @classmethod
    def seq(cls, *steps: Syntax[Any, S] | Tuple[Syntax[Any, S], bool]) -> Syntax[Tuple[Any, ...], S]:
        def infer_default_keep(steps: Tuple[Syntax[Any, S] | Tuple[Syntax[Any, S], bool | str], ...]) -> bool:
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
                return infered_default
            else:
                return True
            
        default:bool = infer_default_keep(steps)
        syntaxes = [X if isinstance(X, tuple) else (X, default) for X in steps]
        def seq_f(acls: Type[Algebra], **global_kwargs: Any) -> Algebra:
            algs = [(step(acls, **global_kwargs), keep) for step, keep in syntaxes]
            return acls.seq(*algs)
        spec = SeqSpec(steps=tuple((step.spec, keep) for step, keep in syntaxes), name=None, file=None, line=None, func=None)
        iso = Iso() if cls.get('no_iso') else spec.iso()
        return cls(alg_f=seq_f, spec=spec).iso(iso) # type: ignore

    @classmethod
    def lazy(cls, thunk: Callable[[], Syntax[A, S]]) -> Syntax[A, S]:
        facade_cache = cls._lazy_facade_cache
        existing = facade_cache.get(thunk)
        if existing is not None:
            return existing  

        helper = LazyState(thunk=thunk)
        spec = LazySpec(lazy_state=helper, name=None, file=None, line=None, func=None)
        def lazy_alg_f(acls: Type[Algebra], **global_kwargs: Any) -> Algebra:
            return helper(acls, **global_kwargs)
        iso = Iso() if cls.get('no_iso') else spec.iso()
        facade = cls(alg_f=lazy_alg_f, spec=spec).iso(iso) # type: ignore
        facade_cache[thunk] = facade
        
        return facade
    

    @classmethod
    def factory(cls, name: str, *args:Any, **kwargs: Any) -> Syntax:
        def factory_run(acls: Type[Algebra], **global_kwargs: Any) -> Algebra:
            method = getattr(acls, name, None)
            if method is None or not callable(method):
                raise SyncraftError(f"Method {name} is not defined in {acls.__name__}", offender=method, expect='callable')
            result = CallWith(method, *args, **(global_kwargs | kwargs))()
            return cast(Algebra, result)
        spec = LexSpec(fname=name, args=args, kwargs=FrozenDict(kwargs), MAX_NAME_LENGTH=cls.get('MAX_NAME_LENGTH'), name=None, file=None, line=None, func=None)
        iso = Iso() if cls.get('no_iso') else spec.iso()
        return cls(factory_run, spec=spec).iso(iso) # type: ignore
    
    @classmethod
    def eof(cls) -> Syntax:
        return cls.factory('eof')
    
    @classmethod
    def lex(cls, builder: Builder | TokenSpec) -> Syntax:
        return cls.factory('lex', builder)

    @classmethod
    def lexer_transformer(cls) -> Callable[[Builder], Builder] | None:
        return cls.get('lexer_transformer')    
    
    @classmethod
    def set_lexer_transformer(cls, transformer: Callable[[Builder], Builder]) -> Type[Syntax]:
        return cls.set(lexer_transformer=transformer)

    @classmethod
    def re(cls, pattern: str, lexer_transformer: Callable[[Builder], Builder] | None = None, **kwargs: Any) -> Syntax:
        # local import to avoid circular dependency
        from syncraft.regex import builder
        b = builder(pattern).set(**kwargs)
        if not callable(lexer_transformer):
            lexer_transformer = cls.lexer_transformer()
        if callable(lexer_transformer):
            b = lexer_transformer(b)
        return cls.lex(b)
    
    @classmethod
    def lit(cls, txt: str | bytes, lexer_transformer: Callable[[Builder], Builder] | None = None, **kwargs: Any) -> Syntax:
        b: Builder[Any]= Builder.lit(txt).set(**kwargs)
        if not callable(lexer_transformer):
            lexer_transformer = cls.lexer_transformer()
        if callable(lexer_transformer):
            b = lexer_transformer(b)
        return cls.lex(b)

    @classmethod
    def tok(cls, *txt: str | Pattern[str], case_sensitive: bool = True, **kwargs: Any) -> Syntax:
        tkspec: TokenSpec | None = TokenSpecBase.from_kwargs(*txt, case_sensitive=case_sensitive, **kwargs)
        assert tkspec is not None, "TokenSpecBase.from_kwargs returned None"
        return cls.lex(tkspec)

    @classmethod
    def from_spec(cls, spec: SyntaxSpec)->Syntax:
        c: Dict[SyntaxSpec, Syntax] = {}
        return spec.syntax(cls, cache=c)
    
    @classmethod
    def from_graph(cls, graph: Graph[SyntaxSpec]) -> Syntax:
        c: Dict[SyntaxSpec, Syntax] = {}
        return graph.root.syntax(cls, cache=c)
    
class RunnerProtocol(Protocol, Generic[A, S]):
    def algebra(self, 
                syntax: Syntax[A, S],
                alg_cls: Type[Algebra[A, S]]) -> Algebra[A, S]: 
        return syntax(alg_cls)

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
            cache = cache or Cache()
            parser_gen = parser.run(state, cache=cache)
            try:
                result = next(parser_gen)
                while True:
                    if isinstance(result, Incomplete):
                        pending_state = self.resume(result.state, cursor)
                        if cache is not None:
                            cache.gc(pending_state.unused_cache_key())                    
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
        alg = self.algebra(syntax=syntax, alg_cls=alg_cls)  
        yield from self.run(alg, state, cursor, cache, once=once)

    def once(self, 
             syntax: Syntax[A, S], 
             alg_cls: Type[Algebra[A, S]],
             state: Optional[S],
             cursor: Optional[StreamCursor[Any]],
             cache: Optional[Cache[Any]]
             ) -> Tuple[Any, None | S]:
        gen = self(syntax, alg_cls, state, cursor, cache, once=True)
        return next(gen)
        








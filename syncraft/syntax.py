from __future__ import annotations

import keyword

import math
from enum import Enum
from typing import (
    Optional, Any, TypeVar, Generic, Callable, Tuple, cast, Hashable,
    Type, List, Dict, Set, Iterator, ClassVar, Protocol, Generator, MutableMapping, TYPE_CHECKING,
    Pattern, Literal, overload
)

from dataclasses import dataclass, field, replace
from syncraft.lexerprotocol import LexerBuilder
if TYPE_CHECKING:
    from syncraft.format import LayoutDoc
    from syncraft.vis import SVGVisualization

from syncraft.utils import file as get_file, line as get_line, func as get_func, FrozenDict, CallWith, ThreadLocalWeakValueDict, DbgPrint
from syncraft.algebra import Algebra, Either, Left, Right, SYNCRAFT_CONFIG_KEY, Error, EntryCategory
from syncraft.cache import Cache, Incomplete
from syncraft.bimap import Bindable, Iso, DataError, Match, Env
from syncraft.ast import Many, Nothing, SyncraftError, Seq, Alt, Lazy, Unknown, _SingletonBase
from syncraft.input import StreamCursor
from syncraft.fa import Builder
from syncraft.token import TokenSpec, TokenSpecBase
import threading


Tag = str | Enum | None

GREEN = "\033[92m"
RESET = "\033[0m"
RED = "\033[91m"
UNDERLINE = "\033[4m"
ITALIC = "\033[3m"

OPEN_TOP="\u231C"
CLOSE_TOP="\u231D"
OPEN="\u2e24"
CLOSE="\u2e25"

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
    """
    Base class for syntax specifications.

    Subclasses represent grammar combinators (e.g. Seq, Alt, Many, Lex, Lazy).
    SyntaxSpec is immutable and hashable; metadata fields are excluded from
    comparisons and hashing.

    A SyntaxSpec records enough structural information to reconstruct a
    corresponding Syntax object via syntax(cls, cache).
    Caveat:
        SyntaxSpec stores grammar structure only. It does not store user-level
        data/operational transformations (e.g. iso/map/bimap/bind/check/debug).
        Reconstructed Syntax objects therefore keep grammar semantics but do not
        recover those transformation layers.
    """
    name: Optional[str] = field(compare=False, hash=False)
    file: Optional[str] = field(compare=False, hash=False, repr=False) 
    line: Optional[int] = field(compare=False, hash=False, repr=False)
    func: Optional[str] = field(compare=False, hash=False, repr=False)

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
            try:
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
            except IndexError as e:
                raise DataError(f"SeqSpec expected {sum(1 for _, include in self.steps if include)} elements, got {len(v)}", soft_failure=False) from e
        def fwd(s: Seq, ctx: Any) -> Tuple[Any, ...]:
            try:
                vs = []
                index = 0
                for spec, include in self.steps:
                    if include:
                        vs.append(s.value[index][0])
                    index += 1
                ret = tuple(vs)
                return ret
            except IndexError as e:
                raise DataError(f"Seq value has too few elements. Expected at least {len(self.steps)} elements, got {len(s.value)}", soft_failure=False) from e
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
                        step_str = f"{OPEN}{step_str}{CLOSE}"
                    if index == highlight:
                        step_str = f"{OPEN_TOP}{step_str}{CLOSE_TOP}"
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

    @property
    def arity(self) -> int:
        return sum(1 for _, keep in self.steps if keep)
    
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
                choices = [str(opt) if i != highlight else f"{OPEN_TOP}{str(opt)}{CLOSE_TOP}" for i, opt in enumerate(self.options)]
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
    extra_info: FrozenDict[str, Any] = field(default_factory=FrozenDict)
    str_cache: str | None = field(default=None, compare=False, hash=False, repr=False, init=False)

    @classmethod
    def should_ignore(cls, data: Any) -> bool:
        from syncraft.lexer import LocalLexerBuilder, GlobalLexerBuilder
        return isinstance(data, (LocalLexerBuilder, GlobalLexerBuilder))
    
    def syntax(self, cls: type[Syntax], cache: MutableMapping[SyntaxSpec, Syntax])-> Syntax:
        if self in cache:
            return cache[self]
        ret = cls.factory(self.fname, *self.args, **self.kwargs)
        cache[self] = ret = replace(ret, spec=self)
        return ret
    
    @property
    def pattern(self) -> str | None:
        for x in self.args:
            if isinstance(x, str):
                return x
        for k, v in self.kwargs.items():
            if isinstance(v, str) and k != 'type':
                return v
        for k, v in self.extra_info.items():
            if isinstance(v, str) and k != 'type':
                return v
        return None


    def to_str(self, highlight: int) -> str:
        if self.str_cache is None:
            if self.name or not (self.kwargs or self.args or self.extra_info):
                ret = self.name or self.fname
            else:
                parts = []
                for a in self.args:
                    if not LexSpec.should_ignore(a):
                        s = str(a)
                        if self.MAX_NAME_LENGTH is not None and len(s) > self.MAX_NAME_LENGTH:
                            s = s[:self.MAX_NAME_LENGTH-3] + "..."
                        parts.append(s)
                args = ','.join(parts)
                kwparts = []
                all_info = {**self.kwargs, **self.extra_info}
                for k, v in all_info.items():
                    if v is not None and not LexSpec.should_ignore(v):
                        # Use repr() for strings to properly escape backslashes and special chars
                        s = repr(v) if isinstance(v, str) else str(v)
                        if self.MAX_NAME_LENGTH is not None and len(s) > self.MAX_NAME_LENGTH:
                            s = s[:self.MAX_NAME_LENGTH-3] + "..."
                        kwparts.append(f"{k}={s}")
                kwargs = ', '.join(kwparts)


                if args and kwargs:
                    ret = self.format("{fname}({args}, {kwargs})", fname=self.fname, args=args, kwargs=kwargs)
                elif args:
                    ret = self.format("({args})", args=args)
                elif kwargs:
                    ret = self.format("({kwargs})", kwargs=kwargs)
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
    alg_f: Callable[..., Algebra[A, S]] is the function that constructs the algebra instance for this syntax.
    spec: SyntaxSpec is the metadata/specification of this syntax, which can be used for visualization, debugging, and reconstructing 
          the syntax via spec.syntax(Syntax, cache). 
    is_root: whether this syntax is a root syntax (i.e. directly used in Grammar rules). The entry point of a Grammar
    can_normalize: whether this syntax can be normalized. seq and alt combinators will normalize their children if they are marked as can_normalize, 
                   which allows normalization to be applied selectively to certain parts of the syntax tree.
                   Normalization of alt makes 
                    (A | B) | C == A | (B | C) => A or B or C
                   and normalization of seq makes 
                    (A + B) + C == A + (B + C) => (A, B, C)
                    (A >> B) >> C == A >> (B >> C) => (C,) => C
                    (A // B) // C == A // (B // C) => (A,) => A
                    (A,) => A
    print: a class-level DbgPrint instance for debug printing. Use Syntax.cdbg(True) to enable debug printing for all Syntax instances, 
           or use Syntax(...).idbg(True) to enable debug printing for a specific instance.
    _lazy_facade_cache: a class-level cache for storing Syntax instances created as facades for LazySpecs, keyed by the LazySpec's thunk. 
                        This allows different LazySpecs that share the same thunk to reuse the same Syntax facade, 
                        which is important for keeping the correspondence between Syntax and Algebra instances across lazy combinators.
    
    CAVEAT: Syntax objects reconstructed from SyntaxSpec via spec.syntax(Syntax, cache) will lost its data transformation or operational logic 
            (e.g. iso, map, imap, bimap, to, bind, check, etc.) since SyntaxSpec only records the grammatic structure of the syntax, 
            not the data transformation and operational logic.
                   
    """
    
    alg_f: Callable[..., Algebra[A, S]]
    spec: SyntaxSpec = field(repr=False)

    is_root: bool = field(default=False, compare=False, hash=False, repr=False)
    can_normalize: bool = field(default=True, compare=False, hash=False, repr=False)
    # the alt and seq combinators need to keep track of their children for normalization
    _children: Tuple[Syntax[Any, S], ...] | None = field(default=None, compare=False, hash=False, repr=False)

    print: ClassVar[DbgPrint] = DbgPrint.create()
    _lazy_facade_cache: ClassVar[ThreadLocalWeakValueDict[Callable[..., Any], Syntax]] = ThreadLocalWeakValueDict()

    
    @property
    def atomic(self) -> Syntax[A, S]:
        """Mark this syntax as atomic, which means it will not be flattened during normalization."""
        return replace(self, can_normalize=False)

    @property
    def is_orelse(self) -> bool:
        """Return `True` when this syntax node is an alternative (`AltSpec`)."""
        return isinstance(self.spec, AltSpec)

    @property
    def is_lazy(self) -> bool:
        """Return `True` when this syntax node is lazy (`LazySpec`)."""
        return isinstance(self.spec, LazySpec)

    @property
    def has_name(self) -> bool:
        """Return whether this syntax node has a display/debug name."""
        return self.spec.name is not None



    @property
    def location(self) -> Optional[str]:
        """Return source location metadata if available."""
        return self.spec.location
    
    def __str__(self) -> str:
        return str(self.spec)

    def vis(self, depth: int = 3) -> Optional[SVGVisualization]:
        """Render an SVG visualization of this syntax subtree."""
        from syncraft.vis import syntax2svg
        return syntax2svg(self.spec, max_depth=depth)


    @classmethod
    def cdbg(cls, e: bool)->Any:
        """Enable or disable class-level debug printing for all syntax instances."""
        # cls debug enable
        cls.print.enable(e)
        return cls

    def idbg(self, e: bool) -> Syntax[A, S]:
        """Enable or disable debug printing for this syntax instance only."""
        # instance debug enable
        self.print.enable(e)
        return self

    
    @property
    def present(self) -> Syntax[A, S]:
        """Positive lookahead: ensure this syntax is present. Does not consume input."""
        return replace(
            self,
            alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).present,
            can_normalize=self._updated_can_normalize(block_normalization=True),
        )

    @property
    def absent(self) -> Syntax[type[_SingletonBase], S]:
        """Negative lookahead: ensure this syntax is absent. Does not consume input."""
        return replace(
            self,
            alg_f=cast(Callable[..., Algebra[A, S]], lambda cls, **global_kwargs: self(cls, **global_kwargs).absent),
            can_normalize=self._updated_can_normalize(block_normalization=True),
        ) # type: ignore


    @classmethod
    def set(cls, **attrs: Any) -> Type[Syntax]:
        """Create a configured `Syntax` subclass.

        This is used to attach class-level runtime configuration flags
        (for example lexer builders or normalization options) without mutating
        the base class globally.

        Returns:
            A new subclass of `Syntax` with merged configuration.
        """
        return type(cls.__name__, (cls,), {SYNCRAFT_CONFIG_KEY: attrs})

    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        """Return all class-level Syncraft configuration values."""
        return getattr(cls, SYNCRAFT_CONFIG_KEY, {})

    @classmethod
    def get(cls, key: str) -> Any:
        """Return a class-level configuration value by key, or `None`."""
        cfg = getattr(cls, SYNCRAFT_CONFIG_KEY, {})
        return cfg.get(key, None)

    def __call__(self, alg: Type[Algebra], **global_kwargs) -> Algebra[A, S]:
        """Materialize this syntax into an algebra instance.

        Args:
            alg: Algebra class to instantiate (`Parser`, `Generator`, etc.).
            **global_kwargs: Runtime options forwarded to algebra builders.

        Returns:
            Bound algebra instance associated with this syntax node.
        """
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
        """Return a copy marked as grammar root entry."""
        return replace(self, is_root=True)


    def named(self, name: str | None, *, level:int=0, _location:bool=True) -> Syntax[A, S]:
        """Return a copy with an explicit display/debug name.

        Args:
            name: Rule/syntax name, or `None` to clear.
            level: Stack-frame offset used for source-location metadata.
            _location: Whether to update file/line/function location.
        """
        return replace(self, spec=self.spec.named(name=name, file=get_file(level+1), line=get_line(level+1), func=get_func(level+1), _location=_location))

    def walk(self, *, max_depth: Optional[int] = None) -> Iterator[Tuple[int, SyntaxSpec]]:
        """Iterate over syntax spec nodes as `(depth, spec)` pairs."""
        return self.spec.walk(max_depth=max_depth)

    def graph(
        self,
        *,
        max_depth: Optional[int] = None,
    ) -> Graph[SyntaxSpec]:
        """Build a graph view of this syntax specification tree."""
        return self.spec.graph(max_depth=max_depth)

    def _updated_can_normalize(self, *, block_normalization: bool) -> bool:
        return False if block_normalization else self.can_normalize

    ######################################################## value transformation ########################################################
    def format(self,
               *,
               breaks: Literal['never', 'optional', 'required'] = 'never',
               indent: int = 0,
               right: bool = True,
               ) -> Syntax["LayoutDoc", S]:
        """Attach declarative formatting metadata to this grammar subtree.

        ``Syntax.format(...)`` is the typed, validated entry point for the
        formatting pipeline. It annotates this node with a ``FormatSpec`` and
        lowers generated values into ``LayoutDoc`` so a renderer can apply
        width-sensitive line breaking and indentation.

        Core rendering semantics
        ------------------------
        breaks:
            Controls line-break strategy:
            - ``'never'`` (default): no width-sensitive grouping.
            - ``'optional'``: wrap in a ``Group``; render flat when it fits,
              otherwise break across lines.
            - ``'required'``: reserved for forced-break semantics; not yet
              implemented.
        indent:
            Extra indentation depth (non-negative integer) applied to nested
            breaks within this subtree. Used by ``Nest`` in the layout tree.
        
        right:
            Whether to attach line breaks to the right (default) or left of this node.
            This controls whether breaks introduced by this formatting node will prefer to 
            break before (right=False) or after (right=True) this node when breaking.

        """
        from syncraft.format import Nest, Group, Concat, Line, LayoutDoc

        def to_doc(ast: Any) -> "LayoutDoc":
            doc = LayoutDoc.from_ast(ast)
            if breaks == 'optional':
                body: LayoutDoc = Concat(parts=(doc, Line())) if right else Concat(parts=(Line(), doc))
                if indent > 0:
                    body = Nest(ast=ast, body=body, level=indent)
                return Group(ast=ast, body=body)
            elif breaks == 'required':
                body = Concat(parts=(doc, Line(flat="\n"))) if right else Concat(parts=(Line(flat="\n"), doc))
                if indent > 0:
                    body = Nest(ast=ast, body=body, level=indent)
                return Group(ast=ast, body=body)
            elif breaks == 'never':
                return Nest(ast=ast, body=doc, level=indent) if indent > 0 else doc
            else:
                raise SyncraftError(f"Invalid value for breaks: {breaks}", offender=breaks, expect="one of 'never', 'optional', 'required'")

        return cast(Syntax["LayoutDoc", S], self.fmt(to_doc, block_normalization=True))

    def fmt(self, f: Callable[..., B], *, block_normalization: bool = True) -> Syntax[B, S]:
        """Low-level formatting escape hatch.

        Prefer ``Syntax.format(...)`` for typed, validated formatting metadata.
        ``fmt`` remains available for advanced raw transformations.
        """
        return replace(
            self,
            alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).map(f, entry=EntryCategory.Format),
            can_normalize=self._updated_can_normalize(block_normalization=block_normalization),
        ) # type: ignore
    
    def map(self, f: Callable[..., B], *, block_normalization: bool = True) -> Syntax[B, S]:
        """Map the produced value while preserving state and metadata.

        Args:
            f: Function mapping value A to B.
            block_normalization: If True, prevents normalization of this node.
            block_normalization: If False, allows normalization to flatten. 

            normalization happens in seq and alt combinators when their children have can_normalize=True.
            If block_normalization is True, this syntax will be marked as can_normalize=False, 
            which prevents normalization from flattening this node. 
            If block_normalization is False, this syntax will keep its original can_normalize value, 
            allowing normalization to flatten it if it was originally can_normal

        Returns:
            Syntax yielding B with the same resulting state.
        Error Handling:
            If f raises an system exception during parsing, the exception will interrupt the parsing.
            If f raises a DataError(soft_failure=True) during parsing, the exception will be treated as a parsing failure and trigger backtracking.
        """
        return replace(
            self,
            alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).map(f, entry=EntryCategory.Parse),
            can_normalize=self._updated_can_normalize(block_normalization=block_normalization),
        ) # type: ignore
    
    def imap(self, f: Callable[..., A], *, block_normalization: bool = True) -> Syntax[A, S]:
        """Inversely map the input value while preserving state and metadata.
        Args: 
            THE SAME as map, but f maps B to A instead of A to B. 
        Returns:       
            Syntax yielding A with the same resulting state.
        Error Handling:
            THE SAME as map, but applies to the inverse mapping. 
            If f raises a system exception during generation, the exception will interrupt the generation.
            If f raises a DataError(soft_failure=True) during generation, the exception will be treated as a generation failure and trigger backtracking.
        """
        return replace(
            self,
            alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).imap(f, entry=EntryCategory.Generate),
            can_normalize=self._updated_can_normalize(block_normalization=block_normalization),
        ) # type: ignore

    def iso(self, iso: Iso[A, B], *, block_normalization: bool = True) -> Syntax[B, S]:
        """
        Isomorphically map values, preserving round-trip info.

        Args:
            iso: Iso mapping A <-> B.

        Returns:
            Syntax yielding B with state alignment preserved.
        """
        return replace(
            self,
            alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).iso(iso),
            can_normalize=self._updated_can_normalize(block_normalization=block_normalization),
        ) # type: ignore

    def bimap(self, f: Callable[..., B], i: Callable[..., A], *, block_normalization: bool = True) -> Syntax[B, S]:
        """
        Bidirectional data transformation with explicit forward and inverse functions.
        
        Use `bimap` for simple, direct value conversions where you can explicitly
        provide both directions (e.g., int ↔ str, encoding/decoding). This is the
        most straightforward transformation when both mappings are trivial.

        Args:
            f: Forward mapping A -> B (for parsing/reading).
            i: Inverse mapping B -> A (for generation/writing).
            block_normalization: Prevent flattening this node during normalization.

        Returns:
            Syntax yielding B during parsing, accepting B during generation.
            
        Example:
            >>> # Simple type conversion
            >>> number = S.rp(r"[0-9]+").bimap(int, str)
            >>> number.parse("42")  # -> 42 (int)
            >>> number.generate(42)  # -> "42" (str)
            >>>
            >>> # Encoding/decoding
            >>> base64_text = S.rp(r"[A-Za-z0-9+/=]+").bimap(
            ...     lambda s: base64.b64decode(s),
            ...     lambda b: base64.b64encode(b).decode()
            ... )
        """
        return replace(
            self,
            alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).bimap(f, i),
            can_normalize=self._updated_can_normalize(block_normalization=block_normalization),
        ) # type: ignore
    
    def map_error(self, f: Callable[[Optional[Any]], Any], *, block_normalization: bool = True) -> Syntax[A, S]:
        """
        Transform the error payload when this syntax fails.

        Args:
            f: Function applied to the error payload of Left.

        Returns:
            Syntax that preserves successes and maps failures.
        """
        return replace(
            self,
            alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).map_error(f),
            can_normalize=self._updated_can_normalize(block_normalization=block_normalization),
        )
    
    def many(self, *, at_least: int = 0, at_most: Optional[int] = None) -> Syntax[Tuple[A, ...], S]:
        """
        Repeat this syntax and collect results into Many.

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
        base = replace(self, alg_f=alg_f, spec=spec)  # type: ignore[arg-type]
        return base.iso(iso, block_normalization=False) # type: ignore
                       
    

    def on_fail(self, f: Callable[[Optional[Syntax[A, S]], S, Any], Either[Any, Tuple[Any, S]]] | None | Any, *, block_normalization: bool = True) -> Syntax[Any, S]:
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
        return replace(
            self,
            alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).on_fail(_on_fail),
            can_normalize=self._updated_can_normalize(block_normalization=block_normalization),
        )
    
    def on_success(self, f: Callable[[Optional[Syntax[A, S]], S, Tuple[A,S]], Either[Any, Tuple[Any, S]]] | None | Any, *, block_normalization: bool = True) -> Syntax[Any, S]:
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
        return replace(
            self,
            alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).on_success(_on_success),
            can_normalize=self._updated_can_normalize(block_normalization=block_normalization),
        )
    
    def debug(self, 
              dbg: Callable[[Syntax[A, S], S, Optional[S], A | Any, List[Tuple[Syntax[Any, S], int, int| None]]], None] | Any = None,
              *,
              show_stack: bool = True,
              only_fail: bool = False,
              only_success: bool = False,
              pause: bool = False,
              entry: EntryCategory = EntryCategory.Parse,
              level:int = 0) -> Syntax[A, S]:
        """Attach runtime debug tracing to this syntax.

        Args:
            dbg: Optional custom debug callback.
            show_stack: Include formatted call stack in default output.
            only_fail: Emit traces only for failures.
            only_success: Emit traces only for successes.
            pause: Pause for user input after each trace event.
            entry: Entry category for which to enable debug tracing.
            level: Stack-frame offset used for source metadata in debug output.
        
        Example:
            >>> syntax = Syntax.lit("a").debug()
            >>> # The default debug callback will print input state, success/failure, 
            >>> # and call stack for each parse attempt of "a".
        """
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
            if pause:
                input("Press Enter to continue...")


        xdbg: Callable[[Syntax[A, S], S, Optional[S], A | Any, List[Tuple[Syntax[Any, S], int, int| None]]], None] | Any = dbg if callable(dbg) else default_dbg
        return replace(self, 
                       alg_f = lambda acls, **global_args: self(acls, **global_args).debug(dbg=xdbg, entry=entry),
                       can_normalize=self._updated_can_normalize(block_normalization=True)
                       )
            
    ############################################################### facility combinators ############################################################
    def between(self, left: Syntax[B, S], right: Syntax[C, S]) -> Syntax[A, S]:
        """Parse `left`, then `self`, then `right`, returning `self` value."""
        return self.seq(-left, +self, -right)

    def sep_by(self, sep: Syntax[B, S], at_least:int = 1) -> Syntax[Tuple[A, ...], S]: # type: ignore
        """Parse this syntax separated by the given separator.
        
        Parses one or more occurrences of this syntax separated by ``sep`` and
        returns parsed elements as ``Tuple[A, ...]``.
        
        Args:
            sep: Separator syntax to use between elements.
            at_least: Minimum number of occurrences required.
        Returns:
            Syntax producing ``Tuple[A, ...]`` (separators are not included in
            the output value).
            
        Example:
            >>> from syncraft.syntax import Syntax
            >>> A = Syntax.lit("a")
            >>> comma = Syntax.lit(",")
            >>> syntax = A.sep_by(comma)
            >>> # Parses "a,a,a" and produces ('a', 'a', 'a')
        """
        def fwd(t: Tuple[A, Tuple[A, ...]], ctx: Any) -> Tuple[A, ...]:
            first, rest = t
            return tuple([first] + list(rest))

        def inv(v: Tuple[A, ...], ctx: Any) -> Tuple[A, Tuple[A, ...]]:
            first, *rest = v
            return (first, tuple(rest))            

        # Block normalization on self to prevent flattening when used in seq
        self_blocked = self.atomic
        ret1 = (self_blocked + (sep >> self_blocked).many()).bimap(fwd, inv)

        if at_least == 0:
            def fwd0(t: Any, ctx: Any) -> Tuple[A, ...]:
                assert isinstance(t, tuple) or t is Nothing
                return t if t is not Nothing else tuple() # type: ignore
            def inv0(v: Tuple[A, ...], ctx: Any) -> Any:
                assert isinstance(v, tuple)
                return v if v else Nothing
            return ret1.optional.bimap(fwd0, inv0)
        elif at_least == 1:
            return ret1
        else:
            raise SyncraftError(f"at_least must be 1 or 0, got {at_least}", offender=at_least, expect="non-negative integer with 0 or 1")


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
    def optional(self) -> Syntax[Any, S]:
        """Make this syntax optional.

        Parses this syntax if present; otherwise returns ``Nothing``.

        Returns:
            Syntax producing either the parsed value or ``Nothing``.
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
    def __floordiv__(self, other: Syntax[B, S]) -> Syntax[Any, S]:
        """Sequence two syntaxes and keep the left value.

        Args:
            other: Syntax to run after this one.

        Returns:
            Syntax producing the left value.
        """
        return self.seq(+self, -other)                   


    def __rfloordiv__(self, other: Syntax[B, S]) -> Syntax[Any, S]:

        return other.__floordiv__(self)

    def __add__(self, other: Syntax[B, S]) -> Syntax[Any, S]:
        """Sequence two syntaxes and keep both values.

        Args:
            other: Syntax to run after this one.

        Returns:
            Syntax producing a combined tuple-like value per ``seq`` isomorphism.
        """
        return self.seq(+self, +other)
    
    def __radd__(self, other: Syntax[B, S]) -> Syntax[Any, S]:

        return other.__add__(self)

    def __rshift__(self, other: Syntax[B, S]) -> Syntax[Any, S]:
        """Sequence two syntaxes and keep the right value.

        Args:
            other: Syntax to run after this one.

        Returns:
            Syntax producing the right value.
        """
        return self.seq(-self, +other)



    def __rrshift__(self, other: Syntax[B, S]) -> Syntax[Any, S]:

        return other.__rshift__(self)

    def __or__(self, other: Syntax[B, S]) -> Syntax[Any, S]:
        return self.alt(self, other)
        
    def __ror__(self, other: Syntax[Any, S]) -> Syntax[Any, S]:

        return self.__or__(other)


    def __pos__(self) -> Tuple[Syntax[A, S], bool]:
        """
        Mark this syntax as a positive branch in sequencing combinators.
        """
        return (self, True)

    def __neg__(self) -> Tuple[Syntax[A, S], bool]:
        """
        Mark this syntax as a negative branch in sequencing combinators.
        """
        return (self, False)
    
    def __invert__(self) -> Syntax[Any, S]:
        """Syntactic sugar for optional() (tilde operator)."""
        return self.optional

    ######################################################################## data processing combinators #########################################################


    def case(self, *branches: Tuple[Callable[..., Any], Callable[..., Any]], strict: bool=False, passthrough: bool=True, block_normalization: bool = True) -> Syntax[Any, S]:
        """
        Conditional bidirectional transformation based on structural shape.
        
        Use `case` when you need pattern matching on structural/shape conditionally.
        Each branch provides a (source, target) pair that is tried in sequence until
        one succeeds. This is ideal for discriminated unions or sum types where the
        different branches have structurally different input/output shapes.
        
        IMPORTANT - CHANNEL CONSISTENCY:
        Forward direction discriminates on SOURCE patterns (in declaration order).
        Inverse direction discriminates on TARGET patterns (sorted by specificity).
        
        To avoid "channel mismatch" (data taking different branches in different
        directions), ensure that:
        1. Source and target patterns have parallel structure/specificity
        2. Use distinct structural shapes (e.g., different dataclass types)
        3. Avoid overlapping patterns that could unify with the same value
        
        Example of problematic channel mismatch:
            >>> # BAD: generic source but specific target
            >>> .case(
            ...     (lambda env: env.x,              # matches anything
            ...      lambda env: Specific(...)),     # specific structure
            ...     ...
            ... )
            >>> # In forward: first branch matches everything
            >>> # In inverse: other branches may match before first (higher specificity)
            
            >>> # BAD: .case().bimap() composition with structural overlap
            >>> .case(
            ...     (lambda env: ("tagged", env.x),
            ...      lambda env: {"type": "tagged", "value": env.x})
            ... ).bimap(
            ...     forward=lambda x: f"processed:{x}",
            ...     inverse=lambda x: {"type": "other", "value": x}  # Also a dict!
            ... )
            >>> # Forward: unmatched input -> passthrough -> bimap.forward ✓
            >>> # Inverse: bimap.inverse produces dict -> matches case target pattern!
            >>> #          Takes case branch instead of passthrough = channel mismatch!
        
        LIMITATION: `case` handles structural conditions only (i.e., which branch to use
        based on data shape). For non-structural conditions or complex logic
        that cannot be determined by shape alone, use `.bimap()` instead.

        Args:
            *branches: Each branch is a tuple (forward_fn, inverse_fn) where:
                      - forward_fn: A -> B (returns value or raises to try next branch)
                      - inverse_fn: B -> A (for generation)
            strict: Not allow multiple branches to match the same value (default False).
            passthrough: Add catch-all branch that passes through unmatched values (default True).
            block_normalization: Prevent flattening this node during normalization (default True).

        Returns:
            Syntax with conditional transformation applied.
            
        Example:
            >>> # GOOD: Discriminated union with parallel structure
            >>> value = S.alt(
            ...     S.rp(r"null"),
            ...     S.rp(r"true|false")
            ... ).case(
            ...     (lambda _: "null", lambda _: None),
            ...     (lambda _: "true", lambda _: True), 
            ...     (lambda _: "false", lambda _: False)
            ... )
        
        """
        if not branches:
            return self
        m = Match(branches[0][0], branches[0][1])
        for branch in branches[1:]:
            m.case(branch[0], branch[1])
        return self.iso(m.iso(strict=strict, passthrough=passthrough), block_normalization=block_normalization)
        

    @overload
    def to(self, a: Callable[..., B], b: None = None, *, block_normalization: bool = True) -> Syntax[B, S]: ...

    @overload
    def to(self, a: Callable[..., A], b: Callable[..., B], *, block_normalization: bool = True) -> Syntax[B, S]: ...

    def to(self, a: Callable[..., A|B], b: Callable[..., B] | None = None, *, block_normalization: bool = True) -> Syntax[B, S]:
        """
        Structural transformation via constructor-based isomorphism derivation.
        
        Use `to` when transforming between data shapes (e.g., tuples to
        dataclasses). Syncraft automatically derives the inverse transformation by
        analyzing the constructors' signatures, making this ideal for
        "destruct-then-reconstruct" workflows without manually writing the inverse.
        
        LIMITATION: `to` works only on flat or finitely nested structures. General recursion and nesting are
        handled at the grammar/syntax level (e.g., via `Syntax.lazy()` or rule
        composition), not at the data transformation level. Use `.to()` to reshape
        single-level parsed results, then compose syntaxes for recursive structures.
        
        Args: 
            A pair of functions that takes one environment argument and returns a pattern. 
            The first function `a` is used for parsing (destructuring the source shape), 
            and the second function `b` is used for generation (constructing the target shape). 
            If only one function is provided, it is treated as the target pattern
            and Syncraft will treat the source pattern as `lambda env: env.X`. 
            The name `X` is inferred from the target pattern, which must 
            contain exactly one variable.
            
            a: Destructor/pattern for A (source shape). Typically a lambda that
               deconstructs the parsed result into components. When `b` is omitted,
               this becomes the target constructor instead.
            b: Constructor for B (target shape). Takes the components from `a` and
               builds the desired output type. If omitted, `a` is used as the target
               constructor and the source pattern is automatically inferred from the
               single variable in `a` (requires exactly one variable in the pattern).
            block_normalization: Prevent flattening this node during normalization.

        Returns:
            Syntax yielding B during parsing, accepting B during generation.
            
        Example:
            >>> from dataclasses import dataclass
            >>> @dataclass
            >>> class Point:
            ...     x: int
            ...     y: int
            >>>
            >>> # Transform from tuple to dataclass (flat structure)
            >>> point = S.seq(
            ...     S.rp(r"[0-9]+").bimap(int, str),
            ...     S.lit(","),
            ...     S.rp(r"[0-9]+").bimap(int, str)
            ... ).to(
            ...     lambda env: (env.X, env.Y),         # destruct: extract X, Y
            ...     lambda env: Point(env.X, env.Y)     # construct: build Point
            ... )
            >>> assert point.parse("3,4") == Point(3, 4) 
            >>> assert point.generate(Point(3, 4)) == "3,4"
            >>> 
            >>> # Convenience form: single-argument identity transformation
            >>> # Useful for wrapping a single value in a constructor
            >>> expr = S.rp(r"[0-9]+").to(
            ...     lambda env: SomeDataClass(env.X)    # unary target pattern, auto-infer source pattern
            ... )
            >>> # Equivalent to: .to(lambda env: env.X, lambda env: int(env.X))
                
        """
        if b is None:
            env = Env(constants=FrozenDict())
            # execute the pattern function to populate the environment with variable names, 
            a(env)
            names = env.scope.all_var_names()
            if len(names) != 1:
                raise SyncraftError(f"to() with single function requires exactly one variable in the pattern, found {len(names)}: {names}", offender=names, expect="exactly one variable name")
            var_name = next(iter(names))
            def default_source(env: Env) -> Any:
                return env.create_var(var_name)
            b = cast(Callable[..., B], a)
            a = default_source

        assert b is not None # For mypy type checking
        return self.iso(Iso.derive(a, b), block_normalization=block_normalization) # type: ignore
        



    def bind(self, entry: EntryCategory = EntryCategory.Parse, **f: Callable[[Any, Any], Any]) -> Syntax[A, S]:
        """
        Bind parsing result to a name for downstream transforms/checks.

        Args:
            entry: The stage where bindings are applied (`Parse`/`Generate`/`Format`).
                   The default is 'parse', which means the bindings will only be available 
                   during parsing and can be used by map and check that are applied 
                   after this bind in the syntax node.
            **f: Name-to-function mapping. Each function receives current value
                and context and returns the bound value. The name of the keyword argument
                becomes the name of the variable in the context that can be accessed by 
                downstream combinators.
        """
        return replace(
            self,
            alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).bind(entry=entry, **f),
            can_normalize=self._updated_can_normalize(block_normalization=True),
        )

    def check(self, 
              pred: Callable[..., bool], 
              *, 
              entry: EntryCategory = EntryCategory.Parse,
              level:int = 0, 
              message: str | None = None) -> Syntax[A, S]:
        """
        pred: A predicate function that takes the value and context variables as arguments and returns a boolean.
              For example, for a predicate that checks if the value is greater than a variable 'x' in the context, you could define:
              def pred(value, x):
                  return value > x
              the variable x will be resolved from the context by its name `x` when the predicate is evaluated.
        entry: Indicates which stage to apply the check on. It can be one of EntryCategory.Parse, EntryCategory.Generate, or EntryCategory.Format.
               - If EntryCategory.Parse, the predicate will be applied during parsing, and a failure will trigger backtracking.
               - If EntryCategory.Generate, the predicate will be applied during generation, and a failure will raise an error.
               - If EntryCategory.Format, the predicate will be applied during formatting, and a failure will raise an error.
        level: The stack level to use for error reporting. 0 means the caller of check, 1 means the caller's caller, etc. 
               This is used to get the correct file and line number for error messages.
        message: Optional custom error message template to use when the predicate fails. 
                 The template can include placeholders {value} and {ctx} for the value being checked and the context variables, respectively. 
                 If not provided, a default message including the predicate and location will be used.
        """
        file = get_file(level+1)        
        line = get_line(level+1)
        f = CallWith(pred)
        names = f.missing_args[1:]
        def check_preds(value: Any, ctx: FrozenDict[str, Any]) -> Any:
            vars = [ctx.get(name, ...) for name in names]
            if not pred(value, *vars):
                if message is None:
                    msg = f"Predicate {pred} (at {file}:{line}) failed for value {value} with context {ctx}\n{message}" 
                else:
                    msg = message.format(value=value, ctx=ctx)
                raise DataError(msg, soft_failure=entry is EntryCategory.Parse)
            return value
        match entry:
            case EntryCategory.Parse:
                return self.map(check_preds)
            case EntryCategory.Generate:
                return self.imap(check_preds)
            case EntryCategory.Format:
                return self.fmt(check_preds)
            case _:
                raise SyncraftError(f"Invalid entry category: {entry}", offender=entry, expect=f"None, {EntryCategory.Parse}, {EntryCategory.Generate}, or {EntryCategory.Format}")        

    @classmethod
    def fail(cls, error: B) -> Syntax[B, S]:
        """Create a syntax that always fails with `error`."""
        return cls.factory('fail', error=error)

    @classmethod
    def success(cls, value: B) -> Syntax[B, S]:
        """Create a syntax that always succeeds with `value` without consuming input."""
        return cls.factory('success', value=value)

    @classmethod
    def alt(cls, *parsers: Syntax[Any, S]) -> Syntax[Any, S]:
        """
        Construct an alternative (`or`) syntax from one or more branches.

        Normalization flattens nested alternatives when allowed.
        """
        all_parsers: Tuple[Syntax[Any, S], ...]
        flattened: List[Syntax[Any, S]] = []
        for parser in parsers:
            if isinstance(parser.spec, AltSpec) and parser.can_normalize:
                if parser._children is not None:
                    flattened.extend(parser._children)
                else:
                    flattened.append(parser)
            else:
                flattened.append(parser)
        all_parsers = tuple(flattened)
        def alt_f(acls: Type[Algebra], **global_kwargs: Any) -> Algebra:
            algs = [p(acls, **global_kwargs) for p in all_parsers]
            return acls.alt(*algs)
        spec = AltSpec(options=tuple(p.spec for p in all_parsers), name=None, file=None, line=None, func=None)
        iso = Iso() if cls.get('no_iso') else spec.iso()
        base = cls(alg_f=alt_f, spec=spec, _children=all_parsers)
        wrapped = base.iso(iso, block_normalization=False)  # type: ignore[arg-type]
        return replace(wrapped, _children=all_parsers) # type: ignore
    
    @classmethod
    def seq(cls, *steps: Syntax[Any, S] | Tuple[Syntax[Any, S], bool]) -> Syntax[Any, S]:
        """
        Construct a sequence syntax with optional keep/discard flags.

        Each step may be either:
        - `Syntax` (defaults to keep=True), or
        - `(Syntax, keep_bool)` where `True` keeps and `False` discards.

        Use the unary `+` operator to explicitly mark as keep, and `-` to discard:
        - `+syntax` creates `(syntax, True)` - keep in output
        - `-syntax` creates `(syntax, False)` - discard from output

        Args:
            *steps: One or more steps to sequence, with optional keep flags.

        """
        # Simple default: always True (keep) if not explicitly specified
        syntaxes = [X if isinstance(X, tuple) else (X, True) for X in steps]

        runtime_steps: List[Tuple[Syntax[Any, S], bool]]
        normalized_steps: List[Tuple[Syntax[Any, S], bool]] = []
        for step, keep in syntaxes:
            if isinstance(step.spec, SeqSpec) and step.can_normalize:
                # a nested Seq can be flattened, but we need to respect the keep flags. 
                # If the parent Seq has keep=True, then the child steps keep their own keep flags. 
                # If the parent Seq has keep=False, then all child steps are treated as keep=False 
                # regardless of their own flags.
                if step._children is not None:
                    for i, child_step in enumerate(step._children):
                        if keep:
                            normalized_keep = step.spec.steps[i][1] 
                        else:
                            normalized_keep = False
                        normalized_steps.append((child_step, normalized_keep))
                else:
                    normalized_steps.append((step, keep))
            else:
                normalized_steps.append((step, keep))

        runtime_steps = normalized_steps

        def seq_f(acls: Type[Algebra], **global_kwargs: Any) -> Algebra:
            algs = [(step(acls, **global_kwargs), keep) for step, keep in runtime_steps]
            return acls.seq(*algs)
        spec = SeqSpec(steps=tuple((step.spec, keep) for step, keep in runtime_steps), name=None, file=None, line=None, func=None)
        iso: Iso[Any, Any]
        if cls.get('no_iso'):
            iso = Iso()
        else:
            iso = spec.iso()
            if spec.arity == 1:
                unary_iso = Iso(
                    lambda value, _: value[0],
                    lambda value, _: (value,),
                )
                iso = iso >> unary_iso
        children = tuple(rs[0] for rs in runtime_steps)
        base = cls(alg_f=seq_f, spec=spec, _children=children)
        wrapped = base.iso(iso, block_normalization=False) # type: ignore
        return replace(wrapped, _children=children) 

    @classmethod
    def lazy(cls, thunk: Callable[[], Syntax[A, S]]) -> Syntax[A, S]:
        """
        Create a lazy syntax node for recursive grammar.

        The thunk is evaluated on demand and memoized through a facade cache,
        which keeps recursion identity stable across parser/generator algebras.
        """
        facade_cache = cls._lazy_facade_cache
        existing = facade_cache.get(thunk)
        if existing is not None:
            return existing  

        helper = LazyState(thunk=thunk)
        spec = LazySpec(lazy_state=helper, name=None, file=None, line=None, func=None)
        def lazy_alg_f(acls: Type[Algebra], **global_kwargs: Any) -> Algebra:
            return helper(acls, **global_kwargs)
        iso = Iso() if cls.get('no_iso') else spec.iso()
        facade = cls(alg_f=lazy_alg_f, spec=spec).iso(iso, block_normalization=False) # type: ignore
        facade_cache[thunk] = facade
        
        return facade
    

    @classmethod
    def factory(cls, name: str, *args:Any, **kwargs: Any) -> Syntax:
        """
        Create syntax from a method name of the underlying algebra.

        This is the primitive constructor used by helpers like `lit`, `re`, `rp`, 
        `tok`, and `eof`.
        """
        def factory_run(acls: Type[Algebra], **global_kwargs: Any) -> Algebra:
            method = getattr(acls, name, None)
            if method is None or not callable(method):
                raise SyncraftError(f"Method {name} is not defined in {acls.__name__}", offender=method, expect='callable')
            result = CallWith(method, *args, **(global_kwargs | kwargs))()
            return cast(Algebra, result)
        spec = LexSpec(fname=name, args=args, kwargs=FrozenDict(kwargs), MAX_NAME_LENGTH=cls.get('MAX_NAME_LENGTH'), name=None, file=None, line=None, func=None)
        return cls(factory_run, spec=spec)
    
    @classmethod
    def eof(cls) -> Syntax:
        """Create an end-of-input syntax."""
        return cls.factory('eof')
    
    @classmethod
    def lex(cls, builder: Builder | TokenSpec, **kwargs: Any) -> Syntax:
        """Create a terminal syntax from a lexer builder/token specification."""
        lexer_builder = cls.lexer()
        lb = lexer_builder(builder, **kwargs)
        return cls.factory('lex', builder=lb)

    @classmethod
    def set_lexer(cls, builder: LexerBuilder) -> Type[Syntax]:
        """Return a configured `Syntax` subclass with a custom lexer builder."""
        return cls.set(lexer_builder=builder)

    @classmethod
    def lexer(cls) -> LexerBuilder:
        """Return the active lexer builder, creating a local default if needed."""
        from syncraft.lexer import LocalLexerBuilder
        tmp = cls.get('lexer_builder')
        if tmp is None:
            tmp = LocalLexerBuilder()
            cls.set_lexer(tmp)
            return tmp
        return tmp


    @classmethod
    def re(cls, 
           pattern: str, 
           *,
           skip: bool = False, 
           tag: Tag = None, 
           push: str | None = None, 
           pop: str | Literal[True] | None = None,  
           of: str | None = None) -> Syntax:
        """Create a regex-backed terminal syntax.

        This is lexical regex matching (token-level). For recursive grammar
        fragments with `(?&name)` references, use `Syntax.rp(...)`.
        
        Args:
            pattern: Regular expression pattern for matching.
            skip: Mark this terminal for automatic skipping (whitespace/comments).
            tag: Optional tag for lexer identification.
            push: Push a new lexer mode when this token is matched (requires
                  GlobalLexerBuilder).
            pop: Pop the current lexer mode when this token is matched (requires
                 GlobalLexerBuilder).
            of: Specifies which mode this rule belongs to (requires
                GlobalLexerBuilder).
        
        NOTE:
            This API only works on str input.
        
        Skip Flag Behavior:
            The `skip` flag marks tokens for automatic filtering between other
            terminals. Behavior depends on the lexer builder mode:
            
            - **LocalLexerBuilder** (default): `skip=True` affects ONLY this
              specific terminal. If this terminal is explicitly included in your
              grammar (e.g., `S.re(r"\\s+", skip=True) + S.lit("x")`), the skip
              node still yields its text. Skip is NOT globally applied to other
              terminals.
            
            - **GlobalLexerBuilder**: `skip=True` is unioned into a shared DFA.
              Marked tokens are automatically filtered between ALL terminals in
              the grammar.
            
            For grammars using `S.rp()` patterns, explicit spacing in the pattern
            is often clearer than relying on skip flags.
        
        Lexer Modes (GlobalLexerBuilder only):
            The `push`, `pop`, and `of` parameters enable context-sensitive
            lexing (e.g., string interpolation, nested comments). These features
            require `GlobalLexerBuilder` as they depend on a unified lexer state
            machine. See `GlobalLexerBuilder` documentation for details.
        """
        # local import to avoid circular dependency
        import syncraft.regex as regex  
        b = regex.re(pattern).apply(skip=skip, tag=tag, push=push, pop=pop, of=of)
        ret = cls.lex(b)
        extra: FrozenDict[str, Any] = FrozenDict({
            'type': 're',
            'pattern': pattern,
            'skip': skip,
            'tag': tag,
            'push': push,
            'pop': pop,
            'of': of
        })
        assert isinstance(ret.spec, LexSpec), f"Expected LexSpec from cls.lex, got {type(ret.spec)}"
        return replace(ret, spec=replace(ret.spec, extra_info = extra))

    @classmethod
    def rp(cls, pattern: str, **refs: Syntax[Any, Any] | Tuple[Syntax[Any, Any], bool]) -> Syntax:
        """Compile a regex++ grammar fragment into `Syntax`.

        `rp` extends regex-like authoring with grammar references and recursion.
        Use `(?&name)` in `pattern` and pass the referenced syntaxes through
        keyword arguments (`name=...`).

        Args:
            pattern: Regex++ fragment string.
            **refs: Named syntax references used by `(?&name)`.

        Returns:
            A `Syntax` value representing the compiled fragment.

        Output semantics:
        - Capturing groups `(...)` and named captures `(?P<name>...)` are included in output
        - Placeholders `(?&name)` include their referenced syntax's output if the referenced syntax 
          is a bare Syntax object or marked as keep=True in the refs argument; 
          otherwise, they are matched but not included in output
          rp(..., ref = Syntax(...))  # placeholder is included in output
          rp(..., ref = (Syntax(...), True))  # placeholder is included in output
          rp(..., ref = (Syntax(...), False))  # placeholder is NOT included in output
          rp(..., ref = +Syntax(...))  # placeholder is included in output (keep=True
          rp(..., ref = -Syntax(...))  # placeholder is NOT included in output (keep=False)

        - Non-capturing groups `(?:...)` are matched but NOT included in output
        - Literals and character classes outside groups are matched but NOT captured
        - Multiple captures are flattened into a tuple in order of appearance
        - If no captures exist, returns the full matched text as a string

        Supported high-level capabilities:
        - Character classes, quantifiers, grouping, alternation.
        - Named syntax references via `(?&name)`.
        - Recursive references when combined with `Syntax.lazy(...)`.

        Example:
            >>> from syncraft.syntax import Syntax as S
            >>> # No captures: returns full text
            >>> word = S.rp(r"[a-z]+")  # "hello" -> "hello"
            >>> 
            >>> # With captures: returns tuple
            >>> pair = S.rp(r"(\\w+)-(\\d+)")  # "foo-42" -> ("foo", "42")
            >>> 
            >>> # Non-capturing groups excluded from output
            >>> S.rp(r"(?:foo)(bar)")  # "foobar" -> "bar"
            >>> 
            >>> # Grammar references
            >>> number = S.rp(r"[0-9]+").bimap(int, str)
            >>> op = S.rp(r"[+\\-*/]")
            >>> expr = S.lazy(lambda: S.rp(
            ...     r"(?&number)|(\\((?&expr)\\s*(?&op)\\s*(?&expr)\\))",
            ...     number=number,
            ...     op=op,
            ...     expr=expr,
            ... ))

        NOTE:
        - Keep reference names aligned between `(?&name)` and `name=...`.
        - Recursive references should usually be wrapped in `Syntax.lazy(...)`.
        - Global lexer skip behavior configured via grammar terminals does not
            automatically apply inside `rp` patterns; include spacing/comments in
            the pattern itself when needed.
        - Backreferences in classic regex style are not supported;
          model structural dependencies through grammar composition instead.
        - This API only works on str input, as regex matching is inherently string-based.
        """
        import syncraft.regex as regex
        ret = regex.rp(pattern, syntax_cls=cls, **refs)
        if isinstance(ret.spec, LexSpec):
            extra: FrozenDict[str, Any] = FrozenDict({
                'type': 'rp',
                'pattern': pattern,
                'refs': tuple(refs.keys())
            })
            return replace(ret, spec=replace(ret.spec, extra_info = extra))
        return ret

    @classmethod
    def lit(cls, 
            txt: str | bytes,
            *,
            skip: bool = False, 
            tag: Tag = None, 
            push: str | None = None, 
            pop: str | Literal[True] | None = None,  
            of: str | None = None) -> Syntax:
        """
        Create a literal terminal syntax from exact text.
        
        Args:
            txt: Exact text to match.
            skip: Mark this terminal for automatic skipping (whitespace/comments).
            tag: Optional tag for lexer identification.
            push: Push a new lexer mode when this token is matched (requires
                  GlobalLexerBuilder).
            pop: Pop the current lexer mode when this token is matched (requires
                 GlobalLexerBuilder).
            of: Specifies which mode this rule belongs to (requires
                GlobalLexerBuilder).
        
        NOTE:
            This API only works on str input.
        
        Skip Flag Behavior:
            The `skip` flag marks tokens for automatic filtering. Behavior
            depends on the lexer builder mode:
            
            - **LocalLexerBuilder** (default): Skip is NOT globally applied.
              Each terminal has its own independent lexer.
            
            - **GlobalLexerBuilder**: Skip is globally applied via DFA union.
              Marked tokens are filtered between all terminals.
            
            See `Syntax.re()` and `GlobalLexerBuilder` documentation for
            detailed skip semantics and lexer mode features.
        """
        b: Builder[Any]= Builder.lit(txt).apply(skip=skip, tag=tag, push=push, pop=pop, of=of)
        ret = cls.lex(b)
        extra: FrozenDict[str, Any] = FrozenDict({
            'type': 'lit',
            'text': txt,
            'skip': skip,
            'tag': tag,
            'push': push,
            'pop': pop,
            'of': of
        })
        assert isinstance(ret.spec, LexSpec), f"Expected LexSpec from cls.lex, got {type(ret.spec)}"
        return replace(ret, spec=replace(ret.spec, extra_info = extra))

    @classmethod
    def tok(cls, *txt: str | Pattern[str], case_sensitive: bool = True, **kwargs: Any) -> Syntax:
        """
        Create token-spec terminal syntax from literal/regex token forms.
        NOTE:
        - This API only works on structured token input, not raw strings.
        """
        tkspec: TokenSpec | None = TokenSpecBase.from_kwargs(*txt, case_sensitive=case_sensitive, **kwargs)
        if tkspec is None:
            parts = [str(t) for t in txt]
            parts += [f"{k}={v}" for k, v in kwargs.items()]
            args = ', '.join(parts)
            raise SyncraftError(f"Invalid arguments to tok({args})", offender=(txt, kwargs), expect="valid token specification")
        return cls.lex(tkspec, **kwargs)

    @classmethod
    def from_spec(cls, spec: SyntaxSpec)->Syntax:
        """Reconstruct a `Syntax` tree from a `SyntaxSpec` graph root."""
        c: Dict[SyntaxSpec, Syntax] = {}
        return spec.syntax(cls, cache=c)
    
    @classmethod
    def from_graph(cls, graph: Graph[SyntaxSpec]) -> Syntax:
        """Reconstruct a `Syntax` tree from a graph produced by `Syntax.graph()`."""
        c: Dict[SyntaxSpec, Syntax] = {}
        return graph.root.syntax(cls, cache=c)

    def to_ebnf(self) -> str:
        """Export this syntax to canonical EBNF text."""
        return ""
        # from syncraft.ebnf import syntax_to_ebnf_text
        # return syntax_to_ebnf_text(self)

    @classmethod
    def from_ebnf(cls, source: str) -> Syntax:
        """Build syntax from EBNF text."""
        return cls.success(None)  # placeholder
        # from syncraft.ebnf import ebnf_text_to_syntax
        # return ebnf_text_to_syntax(source, syntax_cls=cls)
    
    def parse(self, data: str) -> Any:
        """Parse text using this syntax.
        
        Args:
            data: The string to parse.
            
        Returns:
            The parsed result.
            
        Example:
            >>> num = S.rp(r"[0-9]+").bimap(int, str)
            >>> num.parse("42")
            42
        """
        from syncraft.parser import Runner
        from syncraft.parser import Parser
        runner: Runner = Runner()
        cursor = StreamCursor.from_data(data)
        parser = self(Parser)
        for result in runner.run(parser, state=None, cursor=cursor, once=True, cache=Cache()):  # type: ignore[arg-type]
            return result
        raise SyncraftError("Parsing did not yield any results", offender=None, expect="at least one result")
    
    def generate(self, data: Any = Unknown(), seed: int | None = None, replay: bool = False) -> LayoutDoc:
        """Generate a layout document from data using this syntax.
        
        Args:
            data: Source value/AST used for generation. ``None`` is treated as
                ``Unknown()``.
            seed: Optional random seed. When provided, stochastic choices are
                reproducible.
            replay: When ``True``, generation replays provided structure instead
                of freely sampling pruned/implicit parts. Useful for verification
                and round-trip checks.
            
        Returns:
            A ``LayoutDoc`` value. Call ``.render(width=..., indent=...)`` to
            materialize text under caller-defined constraints.
            
        Example:
            >>> num = S.rp(r"[0-9]+").bimap(int, str)
            >>> num.generate(42, seed=0).render()
            '42'
        """
        from syncraft.generator import Runner, Generator
        from syncraft.format import LayoutDoc
        import random
        runner = Runner(ast=data if data is not None else Unknown(),
                       seed=seed if seed is not None else random.randint(0, 2**32 - 1), 
                       replay=replay)
        generator = self(Generator)
        for result in runner.run(generator, state=None, cursor=None, once=True, cache=Cache()):  # type: ignore[arg-type]
            if isinstance(result, Error):
                raise SyncraftError(f"Generation failed with error: {result}", offender=result, expect="successful generation")
            return LayoutDoc.from_ast(result)
        raise SyncraftError("Generation did not yield any results", offender=None, expect="at least one result")
    
    def validate(self, data: Any, seed: int | None = None) -> Literal[True] | Error:
        """Validate data against this syntax.
        
        Args:
            data: The value/AST to validate.
            seed: Optional random seed. Used for deterministic internal choices
                when needed.
            
        Returns:
            ``True`` if validation succeeds, or ``Error`` with details if it
            fails.
            
        Example:
            >>> num = S.rp(r"[0-9]+").bimap(int, str)
            >>> num.validate(42)
            True
        """
        from syncraft.generator import Runner, Validator
        import random
        runner = Runner(ast=data if data is not None else Unknown(), 
                       seed=seed if seed is not None else random.randint(0, 2**32 - 1),
                       replay=True)
        validator = self(Validator)
        try:
            for result in runner.run(validator, state=None, cursor=None, once=True, cache=Cache()):  # type: ignore[arg-type]
                if isinstance(result, Error):
                    return result
            return True    
        except SyncraftError as e:
            return Error.new(this=None, message=f"Exception {e} during validation", error=e)



class RunnerProtocol(Protocol, Generic[A, S]):
    def algebra(self, 
                syntax: Syntax[A, S],
                alg_cls: Type[Algebra[A, S]]) -> Algebra[A, S]: 
        return syntax(alg_cls)

    def resume(self, previous: Optional[S], cursor: Optional[StreamCursor[Any]]) -> S: ...

    def finalize(self, result: Optional[Any]) -> None: 
        return


    def run(self, 
            parser: Algebra[A, S], 
            state: Optional[S],
            cursor: Optional[StreamCursor[Any]],
            cache: Optional[Cache[Any]],
            once: bool
            ) -> Generator[Any, None, None]: 
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
                    ret = result.value[0]
                elif isinstance(result, Left):
                    assert result.value is not None, "Algebra returned Left with None value"
                    ret = result.value
                else:
                    ret = Error.new(this=result, message="Algebra returned data that is not Left or Right")
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
                 ) -> Generator[Any, None, None]:
        alg = self.algebra(syntax=syntax, alg_cls=alg_cls)  
        yield from self.run(alg, state, cursor, cache, once=once)

    def once(self, 
             syntax: Syntax[A, S], 
             alg_cls: Type[Algebra[A, S]],
             state: Optional[S],
             cursor: Optional[StreamCursor[Any]],
             cache: Optional[Cache[Any]]
             ) -> Any:
        gen = self(syntax, alg_cls, state, cursor, cache, once=True)
        return next(gen)
        








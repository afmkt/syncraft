from __future__ import annotations

import keyword
import re
import math

from typing import (
    Optional, Any, TypeVar, Generic, Callable, Tuple, cast, Hashable,
    Type, List, Dict, Set, Iterator, ClassVar, Protocol, Generator
)
from dataclasses import dataclass, field, replace
from functools import reduce, cached_property


from syncraft.utils import file as get_file, line as get_line, func as get_func, FrozenDict, CallWith, ThreadLocalWeakValueDict
from syncraft.algebra import Algebra, Either, Left, Right, SYNCRAFT_CONFIG_KEY, Error
from syncraft.cache import Cache, Incomplete
from syncraft.constraint import Bindable

from syncraft.ast import Then, ThenKind, Marked, Choice, Many, ChoiceKind, Nothing, Collect, E, Collector, SyncraftError

from syncraft.input import StreamCursor, PayloadKind
from syncraft.fa import FABuilder




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
@dataclass(frozen=True)
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
    
    def __str__(self) -> str:
        """
        Generates a human-readable, indented tree representation of the graph
        starting from the root node.
        """
        # Set to track visited nodes to avoid infinite recursion on cycles
        visited: Set[N] = set()
        
        # List to store all lines of the output
        output_lines: List[str] = [self.__class__.__name__]
        def node_str(node: N) -> str:
            if isinstance(node, ThenSpec):
                return f"{str(id(node))}:{node}:ThenSpec({node.kind})"
            elif isinstance(node, ChoiceSpec):
                return f"{str(id(node))}:{node}:ChoiceSpec(|)"
            else:
                return f"{str(id(node))}:{node}"

        def _format_node(node: N, prefix: str, is_last_sibling: bool):
            """
            Recursive helper function for DFS traversal and formatting.
            
            Args:
                node: The current node being processed.
                prefix: The indentation string accumulated from parents (e.g., "│   │   ").
                is_last_sibling: True if this node is the last in its parent's list.
            """
            # 1. Check for cycles
            if node in visited:
                # Use └── for cycles as well, but only at the end of the line
                output_lines.append(f"{prefix}└── [CYCLE] {node}")
                return

            # 2. Mark as visited, determine connector, and add line
            visited.add(node)
            connector = "└── " if is_last_sibling else "├── "

            node_display = f"ROOT {node_str(node)}" if node == self.root else f"{node_str(node)}"
            output_lines.append(f"{prefix}{connector}{node_display}")
            
            # 3. Determine the new prefix for the children
            # If the current node is the last sibling, stop the vertical line (use '    ').
            # Otherwise, continue the vertical line (use '│   ').
            new_prefix = prefix + ("    " if is_last_sibling else "│   ")
            
            # 4. Process neighbors
            neighbors = sorted(list(self.edges.get(node, frozenset())), key=lambda x: -len(str(x)))
            
            for i, neighbor in enumerate(neighbors):
                neighbor_is_last = (i == len(neighbors) - 1)
                
                # The recursive call uses the new prefix and the neighbor's status
                _format_node(neighbor, new_prefix, neighbor_is_last)
        
        # --- Root Initialization ---
        
        # The root is treated as the 'last' child of an imaginary parent (is_last_sibling=True) 
        # so it gets the initial "└── " connector, matching the visual style.
        _format_node(self.root, "", True)

        # The root node should not have a connector if it were a pure tree print, 
        # but since your example started with `└── ROOT regex`, we keep the 
        # recursive call and the logic should now correctly indent the children 
        # from that point.
             
        return "\n".join(output_lines).strip()

    def __repr__(self) -> str:
        return self.__str__()

@dataclass(frozen=True)
class SyntaxSpec:
    name: Optional[str] = field(compare=False, hash=False)
    file: Optional[str] = field(compare=False, hash=False) 
    line: Optional[int] = field(compare=False, hash=False)
    func: Optional[str] = field(compare=False, hash=False)

    def syntax(self, cls: type[Syntax], cache: Dict[SyntaxSpec, Syntax])-> Syntax[Any, Any]:
        if self in cache:
            return cache[self]
        raise NotImplementedError
        
    def named(self, name: str, *, file: None | str, line: None | int, func: None | str, _location:bool=True) -> SyntaxSpec:
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

    def _children(self, *, lazy_cache: Dict[int, "SyntaxSpec"]) -> Tuple["SyntaxSpec", ...]:
        return ()

    @property    
    def complexity(self) -> float:
        return 0
    
    def walk(self, *, max_depth: Optional[int] = None) -> Iterator[Tuple[int, "SyntaxSpec"]]:
        lazy_cache: Dict[int, SyntaxSpec] = {}
        visited: Set[int] = set()
        stack: List[Tuple[int, SyntaxSpec]] = [(0, self)]

        while stack:
            depth, node = stack.pop()
            if max_depth is not None and depth > max_depth:
                continue

            node_id = id(node)
            if node_id in visited:
                continue
            visited.add(node_id)

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
        seen: Set[Tuple[int, int]] = set()

        for _depth, node in self.walk(max_depth=max_depth):
            for child in node._children(lazy_cache=lazy_cache):
                key = (id(node), id(child))
                if key in seen:
                    continue
                seen.add(key)
                edges.append((node, child))
        return Graph.from_edges(self, *edges)
        
    

@dataclass(frozen=True)
class LazySpec(SyntaxSpec):
    spec: Callable[[], SyntaxSpec]
    flatten: bool 

    def syntax(self, cls: type[Syntax], cache: Dict[SyntaxSpec, Syntax])-> Syntax[Any, Any]:
        if self in cache:
            return cache[self]
        ret = cls.lazy(lambda: self.spec().syntax(cls, cache=cache), flatten=self.flatten)
        cache[self] = ret
        return ret

    def __str__(self) -> str:
        name = self.name or "lazy(...)"
        return self.format("{0}", name)
    
    def __repr__(self) -> str:
        return super().__repr__()
    
    @property    
    def complexity(self) -> float:
        return math.inf


    def _children(self, *, lazy_cache: Dict[int, SyntaxSpec]) -> Tuple[SyntaxSpec, ...]:
        key = id(self)
        if key in lazy_cache:
            return (lazy_cache[key],)
        try:
            target = self.spec()
        except RecursionError:
            return ()
        lazy_cache[key] = target
        return (target,)
    

@dataclass(frozen=True)
class ThenSpec(SyntaxSpec, Generic[A, B]):
    kind: ThenKind
    left: SyntaxSpec
    right: SyntaxSpec

    def syntax(self, cls: type[Syntax], cache: Dict[SyntaxSpec, Syntax])-> Syntax[Any, Any]:
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

            
    def __repr__(self) -> str:
        return super().__repr__()

    @property
    def complexity(self) -> float:
        return 1 + self.left.complexity + self.right.complexity
    
    def _children(self,*, lazy_cache: Dict[int, SyntaxSpec]) -> Tuple[SyntaxSpec, ...]:
        return (self.left, self.right)

@dataclass(frozen=True)
class ChoiceSpec(SyntaxSpec, Generic[A, B]):
    left: SyntaxSpec
    right: SyntaxSpec

    def syntax(self, cls: type[Syntax], cache: Dict[SyntaxSpec, Syntax])-> Syntax[Any, Any]:
        if self in cache:
            return cache[self]
        left = self.left.syntax(cls, cache=cache)
        right = self.right.syntax(cls, cache=cache)
        ret = left | right
        cache[self] = ret
        return ret

    @classmethod
    def flatten(cls, node: SyntaxSpec) -> List[SyntaxSpec]:
        choices = []
        if isinstance(node, ChoiceSpec):
            choices.extend(cls.flatten(node.left))
            choices.extend(cls.flatten(node.right))
        else:
            choices.append(node)
        return choices


    def __str__(self) -> str:
        if self.name:
            return self.name
        else:
            choices = ChoiceSpec.flatten(self)
            if len(choices) == 2:
                return self.format("({left} | {right})", left=str(choices[0]), right=str(choices[1]))
            else:
                inner = " | ".join(str(c) for c in choices)
                return self.format("({choices})", choices=inner)

    def __repr__(self) -> str:
        return super().__repr__()

    @property
    def complexity(self) -> float:
        return 1 + max(self.left.complexity, self.right.complexity)

    def _children(self, *, lazy_cache: Dict[int, SyntaxSpec]) -> Tuple[SyntaxSpec, ...]:
        return (self.left, self.right)

@dataclass(frozen=True)
class ManySpec(SyntaxSpec, Generic[A]):
    spec: SyntaxSpec
    at_least: int
    at_most: Optional[int]

    def syntax(self, cls: type[Syntax], cache: Dict[SyntaxSpec, Syntax])-> Syntax[Any, Any]:
        if self in cache:
            return cache[self]
        inner = self.spec.syntax(cls, cache=cache)
        ret = inner.many(at_least=self.at_least, at_most=self.at_most)
        cache[self] = ret
        return ret

    def __str__(self) -> str:
        if self.name:
            return self.name
        else:
            return self.format("*({spec})", spec=str(self.spec))
        
    def __repr__(self) -> str:
        return super().__repr__()

    @property
    def complexity(self) -> float:
        if self.at_most is None:
            return 1 + self.spec.complexity * (self.at_least + 1)        
        else:
            return 1 + self.spec.complexity * ((self.at_least + self.at_most) // 2)
    
    def _children(self, *, lazy_cache: Dict[int, SyntaxSpec]) -> Tuple[SyntaxSpec, ...]:
        return (self.spec,)



@dataclass(frozen=True)
class LexSpec(SyntaxSpec):
    fname: str
    kwargs: FrozenDict[str, Any] = field(default_factory=FrozenDict)
    def syntax(self, cls: type[Syntax], cache: Dict[SyntaxSpec, Syntax])-> Syntax[Any, Any]:
        if self in cache:
            return cache[self]
        ret = cls.factory(self.fname, **self.kwargs)
        cache[self] = ret
        return ret
    
    def __str__(self) -> str:
        if self.name or not self.kwargs:
            return self.name or self.fname
        else:
            args = f"{', '.join(f'{k}={v}' for k,v in self.kwargs.items())}"
            return self.format("{fname}({args})", fname=self.fname, args=args)
    
    def __repr__(self) -> str:
        return super().__repr__()

    @property
    def complexity(self) -> float:
        return 1
    
@dataclass
class LazyState(Generic[A, S]):
    flatten: bool
    # thunk returns a Syntax[A, S], the original callable passed to Syntax.lazy
    thunk: Callable[[], Syntax[A, S]] | None = field(default = None, repr=False, compare=False)
    # cached resolved Syntax; excluded from comparisons
    _cached_syntax: Optional[Syntax[A, S]] = field(default=None, init=False, repr=False, compare=False)
    # cache algebras per (alg, kwargs_key). excluded from comparisons
    _inner_algebras_cache: Dict[Tuple[Type[Algebra[Any, Any]], Tuple[Tuple[str, Any], ...]], Algebra[A, S]] = field(default_factory=dict, init=False, repr=False, compare=False)
    _algebras_cache: Dict[Tuple[Type[Algebra[Any, Any]], Tuple[Tuple[str, Any], ...]], Algebra[A, S]] = field(default_factory=dict, init=False, repr=False, compare=False)

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
        



@dataclass(frozen=True)
class Syntax(Generic[A, S]):
    """
    The core signature of Syntax is take an Algebra Class and return an Algebra Instance.
    """
    alg_f: Callable[..., Algebra[A, S]]
    spec: SyntaxSpec = field(repr=False)
    _lazy_facade_cache: ClassVar[ThreadLocalWeakValueDict[Callable[..., Any], Syntax[Any, Any]]] = ThreadLocalWeakValueDict()
    
    def __str__(self) -> str:
        return str(self.spec)
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def as_(self, typ: Type[B]) -> B:
        return cast(typ, self)  # type: ignore
    
    @classmethod
    def config(cls, **attrs: Any) -> Type['Syntax[Any, Any]']:
        return type(cls.__name__, (cls,), {SYNCRAFT_CONFIG_KEY: attrs})


    def __call__(self, alg: Type[Algebra[Any, Any]], **global_kwargs) -> Algebra[A, S]:
        cfg = getattr(self.__class__, SYNCRAFT_CONFIG_KEY, {})
        return self.alg_f(alg, **(cfg | global_kwargs)).with_syntax(self)
            
    def named(self, name: str, *, level:int=0, _location:bool=True) -> Syntax[A, S]:
        return replace(self, spec=self.spec.named(name, file=get_file(level+1), line=get_line(level+1), func=get_func(level+1), _location=_location))

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

    def many(self, *, at_least: int = 1, at_most: Optional[int] = None) -> Syntax[Many[A], S]:
        """Repeat this syntax and collect results into Many.

        Repeats greedily until failure or no progress. Enforces bounds.

        Args:
            at_least: Minimum number of matches (default 1).
            at_most: Optional maximum number of matches.

        Returns:
            Syntax producing Many of values.
        """
        return replace(self, 
                       alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).many(at_least=at_least, at_most=at_most), # type: ignore
                       spec = ManySpec(spec=self.spec, at_least=at_least, at_most=at_most, name=None, file=None, line=None, func=None)
                       )

    def debug(self, 
              on_fail: Optional[Callable[[Algebra[A, S], Any, S], None]] = None, 
              on_success: Optional[Callable[[Algebra[A, S], A, S], None]] = None) -> Syntax[A, S]:

        def on_succeed(alg: Algebra[A, S], input: S, result: Right[Tuple[A, S]]) -> Either[Any, Tuple[A, S]]:
            if callable(on_success):
                on_success(alg, *result.value)
            return result
            
        def on_failure(alg: Algebra[A, S], input: S, error: Left[Any]) -> Either[Any, Tuple[A, S]]:
            if callable(on_fail):
                on_fail(alg, error.value, input)
            return error
        
        return replace(self, alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).on_success(on_succeed).on_fail(on_failure))

    ############################################################### facility combinators ############################################################
    def between(self, left: Syntax[B, S], right: Syntax[C, S]) -> Syntax[Then[B, Then[A, C]], S]:
        """Parse left, then this syntax, then right; keep all.

        Equivalent to left >> self // right.

        Args:
            left: Opening syntax.
            right: Closing syntax.

        Returns:
            Syntax producing nested Then with all parts.
        """
        return (left >> self // right)

    def sep_by(self, sep: Syntax[B, S]) -> Syntax[Then[A, Choice[Many[Then[B, A]], Optional[Nothing]]], S]:
        """Parse one or more items separated by sep.

        Returns a structure where the first item is separated from the rest,
        which are collected in a Many of Then pairs.

        Args:
            sep: Separator syntax between items.

        Returns:
            Syntax describing a non-empty, separator-delimited list.
        """
        ret: Syntax[Then[A, Choice[Many[Then[B, A]], Nothing]], S] = self + (sep >> self).many().optional

        def f(a: Then[A, Choice[Many[Then[B, A]], Nothing]]) -> Many[A]:
            match a:
                case Then(
                    kind=ThenKind.BOTH,
                    left=left,
                    right=Choice(kind=ChoiceKind.RIGHT, value=Nothing()),
                ):
                    return Many(value=(left,))
                case Then(
                    kind=ThenKind.BOTH,
                    left=left,
                    right=Choice(kind=ChoiceKind.LEFT, value=Many(value=bs)),
                ):
                    return Many(value=(left,) + tuple([b.right for b in bs]))
                case _:
                    raise SyncraftError(f"Bad data shape {a}", offender=a, expect="Then(BOTH) with Choice on the right")

        def i(a: Many[A]) -> Then[A, Choice[Many[Then[B | None, A]], Nothing]]:
            if not isinstance(a, Many) or len(a.value) < 1:
                raise SyncraftError(f"sep_by inverse expect Many with at least one element, got {a}", offender=a, expect="Many with at least one element")
            if len(a.value) == 1:
                return Then(
                    kind=ThenKind.BOTH,
                    left=a.value[0],
                    right=Choice(kind=ChoiceKind.RIGHT, value=Nothing()),
                )
            else:
                v: List[Then[B | None, A]] = [
                    Then(kind=ThenKind.RIGHT, right=x, left=None) for x in a.value[1:]
                ]
                return Then(
                    kind=ThenKind.BOTH,
                    left=a.value[0],
                    right=Choice(kind=ChoiceKind.LEFT, value=Many(value=tuple(v))),
                )

        return ret.iso(f, i)  # type: ignore

    def parens(
        self,
        sep: Syntax[C, S],
        open: Syntax[B, S],
        close: Syntax[D, S],
    ) -> Syntax[Then[B, Then[Then[A, Choice[Many[Then[C, A]], Optional[Nothing]]], D]], S]:
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
    def optional(self) -> Syntax[Choice[A, Nothing], S]:
        """Make this syntax optional.

        Returns a Choice of the value or Nothing when absent.

        Returns:
            Syntax producing Choice of value or Nothing.
        """
        return (self | self.success(Nothing())).named(f"({str(self.spec)})?", _location=False)
        
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
                       spec = ThenSpec(kind=ThenKind.LEFT, left=self.spec, right=other.spec, name=None, file=None, line=None, func=None)
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

    def __or__(self, other: Syntax[B, S]) -> Syntax[Choice[A, B], S]:
        """Alternative: try this syntax; if it fails uncommitted, try the other.

        Returns a Choice indicating which branch succeeded.

        Args:
            other: Alternative syntax to try on failure.

        Returns:
            Syntax producing Choice.LEFT or Choice.RIGHT.
        """

        return replace(self, 
                       alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).or_else(other(cls, **global_kwargs)).flag(is_choice=True), # type: ignore
                       spec=ChoiceSpec(left=self.spec, right=other.spec, name=None, file=None, line=None, func=None))
        

    def __ror__(self, other: Syntax[B, S]) -> Syntax[Choice[B, A], S]:

        return other.__or__(self)

    def __invert__(self) -> Syntax[Choice[A, Nothing], S]:
        """Syntactic sugar for optional() (tilde operator)."""
        return self.optional

    ######################################################################## data processing combinators #########################################################
    def bind(self, name: Optional[str] = None) -> Syntax[A, S]:
        """Bind the produced value to the name.

        If name is None and the value is Marked, the name of Marked is used.
        If name is None and the value if Collect, the name of the collector is used.

        Args:
            name: Optional binding name; must be a valid identifier if provided.

        Returns:
            Syntax that writes the value into the state's binding table.
        """
        if name:
            assert valid_name(name), f"Invalid mark name: {name}"

        def bind_v(v: Any, s: S) -> Tuple[Any, S]:
            if name:
                return v, s.bind(name, v)
            elif isinstance(v, Marked):
                return v.value, s.bind(v.name, v.value)
            elif isinstance(v, Collect) and isinstance(v.collector, type):
                return v.value, s.bind(v.collector.__name__, v.value)
            else:
                return v, s

        return self.map_all(bind_v)

    def to(self, f: Collector[E]) -> Syntax[Collect[A, E], S]:
        """Attach a collector to the produced value.
        A collector can be a dataclass, and the Marked nodes will be 
        mapped to the fields of the dataclass.

        Wraps the value in Collect or updates an existing one.

        Args:
            f: Collector invoked during generation/printing.

        Returns:
            Syntax producing Collect(value, collector=f).
        """
        def to_f(v: A) -> Collect[A, E]:
            if isinstance(v, Collect):
                return replace(v, collector=f)
            else:
                return Collect(collector=f, value=v)

        def ito_f(c: Collect[A, E]) -> A:
            return c.value if isinstance(c, Collect) else c

        return self.iso(to_f, ito_f)

    def mark(self, name: str) -> Syntax[Marked[A], S]:

        assert valid_name(name), f"Invalid mark name: {name}"

        def mark_s(value: A) -> Marked[A]:
            if isinstance(value, Marked):
                return replace(value, name=name)
            else:
                return Marked(name=name, value=value)

        def imark_s(m: Marked[A]) -> A:
            return m.value if isinstance(m, Marked) else m

        return self.iso(mark_s, imark_s)
    
    @cached_property
    def lexspec(self) -> frozenset[LexSpec]:
        result: Set[LexSpec] = set()
        for _, node in self.spec.walk():
            if isinstance(node, LexSpec):
                result.add(node)
        return frozenset(result)


    @classmethod
    def fail(cls, error: B) -> Syntax[B, S]:
        return cls.factory('fail', error=error)

    @classmethod
    def success(cls, value: B) -> Syntax[B, S]:
        return cls.factory('success', value=value)


    @classmethod
    def choice(cls, *parsers: Syntax[Any, S]) -> Syntax[Any, S]:
        sorted_parsers = sorted(parsers, key=lambda p: p.spec.complexity)
        return reduce(lambda a, b: a | b, sorted_parsers) if len(sorted_parsers) > 0 else cls.success(Nothing())


    @classmethod
    def lazy(cls, thunk: Callable[[], Syntax[A, S]], flatten: bool = False) -> Syntax[A, S]:
        facade_cache = cls._lazy_facade_cache
        existing = facade_cache.get(thunk)
        if existing is not None:
            return existing  

        helper = LazyState(flatten=flatten, thunk=thunk)

        facade = cls(alg_f=lambda acls, **global_kwargs: helper(acls, **global_kwargs), 
                     spec=LazySpec(spec=lambda: helper.cached.spec, 
                                   flatten=flatten,
                                   name=None, 
                                   file=None, 
                                   line=None, 
                                   func=None))
        facade_cache[thunk] = facade
        return facade
    

    @classmethod
    def factory(cls, name: str, **kwargs: Any) -> Syntax[Any, Any]:
        
        def factory_run(acls: Type[Algebra[Any, Any]], **global_kwargs: Any) -> Algebra[Any, Any]:
            method = getattr(acls, name, None)
            if method is None or not callable(method):
                raise SyncraftError(f"Method {name} is not defined in {acls.__name__}", offender=method, expect='callable')
            result = CallWith(method, **(global_kwargs | kwargs))()
            return cast(Algebra[Any, Any], result)
        return cls(factory_run, spec=LexSpec(fname=name, kwargs=FrozenDict(kwargs), name=None, file=None, line=None, func=None))

    @classmethod
    def token(cls, **kwargs: Any) -> Syntax[Any, Any]:
        return cls.factory('lex', **kwargs)

    @classmethod
    def lex(cls, **kwargs: FABuilder) -> Syntax[Any, Any]:
        return cls.factory('lex', **kwargs)
    
    @classmethod
    def literal(cls, lit: str | re.Pattern[str]) -> Syntax[Any, Any]:
        return cls.token(text=lit, case_sensitive=True)
    

    @classmethod
    def from_spec(cls, spec: SyntaxSpec)->Syntax[Any, Any]:
        c: Dict[SyntaxSpec, Syntax] = {}
        return spec.syntax(cls, cache=c)


        
    
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
            cursor: Optional[StreamCursor[Any]],
            cache: Optional[Cache[Any]] = None,
            once: bool=True) -> Generator[Tuple[Any, None | S], None, None]: 
        while True:
            ret = None
            state = self.resume(None, cursor)
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
                    ret = result.value
                elif isinstance(result, Left):
                    ret = result.value, None
                else:
                    ret = Error(this=result, message="Algebra returned data that is not Left or Right"), None
            finally:
                self.finalize(ret)
            yield ret  # type: ignore
            if once:
                break
                
                


    def __call__(self, 
                 syntax: Syntax[A, S], 
                 alg_cls: Type[Algebra[A, S]],
                 cursor: Optional[StreamCursor[Any]],
                 cache: Optional[Cache[Any]] = None) -> Tuple[Any, None | S]:
        parser = self.algebra(syntax=syntax, alg_cls=alg_cls, payload_kind=cursor.payload_kind if cursor else None)  
        for ret in self.run(parser, cursor, cache, once=True):
            return ret
        raise SyncraftError("Runner did not yield any results", offender=self, expect="at least one result")
        





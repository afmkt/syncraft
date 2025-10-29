from __future__ import annotations

import keyword
import re
import threading
import math
from weakref import WeakValueDictionary

from typing import (
    Optional, Any, TypeVar, Generic, Callable, Tuple, cast,
    Type, List, Dict, Set, Iterator, ClassVar, Protocol
)
from dataclasses import dataclass, field, replace
from functools import reduce

from syncraft.algebra import Algebra, Error, Either, Left, Right, SYNCRAFT_CONFIG_KEY
from syncraft.cache import Cache, Incomplete
from syncraft.constraint import Bindable, FrozenDict
from syncraft.ast import Then, ThenKind, Marked, Choice, Many, ChoiceKind, Nothing, Collect, E, Collector, SyncraftError
from syncraft.utils import CallWith

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
@dataclass(frozen=True)
class SyntaxSpec:
    def named(self, name: str) -> SyntaxSpec:
        return self
    
    def _children(
        self,
        *,
        lazy_cache: Optional[Dict[int, "SyntaxSpec"]] = None,
    ) -> Tuple["SyntaxSpec", ...]:
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

    def build_graph(
        self,
        *,
        max_depth: Optional[int] = None,
    ) -> List[Tuple["SyntaxSpec", "SyntaxSpec"]]:
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

        return edges
    

@dataclass(frozen=True)
class LazySpec(SyntaxSpec):
    spec: Callable[[], SyntaxSpec]
    name: Optional[str] = None
    def named(self, name: str) -> SyntaxSpec:
        return replace(self, name=name)
    
    def __str__(self) -> str:
        if self.name:
            return self.name
        return "lazy(...)" 
    def __repr__(self) -> str:
        return super().__repr__()
    
    @property    
    def complexity(self) -> float:
        return math.inf


    def _children(
        self,
        *,
        lazy_cache: Optional[Dict[int, SyntaxSpec]] = None,
    ) -> Tuple[SyntaxSpec, ...]:
        if lazy_cache is None:
            lazy_cache = {}
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
    name: Optional[str] = None
    def named(self, name: str) -> SyntaxSpec:
        return replace(self, name=name)
    
    def __str__(self) -> str:
        if self.name:
            return self.name
        match self.kind:
            case ThenKind.LEFT:
                return f"({str(self.left)} // {str(self.right)})" 
            case ThenKind.RIGHT:
                return f"({str(self.left)} >> {str(self.right)})" 
            case _:
                return f"({str(self.left)} + {str(self.right)})"
    def __repr__(self) -> str:
        return super().__repr__()

    @property
    def complexity(self) -> float:
        return 1 + self.left.complexity + self.right.complexity
    
    def _children(
        self,
        *,
        lazy_cache: Optional[Dict[int, SyntaxSpec]] = None,
    ) -> Tuple[SyntaxSpec, ...]:
        return (self.left, self.right)

@dataclass(frozen=True)
class ChoiceSpec(SyntaxSpec, Generic[A, B]):
    left: SyntaxSpec
    right: SyntaxSpec
    name: Optional[str] = None
    def named(self, name: str) -> SyntaxSpec:
        return replace(self, name=name)
    
    def __str__(self) -> str:
        if self.name:
            return self.name
        return f"({str(self.left)} | {str(self.right)})" 
    def __repr__(self) -> str:
        return super().__repr__()

    @property
    def complexity(self) -> float:
        return 1 + self.left.complexity + (self.right.complexity / 2)

    def _children(
        self,
        *,
        lazy_cache: Optional[Dict[int, SyntaxSpec]] = None,
    ) -> Tuple[SyntaxSpec, ...]:
        return (self.left, self.right)

@dataclass(frozen=True)
class ManySpec(SyntaxSpec, Generic[A]):
    spec: SyntaxSpec
    at_least: int
    at_most: Optional[int]
    name: Optional[str] = None
    def named(self, name: str) -> SyntaxSpec:
        return replace(self, name=name)
    
    def __str__(self) -> str:
        if self.name:
            return self.name
        return f"*({str(self.spec)})" 
    def __repr__(self) -> str:
        return super().__repr__()

    @property
    def complexity(self) -> float:
        if self.at_most is None:
            return 1 + self.spec.complexity * (self.at_least + 1)        
        else:
            return 1 + self.spec.complexity * ((self.at_least + self.at_most) // 2)
    
    def _children(
        self,
        *,
        lazy_cache: Optional[Dict[int, SyntaxSpec]] = None,
    ) -> Tuple[SyntaxSpec, ...]:
        return (self.spec,)



@dataclass(frozen=True)
class FactorySpec(SyntaxSpec):
    fname: str
    kwargs: FrozenDict[str, Any] = field(default_factory=FrozenDict)
    name: Optional[str] = None
    def named(self, name: str) -> SyntaxSpec:
        return replace(self, name=name)
    
    def __str__(self) -> str:
        if self.name:
            return self.name
        ret = f"{', '.join(f'{k}={v}' for k,v in self.kwargs.items())}"
        return f"{self.fname}({ret})" if ret != '' else self.fname
    def __repr__(self) -> str:
        return super().__repr__()

    @property
    def complexity(self) -> float:
        return 1
    
@dataclass
class LazyState(Generic[A, S]):
    # thunk returns a Syntax[A, S]
    thunk: Callable[[], Syntax[A, S]] | None = field(default = None, repr=False, compare=False)
    # cached resolved Syntax; excluded from comparisons
    _cached: Optional[Syntax[A, S]] = field(default=None, init=False, repr=False, compare=False)
    # cache algebras per (alg, kwargs_key). excluded from comparisons
    _cached_algebras: Dict[Tuple[Type[Algebra[Any, Any]], Tuple[Tuple[str, Any], ...]], Algebra[A, S]] = field(default_factory=dict, init=False, repr=False, compare=False)
    # lock to guard initialization
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False, compare=False)
    @property
    def cached(self) -> Syntax[A, S]:
        # Double-checked locking: avoid acquiring lock in the fast path.
        if self._cached is None:
            with self._lock:
                if self._cached is None:
                    if self.thunk is None:
                        raise SyncraftError("LazyState missing thunk", offender=self, expect="a thunk Callable")
                    resolved = self.thunk()
                    if not isinstance(resolved, Syntax):
                        raise SyncraftError("Lazy thunk did not return a Syntax", offender=(self.thunk, resolved), expect="Syntax")
                    # store resolved syntax into the frozen dataclass slot
                    self._cached = resolved
                    
        return self._cached  # type: ignore

    def __call__(self, alg: Type[Algebra[Any, Any]], **global_kwargs) -> Algebra[A, S]:
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

        key = (alg, kwargs_key)

        # fast path: avoid lock if already cached
        existing = self._cached_algebras.get(key)
        if existing is not None:
            return existing

        # guarded path: populate cache under lock
        with self._lock:
            # existing = self._cached_algebras.get(key)
            # if existing is not None:
            #     return existing
            resolved_syntax = self.cached
            def algebra_lazy_f() -> Algebra[A, S]:
                return resolved_syntax(alg, **global_kwargs)
            algebra = alg.lazy(algebra_lazy_f)
            # --- Patch _rule_id for left-recursion recovery ---
            try:
                setattr(algebra.run_f, "_rule_id", self.thunk)
                pass
            except Exception:
                pass
            self._cached_algebras[key] = algebra
            return algebra
        



@dataclass(frozen=True)
class Syntax(Generic[A, S]):
    """
    The core signature of Syntax is take an Algebra Class and return an Algebra Instance.
    """
    alg_f: Callable[..., Algebra[A, S]]
    spec: SyntaxSpec = field(repr=False)
    _lazy_facade_cache: ClassVar[WeakValueDictionary[Callable[..., Any], Syntax[Any, Any]]] = WeakValueDictionary()
    
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
        cfg = getattr(alg, SYNCRAFT_CONFIG_KEY, {})
        return self.alg_f(alg, **(cfg | global_kwargs)).named(self)
            
    def named(self, name: str) -> Syntax[A, S]:
        return replace(self, spec=self.spec.named(name))

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

    def build_graph(
        self,
        *,
        max_depth: Optional[int] = None,
    ) -> List[Tuple[SyntaxSpec, SyntaxSpec]]:
        return self.spec.build_graph(max_depth=max_depth)

    def bimap(self, f: Callable[[A], B], i: Callable[[B], A]) -> Syntax[B, S]:
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
                       spec = ManySpec(spec=self.spec, at_least=at_least, at_most=at_most)
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
        ret: Syntax[Then[A, Choice[Many[Then[B, A]], Optional[Nothing]]], S] = (
            self + (sep >> self).many().optional()
        )

        def f(a: Then[A, Choice[Many[Then[B, A]], Optional[Nothing]]]) -> Many[A]:
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

        def i(a: Many[A]) -> Then[A, Choice[Many[Then[B | None, A]], Optional[Nothing]]]:
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

        return ret.bimap(f, i)  # type: ignore

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

    def optional(self) -> Syntax[Choice[A, Optional[Nothing | B]], S]:
        """Make this syntax optional.

        Returns a Choice of the value or Nothing when absent.

        Returns:
            Syntax producing Choice of value or Nothing.
        """
        return (self | self.success(Nothing()))  # type: ignore
        

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
                       spec = ThenSpec(kind=ThenKind.LEFT, left=self.spec, right=other.spec)
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
                       spec=ThenSpec(kind=ThenKind.BOTH, left=self.spec, right=other.spec))


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
                       spec=ThenSpec(kind=ThenKind.RIGHT, left=self.spec, right=other.spec))
        

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
                       alg_f=lambda cls, **global_kwargs: self(cls, **global_kwargs).or_else(other(cls, **global_kwargs)), # type: ignore
                       spec=ChoiceSpec(left=self.spec, right=other.spec))
        

    def __ror__(self, other: Syntax[B, S]) -> Syntax[Choice[B, A], S]:

        return other.__or__(self)

    def __invert__(self) -> Syntax[Choice[A, Optional[Nothing]], S]:
        """Syntactic sugar for optional() (tilde operator)."""
        return self.optional()

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

        return self.bimap(to_f, ito_f)

    def mark(self, name: str) -> Syntax[Marked[A], S]:

        assert valid_name(name), f"Invalid mark name: {name}"

        def mark_s(value: A) -> Marked[A]:
            if isinstance(value, Marked):
                return replace(value, name=name)
            else:
                return Marked(name=name, value=value)

        def imark_s(m: Marked[A]) -> A:
            return m.value if isinstance(m, Marked) else m

        return self.bimap(mark_s, imark_s)
    
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
    def lazy(cls, thunk: Callable[[], Syntax[A, S]]) -> Syntax[A, S]:
        facade_cache = cls._lazy_facade_cache
        existing = facade_cache.get(thunk)
        if existing is not None:
            return existing  

        helper = LazyState(thunk)

        facade = cls(alg_f=lambda acls, **global_kwargs: helper(acls, **global_kwargs), 
                     spec=LazySpec(spec=lambda: helper.cached.spec))
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
        return cls(factory_run, spec=FactorySpec(fname=name, kwargs=FrozenDict(kwargs)))

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
        def _rehydrate(
            cls: type[Syntax],
            spec: SyntaxSpec,
            cache: Dict[SyntaxSpec, Syntax]
        ) -> Syntax:
            if spec in cache:
                return cache[spec]
            if isinstance(spec, LazySpec):
                syntax = cls.lazy(lambda: _rehydrate(cls, spec.spec(), cache))
            elif isinstance(spec, ThenSpec):
                left = _rehydrate(cls, spec.left, cache)
                right = _rehydrate(cls, spec.right, cache)
                if spec.kind == ThenKind.BOTH:
                    syntax = left + right
                elif spec.kind == ThenKind.LEFT:
                    syntax = left // right
                elif spec.kind == ThenKind.RIGHT:
                    syntax = left >> right
                else:  # pragma: no cover - defensive guard
                    raise AssertionError(f"Unsupported ThenKind: {spec.kind!r}")
            elif isinstance(spec, ChoiceSpec):
                syntax = _rehydrate(cls, spec.left, cache) | _rehydrate(cls, spec.right, cache)
            elif isinstance(spec, ManySpec):
                inner = _rehydrate(cls, spec.spec, cache)
                syntax = inner.many(at_least=spec.at_least, at_most=spec.at_most)
            elif isinstance(spec, FactorySpec):
                syntax = cls.factory(spec.fname, **spec.kwargs)
            else:  # pragma: no cover - defensive guard
                raise AssertionError(f"Unsupported SyntaxSpec node: {spec!r}")
            cache[spec] = syntax
            return syntax

        return _rehydrate(cls, spec, c)

    def factory_spec(self, visitor: Callable[[FactorySpec, Any], Any], init: Any) -> Any:
        for _, node in self.spec.walk():
            if isinstance(node, FactorySpec):
                init = visitor(node, init)
        return init
    
class RunnerProtocol(Protocol, Generic[A, S]):
    def bootstrap(self, 
                  syntax: Syntax[A, S],
                  alg_cls: Type[Algebra[A, S]],
                  ) -> Tuple[Algebra[A, S], S]: ...

    def resume(self, request: Incomplete[S]) -> S: ...

    def finalize(self, result: Optional[Tuple[Any, None | S]]) -> None: 
        return

    def __call__(self, 
                 syntax: Syntax[A, S], 
                 alg_cls: Type[Algebra[A, S]],
                 cache: Optional[Cache[Any, Any]] = None) -> Tuple[Any, None | S]:
        ret = None
        parser, state = self.bootstrap(syntax=syntax, alg_cls=alg_cls)  
        gen_cache = cache or Cache()
        assert gen_cache is not None
        parser_gen = parser.run(state, cache=gen_cache)
        try:
            result = next(parser_gen)
            while True:
                if isinstance(result, Incomplete):
                    pending_state = self.resume(result)
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
        return ret # type: ignore




from __future__ import annotations

from typing import (
    Optional, Any, TypeVar, Generic, Callable, Tuple, cast,
    Type, Literal, List
)
from dataclasses import dataclass, field, replace
from functools import reduce
from syncraft.algebra import Algebra, Error, Either, Right, Left
from syncraft.constraint import Bindable, FrozenDict
from syncraft.ast import Then, ThenKind, Marked, Choice, Many, ChoiceKind, Nothing, Collect, E, Collector
from types import MethodType, FunctionType
import keyword



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
class Description:
    name: Optional[str] = None
    newline: Optional[str] = None
    fixity: Literal['infix', 'prefix', 'postfix'] = 'infix'
    parameter: Tuple[Any, ...] = field(default_factory=tuple)

    def update(self, 
               *,
               newline: Optional[str] = None,
               name: Optional[str] = None,
               fixity: Optional[Literal['infix', 'prefix', 'postfix']] = None,
               parameter: Optional[Tuple[Any, ...]] = None) -> 'Description':
        return Description(
            name=name if name is not None else self.name,
            newline= newline if newline is not None else self.newline,
            fixity=fixity if fixity is not None else self.fixity,
            parameter=parameter if parameter is not None else self.parameter
        )
        
    def to_string(self, interested: Callable[[Any], bool]) -> Optional[str]:
        if self.name is not None:
            if self.fixity == 'infix':
                assert len(self.parameter) == 2, "Expected exactly two parameters for infix operator"
                left  = self.parameter[0].to_string(interested) if interested(self.parameter[0]) else '...'
                right = self.parameter[1].to_string(interested) if interested(self.parameter[1]) else '...'
                if self.parameter[1].meta.newline is not None:
                    new = '\u2570' # '\u2936'
                    return f"{left}\n{new} \"{self.parameter[1].meta.newline}\" {self.name} {right}"
                return f"{left} {self.name} {right}"
            elif self.fixity == 'prefix':
                if len(self.parameter) == 0:
                    return self.name
                tmp = [x.to_string(interested) if interested(x) else '...' for x in self.parameter]
                return f"{self.name}({','.join(str(x) for x in tmp)})" 
            elif self.fixity == 'postfix':
                if len(self.parameter) == 0:
                    return self.name
                tmp = [x.to_string(interested) if interested(x) else '...' for x in self.parameter]
                return f"({','.join(str(x) for x in tmp)}).{self.name}" 
            else:
                return f"Invalid fixity: {self.fixity}"
        return None




@dataclass(frozen=True)
class Syntax(Generic[A, S]):
    """
    The core signature of Syntax is take an Algebra Class and return an Algebra Instance.
    """
    alg: Callable[[Type[Algebra[Any, Any]]], Algebra[A, S]]
    meta: Description = field(default_factory=Description, repr=False)

    def algebra(self, name: str | MethodType | FunctionType, *args: Any, **kwargs: Any) -> Syntax[A, S]:
        """Calling method of underlying algebra.

        Allows calling Algebra instance methods (e.g., cut) by name, if the method 
        is not exposed by Syntax.

        Args:
            name: Method name (string), bound method, or function to invoke.
            *args: Positional arguments passed to the method.
            **kwargs: Keyword arguments passed to the method.

        Returns:
            A new Syntax reflecting the transformed algebra.
        """
        def algebra_run(cls: Type[Algebra[Any, S]]) -> Algebra[Any, S]:
            a = self.alg(cls)
            if isinstance(name, str):
                attr = getattr(a, name, None) or getattr(cls, name, None)
                if attr is None:
                    return a
                if isinstance(attr, (staticmethod, classmethod)):
                    attr = attr.__get__(None, cls)
                elif isinstance(attr, FunctionType):
                    attr = MethodType(attr, a)
                else:
                    return a
                return cast(Algebra[Any, S], attr(*args, **kwargs))
            elif isinstance(name, MethodType):
                f = MethodType(name.__func__, a)
                return cast(Algebra[Any, S], f(*args, **kwargs))
            elif isinstance(name, FunctionType):
                f = MethodType(name, a)
                return cast(Algebra[Any, S], f(*args, **kwargs))
            else:
                return a
        return self.__class__(alg=algebra_run, meta=self.meta)

    def as_(self, typ: Type[B]) -> B:
        return cast(typ, self)  # type: ignore

    def __call__(self, alg: Type[Algebra[Any, Any]]) -> Algebra[A, S]:
        return self.alg(alg)

    def to_string(self, interested: Callable[[Any], bool]) -> Optional[str]:
        return self.meta.to_string(interested)

    def describe(
        self,
        *,
        newline: Optional[str] = None,
        name: Optional[str] = None,
        fixity: Optional[Literal['infix', 'prefix', 'postfix']] = None,
        parameter: Optional[Tuple[Syntax[Any, S], ...]] = None,
    ) -> Syntax[A, S]:
        return self.__class__(
            alg=self.alg,
            meta=self.meta.update(
                name=name, newline=newline, fixity=fixity, parameter=parameter
            ),
        )

    def newline(self, info: str = '') -> Syntax[A, S]:
        return self.describe(newline=info)

    ######################################################## value transformation ########################################################
    def map(self, f: Callable[[A], B]) -> Syntax[B, S]:
        """Map the produced value while preserving state and metadata.

        Args:
            f: Function mapping value A to B.

        Returns:
            Syntax yielding B with the same resulting state.
        """
        return self.__class__(lambda cls: self.alg(cls).map(f), meta=self.meta)  # type: ignore

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
        return self.__class__(lambda cls: self.alg(cls).bimap(f, i), meta=self.meta)  # type: ignore

    def map_all(self, f: Callable[[A, S], Tuple[B, S]]) -> Syntax[B, S]:
        """Map both value and state on success.

        Args:
            f: Function mapping (value, state) to (new_value, new_state).

        Returns:
            Syntax yielding transformed value and state.
        """
        return self.__class__(lambda cls: self.alg(cls).map_all(f), meta=self.meta)  # type: ignore

    def map_error(self, f: Callable[[Optional[Any]], Any]) -> Syntax[A, S]:
        """Transform the error payload when this syntax fails.

        Args:
            f: Function applied to the error payload of Left.

        Returns:
            Syntax that preserves successes and maps failures.
        """
        return self.__class__(lambda cls: self.alg(cls).map_error(f), meta=self.meta)

    def map_state(self, f: Callable[[S], S]) -> Syntax[A, S]:
        """Map the input state before running this syntax.

        Args:
            f: S -> S function applied to the state prior to running.

        Returns:
            Syntax that runs with f(state).
        """
        return self.__class__(lambda cls: self.alg(cls).map_state(f), meta=self.meta)

    def flat_map(self, f: Callable[[A], Algebra[B, S]]) -> Syntax[B, S]:
        """Chain computations where the next step depends on the value.

        Args:
            f: Function mapping value to the next algebra to run.

        Returns:
            Syntax yielding the result of the chained computation.
        """
        return self.__class__(lambda cls: self.alg(cls).flat_map(f))  # type: ignore

    def many(self, *, at_least: int = 1, at_most: Optional[int] = None) -> Syntax[Many[A], S]:
        """Repeat this syntax and collect results into Many.

        Repeats greedily until failure or no progress. Enforces bounds.

        Args:
            at_least: Minimum number of matches (default 1).
            at_most: Optional maximum number of matches.

        Returns:
            Syntax producing Many of values.
        """
        return self.__class__(
            lambda cls: self.alg(cls).many(at_least=at_least, at_most=at_most)  # type: ignore
        ).describe(
            name='*', fixity='prefix', parameter=(self,)
        )  # type: ignore

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
        return left >> self // right

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
                    raise ValueError(f"Bad data shape {a}")

        def i(a: Many[A]) -> Then[A, Choice[Many[Then[B | None, A]], Optional[Nothing]]]:
            if not isinstance(a, Many) or len(a.value) < 1:
                raise ValueError(
                    f"sep_by inverse expect Many with at least one element, got {a}"
                )
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

        ret = ret.bimap(f, i)  # type: ignore
        return ret.describe(name='sep_by', fixity='prefix', parameter=(self, sep))

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

    def optional(self) -> Syntax[Choice[A, Optional[Nothing]], S]:
        """Make this syntax optional.

        Returns a Choice of the value or Nothing when absent.

        Returns:
            Syntax producing Choice of value or Nothing.
        """
        return (self | success(Nothing())).describe(
            name='~', fixity='prefix', parameter=(self,)
        )

    def cut(self) -> Syntax[A, S]:
        """Commit this branch: on failure, prevent trying alternatives.

        Wraps the underlying algebra's cut.

        Returns:
            Syntax that marks downstream failures as committed.
        """
        return self.__class__(lambda cls: self.alg(cls).cut())

    ###################################################### operator overloading #############################################
    def __floordiv__(self, other: Syntax[B, S]) -> Syntax[Then[A, B], S]:
        """Then-left: run both and prefer the left in the result kind.

        Returns Then(kind=LEFT) with both left and right values.

        Args:
            other: Syntax to run after this one.

        Returns:
            Syntax producing Then(left, right, kind=LEFT).
        """
        other = other if isinstance(other, Syntax) else self.lift(other).as_(Syntax[B, S])
        ret: Syntax[Then[A, B], S] = self.__class__(
            lambda cls: self.alg(cls).then_left(other.alg(cls))  # type: ignore
        )  # type: ignore
        return ret.describe(name=ThenKind.LEFT.value, fixity='infix', parameter=(self, other)).as_(Syntax[Then[A, B], S])

    def __rfloordiv__(self, other: Syntax[B, S]) -> Syntax[Then[B, A], S]:
        other = other if isinstance(other, Syntax) else self.lift(other).as_(Syntax[B, S])
        return other.__floordiv__(self)

    def __add__(self, other: Syntax[B, S]) -> Syntax[Then[A, B], S]:
        """Then-both: run both and keep both values.

        Returns Then(kind=BOTH).

        Args:
            other: Syntax to run after this one.

        Returns:
            Syntax producing Then(left, right, kind=BOTH).
        """
        other = other if isinstance(other, Syntax) else self.lift(other).as_(Syntax[B, S])
        ret: Syntax[Then[A, B], S] = self.__class__(
            lambda cls: self.alg(cls).then_both(other.alg(cls))  # type: ignore
        )  # type: ignore
        return ret.describe(name=ThenKind.BOTH.value, fixity='infix', parameter=(self, other)).as_(Syntax[Then[A, B], S])

    def __radd__(self, other: Syntax[B, S]) -> Syntax[Then[B, A], S]:
        other = other if isinstance(other, Syntax) else self.lift(other).as_(Syntax[B, S])
        return other.__add__(self)

    def __rshift__(self, other: Syntax[B, S]) -> Syntax[Then[A, B], S]:
        """Then-right: run both and prefer the right in the result kind.

        Returns Then(kind=RIGHT).

        Args:
            other: Syntax to run after this one.

        Returns:
            Syntax producing Then(left, right, kind=RIGHT).
        """
        other = other if isinstance(other, Syntax) else self.lift(other).as_(Syntax[B, S])
        ret: Syntax[Then[A, B], S] = self.__class__(
            lambda cls: self.alg(cls).then_right(other.alg(cls))  # type: ignore
        )  # type: ignore
        return ret.describe(name=ThenKind.RIGHT.value, fixity='infix', parameter=(self, other)).as_(Syntax[Then[A, B], S])

    def __rrshift__(self, other: Syntax[B, S]) -> Syntax[Then[B, A], S]:
        other = other if isinstance(other, Syntax) else self.lift(other).as_(Syntax[B, S])
        return other.__rshift__(self)

    def __or__(self, other: Syntax[B, S]) -> Syntax[Choice[A, B], S]:
        """Alternative: try this syntax; if it fails uncommitted, try the other.

        Returns a Choice indicating which branch succeeded.

        Args:
            other: Alternative syntax to try on failure.

        Returns:
            Syntax producing Choice.LEFT or Choice.RIGHT.
        """
        other = other if isinstance(other, Syntax) else self.lift(other).as_(Syntax[B, S])
        ret: Syntax[Choice[A, B], S] = self.__class__(
            lambda cls: self.alg(cls).or_else(other.alg(cls))  # type: ignore
        )  # type: ignore
        return ret.describe(name='|', fixity='infix', parameter=(self, other))

    def __ror__(self, other: Syntax[B, S]) -> Syntax[Choice[B, A], S]:
        other = other if isinstance(other, Syntax) else self.lift(other).as_(Syntax[B, S])
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

        return self.map_all(bind_v).describe(name=f'bind({name})', fixity='postfix', parameter=(self,))

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

        return self.bimap(to_f, ito_f).describe(name=f'to({f})', fixity='postfix', parameter=(self,))

    def mark(self, name: str) -> Syntax[Marked[A], S]:
        """Mark the produced value with a name.

        Useful for later bind operations.

        Args:
            name: Identifier to attach to the value.

        Returns:
            Syntax producing Marked(name, value).
        """
        assert valid_name(name), f"Invalid mark name: {name}"

        def mark_s(value: A) -> Marked[A]:
            if isinstance(value, Marked):
                return replace(value, name=name)
            else:
                return Marked(name=name, value=value)

        def imark_s(m: Marked[A]) -> A:
            return m.value if isinstance(m, Marked) else m

        return self.bimap(mark_s, imark_s).describe(name=f'mark("{name}")', fixity='postfix', parameter=(self,))

    def dump_error(self, formatter: Optional[Callable[[Error], None]] = None) -> Syntax[A, S]:
        def dump_error_run(err: Any) -> Any:
            if isinstance(err, Error) and formatter is not None:
                formatter(err)
            return err

        return self.__class__(lambda cls: self.alg(cls).map_error(dump_error_run))

    def debug(
        self,
        label: str,
        formatter: Optional[
            Callable[[Algebra[Any, S], S, Either[Any, Tuple[Any, S]]], None]
        ] = None,
    ) -> Syntax[A, S]:
        return self.__class__(lambda cls: self.alg(cls).debug(label, formatter), meta=self.meta)


    
def lazy(thunk: Callable[[], Syntax[A, S]]) -> Syntax[A, S]:
    return Syntax(lambda cls: cls.lazy(lambda: thunk()(cls))).describe(name='lazy(?)', fixity='postfix') 

def fail(error: Any) -> Syntax[Any, Any]:
    return Syntax(lambda alg: alg.fail(error)).describe(name=f'fail({error})', fixity='prefix')

def success(value: Any) -> Syntax[Any, Any]:
    return Syntax(lambda alg: alg.success(value)).describe(name=f'success({value})', fixity='prefix')

def choice(*parsers: Syntax[Any, S]) -> Syntax[Any, S]:
    """
    A shorthand for writing a chain of syntax combined with '|'.
    """
    return reduce(lambda a, b: a | b, parsers) if len(parsers) > 0 else success(Nothing())

def run(syntax: Syntax[A, S], alg: Type[Algebra[A, S]], use_cache:bool, *args: Any, **kwargs: Any) -> Tuple[Any, FrozenDict[str, Tuple[Any, ...]]] | Tuple[Any, None]:
    """
    Run the syntax over the given algebra, and return the result and bind.
    """
    parser = syntax(alg)
    input: Optional[S] = alg.state(*args, **kwargs)
    if input:
        result = parser.run(input, use_cache=use_cache)
        if isinstance(result, Right):
            return result.value[0], result.value[1].binding.bound()
        assert isinstance(result, Left), "Algebra must return Either[E, Tuple[A, S]]"
        return result.value, None
    else:
        return Error(this=None, message="Algebra failed to create initial state"), None


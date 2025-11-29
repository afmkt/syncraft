from __future__ import annotations
from typing import (
    Optional, List, Any, TypeVar, Generic, Callable, Tuple, cast, Mapping,
    Type, Generator, Hashable, TYPE_CHECKING, Dict
)
from syncraft.ast import AST, Nothing
from dataclasses import dataclass, replace, field
from syncraft.ast import Bimap, ThenKind, Lazy, Then, OrElse, Many, OrElseKind, SyncraftError, Choice, Seq
from syncraft.cache import Cache, LeftRecursionError, Right, Left, Incomplete, Either
from syncraft.constraint import Bindable

from syncraft.utils import callable_str, is_orelse

if TYPE_CHECKING:
    from syncraft.syntax import Syntax, SyntaxSpec, Graph


S = TypeVar('S', bound=Bindable)    
A = TypeVar('A')  # Result type
B = TypeVar('B')  # Mapped result type

SYNCRAFT_CONFIG_KEY = "__syncraft_config__"





YieldChannelType = Incomplete[S]



@dataclass(slots=True)
class Error:
    this: Optional[Any] = None
    message: Optional[str] = None
    error: Optional[Any] = None    
    state: Optional[Any] = None
    committed: bool = field(default=False, compare=False, repr=False, hash=False)
    stack: List[Tuple[Callable[..., Any], int]] = field(default_factory=list, compare=False, repr=False, hash=False)
    depth: Optional[int] = field(default=None, compare=False, repr=False, hash=False)

    @classmethod
    def new(cls, 
            *, 
            this: Any, 
            message: Optional[str] = None, 
            error: Optional[Any] = None, 
            state: Optional[Any] = None,
            committed: bool = False,
            depth: Optional[int] = None,
            stack: List[Any] = [],
            # previous: Optional[Error] = None
            ) -> Error:
        obj = cls.__new__(cls)
        object.__setattr__(obj, 'this', this)
        object.__setattr__(obj, 'message', message)
        object.__setattr__(obj, 'error', error)
        object.__setattr__(obj, 'state', state)
        object.__setattr__(obj, 'committed', committed)
        object.__setattr__(obj, 'stack', stack)
        object.__setattr__(obj, 'depth', depth)
        return obj

    @staticmethod
    def get_syntax(f: Any) -> Syntax | None:
        if isinstance(f, Algebra):  # for Algebra subclasses
            return f.syntax
        elif hasattr(f, 'syntax'):     # for Algebra.run_f, set by Algebra._flag
            return getattr(f, 'syntax')
        elif hasattr(f, 'spec') and hasattr(f, 'alg_f') and f.__class__.__name__ == 'Syntax':  # Duck typing for Syntax
            return f
        return None

    @property
    def syntax(self) -> Syntax | None:
        h = Error.get_syntax(self.this) 
        return h
    
    @property
    def graph(self) -> None | Graph[SyntaxSpec]:
        h = Error.get_syntax(self.this) 
        if h:
            return h.graph()
        return None

    @property
    def spec(self) -> None | SyntaxSpec:
        h = Error.get_syntax(self.this) 
        if h:
            return h.spec
        return None

    @property
    def str_this(self) -> str:
        spec = self.spec
        if spec and hasattr(spec, 'location'):
            if spec.location is not None:
                return f"{spec} ({spec.location})"
        return f"{spec}"


    @property
    def compact(self) -> list[str]:
        lines = []
        deepest = self
        if deepest.state is not None and hasattr(deepest.state, 'line') and hasattr(deepest.state, 'column'):
            if hasattr(deepest.state, 'str_input'):
                lines.append(f"At line: {deepest.state.line if deepest.state.line > 0 else 'N/A'}, column: {deepest.state.column if deepest.state.column > 0 else 'N/A'}, Input: {deepest.state.str_input(ul=False)}")
            else:
                lines.append(f"At line: {deepest.state.line if deepest.state.line > 0 else 'N/A'}, column: {deepest.state.column if deepest.state.column > 0 else 'N/A'}")
            if deepest.error:
                err_str = self._format_error(deepest.error)
                lines.extend(err_str.splitlines())
            elif deepest.message:
                lines.append(f"{deepest.message}")
            return lines
        return [str(self)]

    @property
    def summary(self) -> str:
        deepest = self
        lines = []
        if deepest.state is not None and hasattr(deepest.state, 'line') and hasattr(deepest.state, 'column'):
            if hasattr(deepest.state, 'str_input'):
                ln = f"Error at line {deepest.state.line if deepest.state.line > 0 else 'N/A'}, column {deepest.state.column if deepest.state.column > 0 else 'N/A'}, Input: {{0}}"
                lns = deepest.state.format_input(ln, False)
                lines.extend(lns)
            else:
                lines.append(f"Error at line {deepest.state.line if deepest.state.line > 0 else 'N/A'}, column {deepest.state.column if deepest.state.column > 0 else 'N/A'}")
                
        else:
            lines.append("Error")
        
        # Show the actual error
        if deepest.message:
            lines.append(f"  Message: {deepest.message}")
        if deepest.error:
            lines.append(f"    Cause: {self._format_error(deepest.error)}")
        return "\n".join(lines)

    @staticmethod
    def fmt_stack(stack: List[Tuple[Any, int]], indent: str="") -> List[str]:
        def str_rule(rule: Callable[..., Any]) -> str:
            syn = Error.get_syntax(rule)
            orelse = syn.is_orelse if syn else is_orelse(rule)
            mark = "\u22d4" if orelse else ""
            spec = syn.spec if syn else None
            if spec and hasattr(spec, 'location'):
                if spec.location is not None:
                    return f"{mark}{str(spec)} ({spec.location})"
            if spec is None:
                return f"{mark}{callable_str(rule)}"
            return f"{mark}{str(spec)}"

        lines = []
        if len(stack) > 0:
            rule_counts: Dict[str, int] = {}
            rule_order: List[str] = []
            for entry in stack[::-1]:  # Reverse to show root->leaf progression
                r, pos = entry
                rule = str_rule(r)
                if rule not in rule_counts:
                    rule_counts[rule] = 0
                    rule_order.append(rule)
                rule_counts[rule] += 1
            
            for i, rule in enumerate(rule_order):
                count = rule_counts[rule]
                prefix = f"{indent}└─ " if i == len(rule_order) - 1 else f"{indent}├─ "
                if count > 1:
                    lines.append(f"{prefix}{rule} [{count}x]")
                else:
                    lines.append(f"{prefix}{rule}")
        return lines
        
    @property
    def trace(self) -> str:
        lines = []
        # Show parsing context with duplicate counts (no limit on stack frames)
        stack = self.stack
        if len(stack) > 1:
            lines.append("  Trace:")
            lines.extend(self.fmt_stack(stack, "  "))
            # Count duplicates and group them
        return "\n".join(lines)

    @property
    def contextual(self) -> str:
        return f"\n{self.summary}\n{self.trace}\n"
        
    def _format_error(self, error: Any) -> str:
        """Format error object in a more readable way"""
        # Check if it's a LexerError
        if hasattr(error, 'message') and hasattr(error, 'index') and hasattr(error, 'offender') and hasattr(error, 'expect'):
            # It's a LexerError - let's make it much more readable
            if hasattr(error, 'expect') and error.expect:
                # Handle case where expect might contain a single string with comma-separated values
                expect_items: List[str] = []
                for item in error.expect:
                    item_str = str(item)
                    if ', ' in item_str:
                        # Split comma-separated string into individual items
                        expect_items.extend(s.strip() for s in item_str.split(', '))
                    else:
                        expect_items.append(item_str)
                
                expect_list = sorted(set(expect_items))  # Remove duplicates and sort
                if len(expect_list) == 1:
                    expected_str = f"'{expect_list[0]}'"
                elif len(expect_list) <= 10:
                    quoted_expects = [f"'{e}'" for e in expect_list]
                    expected_str = f"one of {', '.join(quoted_expects)}"
                else:

                    expected_str = f"one of {', '.join(expect_list[0:5])} ... {len(expect_list)} valid inputs"
            else:
                expected_str = "valid input"
            
            if hasattr(error, 'offender') and error.offender is not None:
                got_str = f"'{error.offender}'"
            else:
                got_str = "unexpected input"
            
            if hasattr(error, 'index') and error.index >= 0:
                return f"{error.__class__.__name__}: at {error.index}: expected {expected_str}, got {got_str}"
            else:
                return f"{error.__class__.__name__}: expected {expected_str}, got {got_str}"
        else:
            # For other error types, just convert to string
            return str(error)
        

    def __str__(self) -> str:
        # Use the contextual format by default instead of the full trace
        return self.contextual
    
    


@dataclass(frozen=True, slots=True)        
class Algebra(Generic[A, S]):
######################################################## shared among all subclasses ########################################################
    run_f: Callable[[S, Cache[S]], Generator[YieldChannelType, S, Either[Any, Tuple[A, S]]]]
    syntax: Syntax | None = None

    @property
    def is_orelse(self)->bool:
        return is_orelse(self.run_f)

    @staticmethod
    def _flag(func: Callable[..., Any], **kwargs: Hashable) -> Callable[..., Any]:
        for key, value in kwargs.items():
            object.__setattr__(func, key, value)
        return func

    def flag(self, **kwargs: Hashable) -> Algebra[A, S]:
        Algebra._flag(self.run_f, **kwargs)
        return self
        

    def get(self) -> dict[str, Any]:
        cfg = getattr(self, SYNCRAFT_CONFIG_KEY, {})
        return dict(cfg) if isinstance(cfg, Mapping) else {}

    def with_syntax(self, syntax: Syntax[A, S]) -> Algebra[A, S]:
        return replace(self, syntax=syntax).flag(syntax=syntax)


    @property
    def name(self) -> str:    
        return str(self.syntax)
    
    
    def __call__(self, 
                 input: S, 
                 cache: Cache[S]) -> Generator[YieldChannelType, 
                                                S, 
                                                Either[Any, Tuple[A, S]]]:
        return self.run(input, cache=cache)

    def run(self, 
            input: S, 
            cache: Cache[S]) -> Generator[YieldChannelType, 
                                        S, 
                                        Either[Any, Tuple[A, S]]]:
        try:
            if cache is None:
                return (yield from self.run_f(input, cache))
            else:
                result = (yield from cache.exec(self.run_f, input))
                if isinstance(result, Left):
                    if isinstance(result.value, Error):
                        if not result.value.stack:
                            result.value.stack = cache.stack + [(self.run_f, input.cache_key)]
                            
                return result
            
        except LeftRecursionError as e:
            if e.offender is self.run_f  or len(e.stack) == 0:
                e = e.push(f"\u25cf {self.name}")
            else:
                e = e.push(f"{self.name}")
            raise e
        # except Exception:
        #     exc_type, exc_value, exc_traceback = sys.exc_info()
        #     traceback_details = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        #     err = Error.new(
        #         message="Unexpected error during parsing",
        #         error=traceback_details,
        #         this=self,
        #         state=input,
        #         committed=True,
        #         stack=cache.stack if cache is not None else []
        #     )
        #     return Left.new(err)
        

    def as_(self, typ: Type[B])->B:
        return cast(typ, self) # type: ignore
        
    @classmethod
    def lazy(cls, thunk: Callable[[], Algebra[A, S]], flatten:bool) -> Algebra[A, S]:
        def algebra_lazy_run(input: S,
                             cache: Cache[S]) -> Generator[YieldChannelType,
                                                            S,
                                                            Either[Any, Tuple[Any, S]]]:
            alg = thunk()
            result = (yield from alg.run(input, cache))
            match result:
                case Right((value, state)):
                    return Right.new((Lazy(value=value, flatten=flatten, custom_mapping=None), state))
                case _:
                    return result
        return cls(algebra_lazy_run)
    
    @classmethod
    def fail(cls, error: Any) -> Algebra[Any, S]:
        def fail_run(input: S, 
                     cache:Cache[S]) -> Generator[YieldChannelType, 
                                                S, 
                                                Either[Any, Tuple[A, S]]]:
            yield from ()
            return Left.new(Error.new(
                error=error,
                this=cls,
                state=input
            ))
        return cls(fail_run)
    
    @classmethod
    def success(cls, value: Any) -> Algebra[Any, S]:
        def success_run(input: S, 
                        cache:Cache[S]) -> Generator[YieldChannelType, 
                                                    S, 
                                                    Either[Any, Tuple[A, S]]]:
            yield from ()
            return Right.new((value, input))
        return cls(success_run)
    
    
    def cut(self) -> Algebra[A, S]:
        def commit_error(e: Any) -> Error:
            match e:
                case Error():
                    e.committed = True
                    return e
                case _:
                    return Error.new(error=e, this=self, committed=True)
        return self.map_error(commit_error)

    def debug(self, 
              dbg: Callable[[Syntax[A, S], S, Optional[S], A | Any, List[Tuple[Syntax[Any, S], int]]], None]
              ) -> Algebra[A, S]:
        syn1 = self.syntax
        def debug_run(input: S,
                      cache: Cache[S]) -> Generator[YieldChannelType, 
                                                S, 
                                                Either[Any, Tuple[A, S]]]:
            syn = self.syntax
            assert syn, f"{self} doesn't have associated Syntax"    
            assert syn is syn1, f"{syn} != {syn1}"
            stack = []
            for rule, pos in cache.stack:
                s = Error.get_syntax(rule)
                if s is not None:
                    stack.append((s, pos))
            result = yield from self.run(input, cache)
            error = None
            value = None
            new_state = None
            if isinstance(result, Left):
                error = result.value
            elif isinstance(result, Right):
                assert isinstance(result.value, tuple) and len(result.value) >= 2
                value = result.value[0]
                new_state = result.value[1]
            dbg(syn, input, new_state, error if error is not None else value, stack)
            return result
        return replace(self, run_f=debug_run)

    def on_fail(self, func: Callable[[Algebra[A, S], S, Any], Either[Any, Tuple[B, S]]]) -> Algebra[A | B, S]:
        assert callable(func), "func must be callable"
        def fail_run(input: S, 
                     cache:Cache[S]) -> Generator[YieldChannelType, 
                                                S, 
                                                Either[Any, Tuple[A|B, S]]]:
            result = yield from self.run(input, cache)
            if isinstance(result, Left):
                return cast(Either[Any, Tuple[A | B, S]], func(self, input, result.value))
            else:
                return cast(Either[Any, Tuple[A | B, S]], result)
        return replace(self, run_f=fail_run) # type: ignore
        

    def on_success(self, func: Callable[[Algebra[A, S], S, Tuple[A, S]], Either[Any, Tuple[B, S]]]) -> Algebra[A | B, S]:
        assert callable(func), "func must be callable"
        def success_run(input: S, 
                        cache:Cache[S]) -> Generator[YieldChannelType, 
                                                    S, 
                                                    Either[Any, Tuple[A|B, S]]]:
            result = yield from self.run(input, cache)
            if isinstance(result, Right):
                return cast(Either[Any, Tuple[A | B, S]], func(self, input, result.value))
            else:
                return cast(Either[Any, Tuple[A | B, S]], result)
        return replace(self, run_f=success_run) # type: ignore
        


######################################################## map on state ###########################################
    def map_state(self, f: Callable[[S], S]) -> Algebra[A, S]:
        def map_state_run(state: S, 
                          cache:Cache[S]) -> Generator[YieldChannelType, 
                                                        S, 
                                                        Either[Any, Tuple[A, S]]]:
            result = yield from self.run(f(state), cache)
            return result
        return replace(self, run_f=map_state_run) 
        


######################################################## fundamental combinators ############################################    
    def map(self, f: Callable[[A], B], *, raw:bool) -> Algebra[B, S]:
        def map_run(input: S, 
                    cache:Cache[S]) -> Generator[YieldChannelType, 
                                                S, 
                                                Either[Any, Tuple[B, S]]]:
            parsed = yield from self.run(input, cache)
            if isinstance(parsed, Right):
                ast, s = parsed.value
                if not raw and isinstance(ast, AST):
                    data:Any = ast.mapped
                else:
                    data = ast 
                # print('calling map', data)
                return Right.new((f(data), s))            
            else:
                return cast(Either[Any, Tuple[B, S]], parsed)
        alg = replace(self, run_f=map_run) # type: ignore
        return cast(Algebra[B, S], alg)
    
    def bimap(self, b: Bimap[A, B]) -> Algebra[A, S]:
        def bimap_f(a: A)->Any:
            assert isinstance(a, AST), f"bimap can only be applied to AST-mapped values, got {type(a)}"
            mapping = a.custom_mapping
            if mapping is not None:
                mapping = mapping >> b
            else:
                mapping = b
            return a.mapping(mapping)
        return self.map(bimap_f, raw=True)
        
    def iso(self, f: Callable[[A], B], i: Callable[[B], A]) -> Algebra[B, S]:
        return self.map(f, raw=True).map_state(lambda s: s.map(i))

    def map_error(self, f: Callable[[Optional[Any]], Any]) -> Algebra[A, S]:
        def map_error_run(input: S, 
                          cache:Cache[S]) -> Generator[YieldChannelType, 
                                                    S, 
                                                    Either[Any, Tuple[A, S]]]:
            parsed = yield from self.run(input, cache)
            if isinstance(parsed, Left):
                return Left.new(f(parsed.value))
            else:
                return parsed
        return replace(self, run_f=map_error_run) 

    def flat_map(self, f: Callable[[A], Algebra[B, S]]) -> Algebra[B, S]:
        def flat_map_run(input: S, 
                         cache:Cache[S]) -> Generator[YieldChannelType, 
                                                    S, 
                                                    Either[Any, Tuple[B, S]]]:
            parsed = yield from self.run(input, cache)
            if isinstance(parsed, Right):
                result = yield from f(parsed.value[0]).run(parsed.value[1], cache)  
                return result
            else:
                return cast(Either[Any, Tuple[B, S]], parsed)
        alg = replace(self, run_f=flat_map_run) # type: ignore
        from typing import cast as _cast
        return _cast(Algebra[B, S], alg)

    def map_all(self, f: Callable[[A, S], Tuple[B, S]]) -> Algebra[B, S]:
        def map_all_f(a : A) -> Algebra[B, S]:
            def map_all_run_f(input:S, 
                              cache:Cache[S]) -> Generator[YieldChannelType, 
                                                        S, 
                                                        Either[Any, Tuple[B, S]]]:
                yield from ()
                return Right.new(f(a, input))
            return replace(self, run_f=map_all_run_f) # type: ignore
        return self.flat_map(map_all_f)


    
    def or_else(self: Algebra[A, S], other: Algebra[B, S]) -> Algebra[OrElse[A, B], S]:
        def or_else_run(input: S, 
                        cache:Cache[S]) -> Generator[YieldChannelType, 
                                                    S,
                                                    Either[Any, Tuple[OrElse[A, B], S]]]:
            inp = input.enter()
            left = yield from self.run(inp, cache)
            match left:
                case Right((value, state)):
                    return Right.new((OrElse(kind=OrElseKind.LEFT, value=value, custom_mapping=None), state.leave()))
                case Left(err) as ERROR:
                    if isinstance(err, Error) and err.committed:
                        return ERROR
                    other_result = yield from other.run(inp, cache)
                    match other_result:
                        case Right((other_value, other_state)):
                            return Right.new((OrElse(kind=OrElseKind.RIGHT, value=other_value, custom_mapping=None), other_state.leave()))
                        case Left() as OTHER_ERROR:
                            return OTHER_ERROR
                    raise SyncraftError(f"Unexpected result type from {other}", offender=other_result, expect=(Left, Right))
            raise SyncraftError(f"Unexpected result type from {self}", offender=left, expect=(Left, Right))
        
        alg = replace(self, run_f=or_else_run) # type: ignore
        return cast(Algebra[OrElse[A, B], S], alg)
        
    @classmethod
    def parallel(cls, 
                 *options: Algebra[Any, S], 
                 reducer: Callable[[S, List[Tuple[Any, S]]], Either[Any, Tuple[Any, S]]],
                 share_cache: bool=True) -> Algebra[Any, S]:
        assert options, "At least one option is required for parallel"
        def parallel_run(input: S,
                         cache: Cache[S]) -> Generator[YieldChannelType, 
                                                  S, 
                                                  Either[Any, Tuple[Any, S]]]:
            inp = input.enter()
            results = []
            if share_cache:
                for opt in options:
                    r = yield from opt.run(inp, cache)
                    if isinstance(r, Right):
                        v, s = r.value
                        results.append((v, s.leave()))
            else:
                for opt in options:
                    new_cache = cache.clone() 
                    r = yield from opt.run(inp, new_cache)
                    if isinstance(r, Right):
                        v, s = r.value
                        results.append((v, s.leave()))
            return reducer(input, results)
        return cls(run_f = parallel_run)
    
    @classmethod
    def choice(cls, *options: Algebra[Any, S]) -> Algebra[Choice[Any], S]:
        assert options, "At least one option is required for choice"

        def choice_run(input: S, 
                       cache:Cache[S]) -> Generator[YieldChannelType, 
                                                  S, 
                                                  Either[Any, Tuple[Choice[Any], S]]]:
            
            inp = input.enter()
            last_error: Optional[Left[Any]] = None
            for i, option in enumerate(options):
                result = yield from option.run(inp, cache)
                match result:
                    case Right((value, state)):

                        return Right.new((Choice(value=value, index=i, custom_mapping=None), state.leave()))
                    case Left(err) as ERROR:

                        if isinstance(err, Error) and err.committed:
                            return ERROR
                        last_error = ERROR

            if last_error is not None:
                return last_error
            else:
                return Left.new(Error.new(
                    message="No options provided",
                    this=cls,
                    state=input
                ))
        return cls(run_f=choice_run) # type: ignore

    @classmethod
    def seq(cls, *steps: Algebra[Any, S] | Tuple[Algebra[Any, S], bool]) -> Algebra[Seq, S]:
        normaize_steps: List[Tuple[Algebra[Any, S], bool]] = [X if isinstance(X, tuple) else (X, True) for X in steps]
        def seq_run(input: S, 
                    cache:Cache[S]) -> Generator[YieldChannelType, 
                                               S, 
                                               Either[Any, Tuple[Seq, S]]]:
            inp = input
            results: List[Tuple[Any, bool]] = []
            for step, keep in normaize_steps:
                result = yield from step.run(inp, cache)
                match result:
                    case Right((value, state)):
                        results.append((value, keep))
                        inp = state
                    case Left() as ERROR:
                        return ERROR
            return Right.new((Seq(value=tuple(results), custom_mapping=None), inp))
        return cls(run_f=seq_run) # type: ignore

    def then_both(self, other: Algebra[B, S]) -> Algebra[Then[A, B], S]:
        def then_both_f(a: A) -> Algebra[Then[A, B], S]:
            def combine(b: B) -> Then[A, B]:
                return Then(left=a, right=b, kind=ThenKind.BOTH, custom_mapping=None)
            return other.map(combine, raw=True)        
        return self.flat_map(then_both_f)
        

    def then_left(self, other: Algebra[B, S]) -> Algebra[Then[A, B], S]:
        def then_left_f(a: A) -> Algebra[Then[A, B], S]:
            def combine(b: B) -> Then[A, B]:
                return Then(left=a, right=b, kind=ThenKind.LEFT, custom_mapping=None)
            return other.map(combine, raw=True)
        return self.flat_map(then_left_f)
        

    def then_right(self, other: Algebra[B, S]) -> Algebra[Then[A, B], S]:
        def then_right_f(a: A) -> Algebra[Then[A, B], S]:
            def combine(b: B) -> Then[A, B]:
                return Then(left=a, right=b, kind=ThenKind.RIGHT, custom_mapping=None)
            return other.map(combine, raw=True)        
        return self.flat_map(then_right_f)

    @classmethod
    def eof(cls) -> Algebra[type[Nothing], S]:
        def eof_run(input: S, 
                    cache:Cache[S]) -> Generator[YieldChannelType, 
                                               S, 
                                               Either[Any, Tuple[type[Nothing], S]]]:
            if input.ended:
                yield from ()
                return Right.new((Nothing, input))
            else:
                return Left.new(Error.new(
                    message="Expected end of input",
                    this=cls,
                    state=input,
                ))
        return cls(run_f=eof_run) # type: ignore        

    def many(self, *, at_least: int, at_most: Optional[int]) -> Algebra[Many[A], S]:
        assert at_least >= 0, "at_least must be non-negative"
        assert at_most is None or at_least <= at_most, "at_least must <= at_most"
        def many_run(input: S, 
                     cache:Cache[S]) -> Generator[YieldChannelType, 
                                                S, 
                                                Either[Any, Tuple[Many[A], S]]]:
            ret: List[A] = []
            current_input = input
            inner_error = None
            while True:
                current_cache_key = current_input.cache_key
                result = yield from self.run(current_input, cache)
                match result:
                    case Left():
                        inner_error = result
                        break
                    case Right((value, next_input)):
                        if next_input.cache_key == current_cache_key:
                            break  # No progress, stop to avoid infinite loop
                        elif value is not Nothing:
                            ret.append(value)
                        current_input = next_input
                        if at_most is not None and len(ret) > at_most:
                            return Left.new(Error.new(
                                    message=f"Expected at most {at_most} matches, got {len(ret)}",
                                    this=self,
                                    state=current_input
                                )) 
            if len(ret) < at_least:
                if inner_error is not None:
                    return inner_error
                else:
                    return Left.new(Error.new(
                            message=f"Expected at least {at_least} matches, got {len(ret)}",
                            this=self,
                            state=current_input
                        )) 
            return Right.new((Many(value=tuple(ret), custom_mapping=None), current_input))
        return replace(self, run_f=many_run) # type: ignore
    

    



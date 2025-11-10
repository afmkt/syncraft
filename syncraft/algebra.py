from __future__ import annotations
from typing import (
    Optional, List, Any, TypeVar, Generic, Callable, Tuple, cast, Mapping,
    Type, Generator, Union, Hashable, TYPE_CHECKING, Dict
)
from syncraft.ast import AST, Ignore
from dataclasses import dataclass, replace, field
from syncraft.ast import ThenKind, Lazy, Then, Choice, Many, ChoiceKind, SyncraftError
from syncraft.cache import Cache, LeftRecursionError, Right, Left, Incomplete, Either
from syncraft.constraint import Bindable

if TYPE_CHECKING:
    from syncraft.syntax import Syntax, SyntaxSpec, Graph


S = TypeVar('S', bound=Bindable)    
A = TypeVar('A')  # Result type
B = TypeVar('B')  # Mapped result type

SYNCRAFT_CONFIG_KEY = "__syncraft_config__"





YieldChannelType = Incomplete[S] 
SendChannelType = Union[S, Either[Any, Tuple[A, S]]]




@dataclass(frozen=True)
class Error:
    this: Optional[Any] = None
    message: Optional[str] = None
    error: Optional[Any] = None    
    state: Optional[Any] = None
    committed: bool = field(default=False)
    previous: Optional[Error] = field(default=None)
    depth: Optional[int] = field(default=None)

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
        if spec and hasattr(spec, 'file') and hasattr(spec, 'line') and spec.file and spec.line:
            return f"{spec} ({spec.file}:{spec.line})"
        return f"{spec}"


    @property
    def compact(self) -> list[str]:
        lines = []
        deepest = self.deepest
        if deepest.state is not None and hasattr(deepest.state, 'line') and hasattr(deepest.state, 'column'):
            if hasattr(deepest.state, 'str_input'):
                lines.append(f"At line: {deepest.state.line if deepest.state.line > 0 else 'N/A'}, column: {deepest.state.column if deepest.state.column > 0 else 'N/A'}, Input: {deepest.state.str_input(ul=False)}")
            else:
                lines.append(f"At line: {deepest.state.line if deepest.state.line > 0 else 'N/A'}, column: {deepest.state.column if deepest.state.column > 0 else 'N/A'}")
            if deepest.error:
                lines.append(f"{self._format_error(deepest.error)}")
            elif deepest.message:
                lines.append(f"{deepest.message}")
            lines.append(f"{deepest.str_this}")
            return lines
        return [str(self)]

    @property
    def summary(self) -> str:
        deepest = self.deepest
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
        
    @property
    def trace(self) -> str:
        lines = []
        # Show parsing context with duplicate counts (no limit on stack frames)
        stack = self.list
        if len(stack) > 1:
            lines.append("  Trace:")
            # Count duplicates and group them
            rule_counts: Dict[str, int] = {}
            rule_order: List[str] = []
            for entry in stack[::-1]:  # Reverse to show root->leaf progression
                rule = entry.str_this
                if rule not in rule_counts:
                    rule_counts[rule] = 0
                    rule_order.append(rule)
                rule_counts[rule] += 1
            
            for i, rule in enumerate(rule_order):
                count = rule_counts[rule]
                prefix = "  └─ " if i == len(rule_order) - 1 else "  ├─ "
                if count > 1:
                    lines.append(f"{prefix}{rule} [{count}x]")
                else:
                    lines.append(f"{prefix}{rule}")
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
    
    
    def push(self, 
            *,
            this: Optional[Any] = None, 
            message: Optional[str] = None,
            error: Optional[Any] = None, 
            state: Optional[Any] = None) -> Error:
        new = Error(
            this=this,
            error=error,
            message=message,
            state=state
        )
        return replace(new, previous=self)
    
    @property
    def list(self) -> List[Error]:
        lst: List[Error] = []
        current: Optional[Error] = self
        while current is not None:
            lst.append(replace(current, depth=len(lst), previous=None))
            current = current.previous
        return lst
    
    @property
    def deepest(self) -> Error:
        current: Error = self
        while current.previous is not None:
            current = current.previous
        return current


@dataclass(frozen=True)        
class Algebra(Generic[A, S]):
######################################################## shared among all subclasses ########################################################
    run_f: Callable[[S, Cache[S]], Generator[YieldChannelType, SendChannelType, Either[Any, Tuple[A, S]]]]
    syntax: Syntax | None = None

    @staticmethod
    def _flag(func: Callable[..., Any], **kwargs: Hashable) -> Callable[..., Any]:
        for key, value in kwargs.items():
            object.__setattr__(func, key, value)
        return func

    def flag(self, **kwargs: Hashable) -> Algebra[A, S]:
        Algebra._flag(self.run_f, **kwargs)
        return self
        

    def config(self) -> dict[str, Any]:
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
                                                SendChannelType, 
                                                Either[Any, Tuple[A, S]]]:
        return self.run(input, cache=cache)

    def run(self, 
            input: S, 
            cache: Cache[S]) -> Generator[YieldChannelType, 
                                        SendChannelType, 
                                        Either[Any, Tuple[A, S]]]:
        try:
            if cache is None:
                return (yield from self.run_f(input, cache))
            else:
                result = (yield from cache.exec(self.run_f, input))
                match result:
                    case Left(Error() as e):
                        return Left(e.push(this=self, state=input))
                    case _:
                        return result
        except LeftRecursionError as e:
            if e.offender is self.run_f  or len(e.stack) == 0:
                e = e.push(f"\u25cf {self.name}")
            else:
                e = e.push(f"{self.name}")
            raise e
        except Exception as err:
            return Left(Error(
                message="Unexpected error during parsing",
                error=err,
                this=self,
                state=input
            ))
        

    def as_(self, typ: Type[B])->B:
        return cast(typ, self) # type: ignore
        
    @classmethod
    def lazy(cls, thunk: Callable[[], Algebra[A, S]], flatten:bool) -> Algebra[A, S]:
        def algebra_lazy_run(input: S,
                             cache: Cache[S]) -> Generator[YieldChannelType,
                                                            SendChannelType,
                                                            Either[Any, Tuple[Any, S]]]:
            alg = thunk()
            result = (yield from alg.run(input, cache))
            match result:
                case Right((value, state)):
                    return Right((Lazy(value, flatten=flatten), state))
                case _:
                    return result
        return cls(algebra_lazy_run)
    
    @classmethod
    def fail(cls, error: Any) -> Algebra[Any, S]:
        def fail_run(input: S, 
                     cache:Cache[S]) -> Generator[YieldChannelType, 
                                                SendChannelType, 
                                                Either[Any, Tuple[A, S]]]:
            yield from ()
            return Left(Error(
                error=error,
                this=cls,
                state=input
            ))
        return cls(fail_run)
    
    @classmethod
    def success(cls, value: Any) -> Algebra[Any, S]:
        def success_run(input: S, 
                        cache:Cache[S]) -> Generator[YieldChannelType, 
                                                                              SendChannelType, 
                                                                              Either[Any, Tuple[A, S]]]:
            yield from ()
            return Right((value, input))
        return cls(success_run)
    
    
    def cut(self) -> Algebra[A, S]:
        def commit_error(e: Any) -> Error:
            match e:
                case Error():
                    return replace(e, committed=True)
                case _:
                    err = Error(error=e, this=self)
                    return replace(err, committed=True)
        return self.map_error(commit_error)

    

    def on_fail(self, func: Callable[[Algebra[A, S], S, Any], Either[Any, Tuple[B, S]]]) -> Algebra[A | B, S]:
        assert callable(func), "func must be callable"
        def fail_run(input: S, 
                     cache:Cache[S]) -> Generator[YieldChannelType, 
                                                SendChannelType, 
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
                                                    SendChannelType, 
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
                                                                                SendChannelType, 
                                                                                Either[Any, Tuple[A, S]]]:
            result = yield from self.run(f(state), cache)
            return result
        return replace(self, run_f=map_state_run) 
        


######################################################## fundamental combinators ############################################    
    def map(self, f: Callable[[A], B], *, raw:bool) -> Algebra[B, S]:
        def map_run(input: S, 
                    cache:Cache[S]) -> Generator[YieldChannelType, 
                                                SendChannelType, 
                                                Either[Any, Tuple[B, S]]]:
            parsed = yield from self.run(input, cache)
            if isinstance(parsed, Right):
                ast, s = parsed.value
                if not raw and isinstance(ast, AST):
                    data:Any = ast.mapped
                else:
                    data = ast 
                return Right((f(data), s))            
            else:
                return cast(Either[Any, Tuple[B, S]], parsed)
        alg = replace(self, run_f=map_run) # type: ignore
        return cast(Algebra[B, S], alg)
    
        
    def iso(self, f: Callable[[A], B], i: Callable[[B], A]) -> Algebra[B, S]:
        return self.map(f, raw=True).map_state(lambda s: s.map(i))

    def map_error(self, f: Callable[[Optional[Any]], Any]) -> Algebra[A, S]:
        def map_error_run(input: S, 
                          cache:Cache[S]) -> Generator[YieldChannelType, 
                                                    SendChannelType, 
                                                    Either[Any, Tuple[A, S]]]:
            parsed = yield from self.run(input, cache)
            if isinstance(parsed, Left):
                return Left(f(parsed.value))
            else:
                return parsed
        return replace(self, run_f=map_error_run) 

    def flat_map(self, f: Callable[[A], Algebra[B, S]]) -> Algebra[B, S]:
        def flat_map_run(input: S, 
                         cache:Cache[S]) -> Generator[YieldChannelType, 
                                                    SendChannelType, 
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
                                                        SendChannelType, 
                                                        Either[Any, Tuple[B, S]]]:
                yield from ()
                return Right(f(a, input))
            return replace(self, run_f=map_all_run_f) # type: ignore
        return self.flat_map(map_all_f)


    
    def or_else(self: Algebra[A, S], other: Algebra[B, S]) -> Algebra[Choice[A, B], S]:
        def or_else_run(input: S, 
                        cache:Cache[S]) -> Generator[YieldChannelType, 
                                                    SendChannelType,
                                                    Either[Any, Tuple[Choice[A, B], S]]]:
            inp = input.enter()
            left = yield from self.run(inp, cache)
            match left:
                case Right((value, state)):
                    return Right((Choice(kind=ChoiceKind.LEFT, value=value), state.leave()))
                case Left(err):
                    if isinstance(err, Error) and err.committed:
                        return Left(replace(err, committed=False))
                    other_result = yield from other.run(inp, cache)
                    match other_result:
                        case Right((other_value, other_state)):
                            return Right((Choice(kind=ChoiceKind.RIGHT, value=other_value), other_state.leave()))
                        case Left(other_err):
                            return Left(other_err)
                    raise SyncraftError(f"Unexpected result type from {other}", offender=other_result, expect=(Left, Right))
            raise SyncraftError(f"Unexpected result type from {self}", offender=left, expect=(Left, Right))
        
        alg = replace(self, run_f=or_else_run) # type: ignore
        return cast(Algebra[Choice[A, B], S], alg)
        

    def then_both(self, other: Algebra[B, S]) -> Algebra[Then[A, B], S]:
        def then_both_f(a: A) -> Algebra[Then[A, B], S]:
            def combine(b: B) -> Then[A, B]:
                return Then(left=a, right=b, kind=ThenKind.BOTH)
            return other.map(combine, raw=True)        
        return self.flat_map(then_both_f)
        

    def then_left(self, other: Algebra[B, S]) -> Algebra[Then[A, B], S]:
        def then_left_f(a: A) -> Algebra[Then[A, B], S]:
            def combine(b: B) -> Then[A, B]:
                return Then(left=a, right=b, kind=ThenKind.LEFT)
            return other.map(combine, raw=True)
        return self.flat_map(then_left_f)
        

    def then_right(self, other: Algebra[B, S]) -> Algebra[Then[A, B], S]:
        def then_right_f(a: A) -> Algebra[Then[A, B], S]:
            def combine(b: B) -> Then[A, B]:
                return Then(left=a, right=b, kind=ThenKind.RIGHT)
            return other.map(combine, raw=True)        
        return self.flat_map(then_right_f)
        

    def many(self, *, at_least: int, at_most: Optional[int]) -> Algebra[Many[A], S]:
        if at_least < 0 or (at_most is not None and at_most < at_least):
            raise SyncraftError(f"Invalid arguments for many: at_least={at_least}, at_most={at_most}", offender=(at_least, at_most), expect="at_least>=0 and (at_most is None or at_most>=at_least)")
        def many_run(input: S, 
                     cache:Cache[S]) -> Generator[YieldChannelType, 
                                                SendChannelType, 
                                                Either[Any, Tuple[Many[A], S]]]:
            ret: List[A] = []
            current_input = input
            inner_error = None
            while True:
                result = yield from self.run(current_input, cache)
                match result:
                    case Left(E):
                        inner_error = Left(E)
                        break
                    case Right((value, next_input)):
                        if next_input == current_input:
                            break  # No progress, stop to avoid infinite loop
                        elif value is not Ignore:
                            ret.append(value)
                        current_input = next_input
                        if at_most is not None and len(ret) > at_most:
                            return Left(Error(
                                    message=f"Expected at most {at_most} matches, got {len(ret)}",
                                    this=self,
                                    state=current_input
                                )) 
            if len(ret) < at_least:
                if inner_error is not None:
                    return inner_error
                else:
                    return Left(Error(
                            message=f"Expected at least {at_least} matches, got {len(ret)}",
                            this=self,
                            state=current_input
                        )) 
            return Right((Many(value=tuple(ret)), current_input))
        return replace(self, run_f=many_run) # type: ignore
    
    @classmethod
    def parallel(cls, *syntaxes: Syntax[Any, S], last_state: Optional[S], **kwargs:Any) -> Algebra[Tuple[Any, ...], S]:
        def parallel_run(input: S, 
                    cache:Cache[S]) -> Generator[YieldChannelType, 
                                               SendChannelType, 
                                               Either[Any, Tuple[Tuple[Any, ...], S]]]:
            algebras = [syntax(cls, **kwargs) for syntax in syntaxes]
            results: List[Tuple[Syntax[Any, S], Either[Any, Tuple[Tuple[Any, ...], S]]]] = []
            for i, alg in enumerate(algebras):
                result = yield from alg.run(input, cache.clone())
                results.append((syntaxes[i], result))
            return Right((tuple(results), input if last_state is None else last_state))
        return cls(run_f=parallel_run) # type: ignore

    



from __future__ import annotations
from typing import (
    Any, TypeVar, Tuple, Optional, Callable, Hashable,
    List, Generator as PyGenerator, cast
)



import random

from dataclasses import dataclass, replace, field
from syncraft.algebra import (
    Algebra, YieldChannelType, Error
)
from syncraft.algebra import ErrorPriority, EntryCategory


from syncraft.lexerprotocol import LexerBuilder, LexerProtocol
from syncraft.cache import Cache, Either, Left, Right

from syncraft.ast import (
    ParseResult, AST, Alt, Seq,
    Nothing, Lazy,
    Many, Unknown,
    SyncraftError
)
from syncraft.utils import callable_str

from syncraft.syntax import Syntax, RunnerProtocol

from syncraft.bimap import Bindable
from syncraft.input import StreamCursor




T = TypeVar('T', bound=Hashable)

B = TypeVar('B')


def debug_print(*arg, **kwargs) -> None:
    pass
    # from rich import print as rich_print
    # rich_print(*arg, **kwargs)


@dataclass(frozen=True, slots=True)
class GenState(Bindable):
    """
    State object for generator algebra.

    This acts as the primary input for generator transformations. It tracks the current 
    AST (or None/Unknown if pruned), manages randomization via a seed, and utilizes 
    a replay flag to enforce consistency with an existing AST structure.

    The `steps` attribute tracks progress by counting calls to grammar rules (terminals 
    and non-terminals). This serves as a cache key to detect growth and prevent 
    infinite loops during left-recursion.    
    """
    ast: Optional[ParseResult] = None
    replay: bool = False
    seed: int = 0
    steps: int = 0

    def str_input(self, ul: bool) -> str:
        try:
            if not self.ast:
                return "<PRUNED>"
            s = str(self.ast)
            if len(s) > 20:
                return f"{self.ast.__class__.__name__}(...)" # type: ignore
            else:
                return s
        except Exception as e:
            return f"<unrepresentable GenState.ast: {e}>"

    @property
    def ended(self) -> bool:
        return False

    @property
    def cache_key(self) -> int:
        return self.steps

    def __str__(self) -> str:
        try:
            return f"{self.__class__.__name__}(ast={self.ast})"
        except Exception as e:
            return f"<unrepresentable GenState: {e}>"
        
    def unused_cache_key(self) -> int:
        return 0

    def enter(self) -> GenState: 
        return self
    
    def leave(self) -> GenState: 
        return self
    
    
    def apply(self, f: Callable[..., Any]) -> GenState:
        if isinstance(self.ast, (Unknown, Nothing)):
            new_ast = self.ast
        else:
            new_ast = f(self.ast, self.ctx)            
        if new_ast is self.ast:
            return self
        else:
            return replace(self, ast=new_ast)
        
    def advance(self, steps: int = 1) -> GenState:
        return replace(self, steps=self.steps + steps)
    
    def inject(self, a: Any) -> GenState:
        if a is self.ast:
            return self
        return replace(self, ast=a)
    
    def fork(self, tag: Any) -> GenState:
        return replace(self, seed=hash((self.seed, tag)))


    def rng(self, tag: Any = None) -> random.Random:
        return random.Random(self.seed if tag is None else hash((self.seed, tag)))

    @property
    def pruned(self)->bool:
        return isinstance(self.ast, Unknown)
        
            
    
    @classmethod
    def from_ast(cls, 
                 *, 
                 ast: Optional[ParseResult[T]], 
                 seed: int = 0, 
                 replay:bool=False) -> GenState:
        return GenState(ast=ast, seed=seed, replay=replay)
        

@dataclass(frozen=True, slots=True)
class Generator(Algebra[ParseResult[T], GenState]):      

    def bimap(self, 
              f: Callable[[ParseResult[T], Any], Any], 
              i: Callable[[Any, Any], ParseResult[T]]) -> Algebra[Any, GenState]:
        return self.imap(i, entry=EntryCategory.Generate)
    
    def enabled(self, entry: EntryCategory) -> bool:
        return entry in {EntryCategory.Generate, EntryCategory.Format}

    @classmethod
    def seq(cls, *steps: Algebra[Any, GenState] | Tuple[Algebra[Any, GenState], bool]) -> Algebra[Seq, GenState]:
        normaize_steps: List[Tuple[Algebra[Any, GenState], bool]] = [X if isinstance(X, tuple) else (X, True) for X in steps]
        def seq_run(input: GenState, 
                    cache: Cache[GenState]) -> PyGenerator[YieldChannelType, 
                                                           GenState, 
                                                           Either[Any, Tuple[Seq, GenState]]]:
            
            if input.pruned:
                result = []
                for step, keep in normaize_steps:
                    step_result = yield from step.run(input, cache)
                    match step_result:
                        case Left(_) as ERROR:
                            debug_print(f"\nSeq CALLING {callable_str(seq_run)} with input=={input} -> FAILED")
                            return ERROR
                        case Right((value, next_input)):
                            input = next_input
                            result.append((value, keep))

                debug_print(f"\nSeq CALLING {callable_str(seq_run)} with input=={input} -> {Seq(value=tuple([]))}")
                return Right.new((Seq(value=tuple(result)), input))
            else:
                if not input.pruned and not isinstance(input.ast, Seq):
                    debug_print(f"\nSeq CALLING {callable_str(seq_run)} with input=={input} -> FAILED")
                    return Left.new(Error.new(
                        this=input.ast,
                        message=f"Expect Seq got {input.ast}",
                        priority=ErrorPriority.EXPECTED,
                        state=input,
                    ))
                result = []
                ast_seq = cast(Seq, input.ast)
                if len(ast_seq.value) != len(normaize_steps):
                    debug_print(f"\nSeq CALLING {callable_str(seq_run)} with input=={input} -> FAILED with wrong length")
                    return Left.new(Error.new(
                        this=input.ast,
                        message=f"Expect Seq of length {len(normaize_steps)} got {len(ast_seq.value)}",
                        priority=ErrorPriority.EXPECTED,
                        state=input,
                    ))
                inp = input
                for (step, keep), (ast_elem, _) in zip(normaize_steps, ast_seq.value):
                    if input.replay or keep:
                        tmp_state = inp.inject(ast_elem).advance()
                        # debug_print(f"\nSeq CALLING BEFORE {callable_str(step.run_f)} with input.ast=={ast_elem}")
                        step_result = yield from step.run(tmp_state, cache)
                        debug_print(f"\nSeq CALLING {callable_str(step.run_f)} with input=={ast_elem} -> {step_result}")
                    else:
                        tmp_state = inp.inject(Unknown()).advance()
                        step_result = yield from step.run(tmp_state, cache)
                        debug_print(f"\nSeq CALLING {callable_str(step.run_f)} with input=={tmp_state} -> {step_result}")
                    match step_result:
                        case Left() as ERROR:
                            debug_print(f"\nSeq CALLING {callable_str(seq_run)} with input=={input} -> FAILED at step with ast {ast_elem}")
                            return ERROR
                        case Right((value, next_input)):
                            inp = next_input
                            result.append((value, keep))    
                debug_print(f"\nSeq CALLING {callable_str(seq_run)} with input=={input} -> {Seq(value=tuple([]))}")
                return Right.new((Seq(value=tuple(result)), inp))
        return cls(run_f=seq_run).flag(intrinsic=True) # type: ignore        


    def many(self, *, at_least: int, at_most: Optional[int]) -> Algebra[Many, GenState]:
        assert at_least >= 0, "at_least must be non-negative"
        assert at_most is None or at_least <= at_most, "at_least must <= at_most"
        def many_run(input: GenState, 
                     cache:Cache[GenState]) -> PyGenerator[YieldChannelType, 
                                                            GenState, 
                                                            Either[Any, Tuple[Many, GenState]]]:
            if input.pruned:
                ret: List[Any] = []
                tmp_input = input
                forked_input = tmp_input.fork(tag=len(ret)).advance()
                times = forked_input.rng("many_rng").choice(range(at_least, at_most if at_most is not None else at_least + 1))
                while len(ret) < times:
                    match (yield from self.run(forked_input, cache)):
                        case Right((value, new_input)):
                            tmp_input = new_input
                            if value is not Nothing:
                                ret.append(value)
                        case Left(err):
                            raise SyncraftError(
                                "Generator.many pruned path hit Left; generation cannot continue.",
                                offender=err,
                                expect="Right",
                            )                    
                debug_print(f"\nMany CALLING {callable_str(many_run)} with input=={tmp_input} -> {Many(value=tuple([]))}")
                return Right.new((Many(value=tuple(ret)), tmp_input))
            else:
                if not isinstance(input.ast, Many) or input.ast is Nothing:
                    debug_print(f"\nMany CALLING {callable_str(many_run)} with input=={input} -> FAILED")
                    return Left.new(Error.new(
                        this=self,
                        message=f"Expect Many got {input}",
                        priority=ErrorPriority.EXPECTED,
                        state=input,
                    ))
                ret = []
                tmp_state = input
                for x in input.ast.value:
                    tmp_state = tmp_state.inject(x).advance()
                    self_result = yield from self.run(tmp_state, cache) 
                    match self_result:
                        case Right((value, new_state)):
                            tmp_state = new_state
                            if value is Nothing:
                                break
                            ret.append(value)
                            if at_most is not None and len(ret) > at_most:
                                debug_print(f"\nMany CALLING {callable_str(many_run)} with input=={input} -> FAILED with too many matches")
                                return Left.new(Error.new(
                                    message=f"Expected at most {at_most} matches, got {len(ret)}",
                                    this=self,
                                    priority=ErrorPriority.EXPECTED,
                                    state=tmp_state,
                                ))
                        case Left(err):
                            debug_print(f"\nMany CALLING {callable_str(many_run)} with input=={input} -> FAILED with error {err}")
                            break
                if len(ret) != len(input.ast.value):
                    debug_print(f"\nMany CALLING {callable_str(many_run)} with input=={input} -> FAILED with mismatch in number of matches")
                    return Left.new(Error.new(
                        message=f"`Many` expected {len(input.ast.value)} matches, got {len(ret)}",
                        this=self,
                        priority=ErrorPriority.EXPECTED,
                        state=tmp_state,
                    ))
                if len(ret) < at_least:
                    debug_print(f"\nMany CALLING {callable_str(many_run)} with input=={input} -> FAILED with too few matches")
                    return Left.new(Error.new(
                        message=f"Expected at least {at_least} matches, got {len(ret)}",
                        this=self,
                        priority=ErrorPriority.EXPECTED,
                        state=tmp_state,
                    )) 
                debug_print(f"\nMany CALLING {callable_str(many_run)} with input=={input} -> {Many(value=tuple([]))}")
                return Right.new((Many(value=tuple(ret)), tmp_state))
        return replace(self, run_f=many_run).flag(intrinsic=True)  # type: ignore
    
 
    @classmethod
    def success(cls, value: Any) -> Algebra[Any, GenState]:
        def success_run(input: GenState, cache: Cache[GenState] | None) -> PyGenerator[YieldChannelType, 
                                                                                     GenState,
                                                                                     Either[Any, Tuple[Any, GenState]]]:
            yield from ()
            if input.pruned:
                return Right.new((value, input))
            elif value != input.ast:
                debug_print(f"\nSuccess CALLING {callable_str(success_run)} with input=={input} -> {value}")
                return Left.new(Error.new(
                    message=f"Success expected {value} but got {input}",
                    this=cls,
                    priority=ErrorPriority.LEXER_VERIFICATION,
                    state=input,
                ))
            else:
                debug_print(f"\nSuccess CALLING {callable_str(success_run)} with input=={input} -> {value}")
                return Right.new((value, input))
        return cls(success_run)



    @classmethod
    def alt(cls, *options: Algebra[Any, GenState]) -> Algebra[Alt, GenState]:
        assert options, "At least one option is required for choice"
        def alt_run(input: GenState, cache: Cache[GenState] | None) -> PyGenerator[YieldChannelType, 
                                                                                     GenState, 
                                                                                     Either[Any, Tuple[Alt, GenState]]]:
            if input.pruned:
                indexes = list(range(len(options)))
                forked_input = input.fork(tag="alt").advance()
                forked_input.rng("alt_index").shuffle(indexes)
                for idx in indexes:
                    selected = options[idx]
                    result = yield from selected.run(forked_input, cache)
                    match result:
                        case Right((value, next_input)):
                            debug_print(f"\nAlt CALLING {callable_str(alt_run)} with input=={input} -> {Alt(index=idx, value=...)}")
                            return Right.new((Alt(index=idx, value=value), next_input))
                        case Left() as ERROR:
                            last_error = ERROR
                            debug_print(f"\nAlt CALLING {callable_str(alt_run)} with input=={input} -> FAILED")
                            
                if last_error is not None:
                    return last_error
                else:
                    return Left.new(Error.new(
                        message=f"Alt, no branch match the given input {input}",
                        this=cls,
                        priority=ErrorPriority.ALT_NO_MATCH,
                        state=input,
                    ))
            else:                    
                if not isinstance(input.ast, (Alt, Nothing)):
                    debug_print(f"\nAlt CALLING {callable_str(alt_run)} with input=={input} -> FAILED")
                    return Left.new(Error.new(
                        this=input.ast,
                        message=f"Expect Alt got {input}",
                        priority=ErrorPriority.EXPECTED,
                        state=input,
                    ))
                ast_choice = input.ast if isinstance(input.ast, Alt) else Alt(index=1, value=Nothing)
                if ast_choice.index is None:
                    for i, option in enumerate(options):
                        tmp_state = input.inject(ast_choice.value).advance()
                        result = yield from option.run(tmp_state, cache)
                        match result:
                            case Right((value, next_input)):
                                debug_print(f"\nAlt CALLING {callable_str(alt_run)} with input=={input} -> {Alt(index=i, value=...)}")
                                return Right.new((Alt(index=i, value=value), next_input))
                            case Left(err) as ERROR:
                                if isinstance(err, Error) and err.committed:
                                    debug_print(f"\nAlt CALLING {callable_str(alt_run)} with input=={input} -> FAILED with committed error")
                                    return ERROR
                    debug_print(f"\nAlt CALLING {callable_str(alt_run)} with input=={input} -> FAILED")
                    return Left.new(Error.new(
                        this=input.ast,
                        message=f"No branch matched for {input}",
                        priority=ErrorPriority.ALT_NO_MATCH,
                        state=input,
                    ))
                else:
                    selected = options[ast_choice.index]
                    tmp_state = input.inject(ast_choice.value).advance()
                    result = yield from selected.run(tmp_state, cache)
                    match result:
                        case Right((value, next_input)):
                            debug_print(f"\nAlt CALLING {callable_str(alt_run)} with input=={input} -> {Alt(index=ast_choice.index, value=...)}")
                            return Right.new((Alt(index=ast_choice.index, value=value), next_input))
                        case Left() as ERROR:
                            debug_print(f"\nAlt CALLING {callable_str(alt_run)} with input=={input} -> FAILED")
                            return ERROR
            raise SyncraftError("alt should always return a value or an error.", offender=result, expect=(Left, Right))
        return cls(run_f=alt_run).flag(intrinsic=True)  # type: ignore
    

    @classmethod
    def lazy(cls, thunk: Callable[[], Algebra[ParseResult[T], GenState]]) -> Algebra[ParseResult[T], GenState]:
        def algebra_lazy_run(input: GenState,
                             cache: Cache[GenState] | None) -> PyGenerator[YieldChannelType,
                                                                        GenState,
                                                                        Either[Any, Tuple[ParseResult[T], GenState]]]:
            
            alg = thunk()            
            if input.pruned:
                result = (yield from alg.run(input, cache))
                match result:
                    case Left() as ERROR:
                        debug_print(f"\nLazy CALLING {callable_str(algebra_lazy_run)} with input=={input} -> FAILED")
                        return ERROR
                    case Right((value, state)):
                        debug_print(f"\nLazy CALLING {callable_str(algebra_lazy_run)} with input=={input} -> {Lazy(value=...)}")
                        return Right.new((Lazy(value=value), state))
                    case _:
                        raise SyncraftError(f"Unexpected result type from lazy algebra {alg}", offender=result)
            else:
                current = input.ast
                if not isinstance(current, Lazy) or current is Nothing:
                    debug_print(f"\nLazy CALLING {callable_str(algebra_lazy_run)} with input=={input} -> FAILED")
                    return Left.new(Error.new(this=alg, 
                                      message=f"Expect Lazy got {input}",
                                      state=input))
                new_state = input.inject(current.value).advance()
                result = (yield from alg.run(new_state, cache))
                match result:
                    case Left() as ERROR:
                        debug_print(f"\nLazy CALLING {callable_str(algebra_lazy_run)} with input=={input} -> FAILED")
                        return ERROR
                    case Right((value, state)):
                        debug_print(f"\nLazy CALLING {callable_str(algebra_lazy_run)} with input=={input} -> {Lazy(value=...)}")
                        return Right.new((Lazy(value=value), state))
                    case _:
                        raise SyncraftError(f"Unexpected result type from lazy algebra {alg}", offender=result) 
        return cls(algebra_lazy_run).flag(intrinsic=True)
    

        
    @classmethod
    def lex(cls, builder: LexerBuilder[Any]) -> Algebra[ParseResult[T], GenState]:
        assert builder, "LexerBuilder could not be None"
        def lex_run(input: GenState, 
                    cache: Cache[GenState] | None) -> PyGenerator[
                              YieldChannelType, 
                              GenState, 
                              Either[Any, Tuple[ParseResult[T], GenState]]]:
            
            lexer: LexerProtocol[Any] = builder.resolve()
            lexer.reset()

            yield from ()
            
            if input.pruned:
                gt = lexer.gen(input.rng())
                generated = gt.value
                debug_print(f"\nLex CALLING {callable_str(lex_run)} with input=={input} -> {generated}")
                return Right.new((cast(ParseResult[T], generated), input.advance(gt.steps)))
            else:
                current = input.ast
                current_value = current
                try:
                    verified = lexer.verify(current_value)
                except SyncraftError as e:
                    debug_print(f"\nLex CALLING {callable_str(lex_run)} with input=={input} -> FAILED")
                    return Left.new(
                        Error.new(
                            this=lex_run,
                            message=(
                                f"{current_value} failed lexer verification. "
                                "This usually means the grammar's inverse mapping returns a shape "
                                "that does not match the lexer input type."
                            ),
                            error=e,
                            priority=ErrorPriority.LEXER_VERIFICATION,
                            state=input,
                        )
                    )
                if not verified.ok:
                    debug_print(f"\nLex CALLING {callable_str(lex_run)} with input=={input} -> FAILED")
                    return Left.new(
                        Error.new(
                            this=lex_run,
                            message=f"Unexpected token {current}: {type(current)}.",
                            priority=ErrorPriority.EXPECTED_TOKEN_TAG,
                            state=input,
                        )
                    )
                parsed_value = cast(ParseResult[T], current)
                if isinstance(parsed_value, AST):
                    parsed_value = replace(parsed_value) # type: ignore
                debug_print(f"\nLex CALLING {callable_str(lex_run)} with input=={input} -> {parsed_value}")
                return Right.new((parsed_value, input.advance(verified.steps)))

        return cls(lex_run).flag(intrinsic=True) 


@dataclass(frozen=True, slots=True)
class Validator(Generator[T]):
    def enabled(self, entry: EntryCategory) -> bool:
        return entry == EntryCategory.Generate


@dataclass
class Runner(RunnerProtocol[ParseResult, GenState]):
    ast : ParseResult = Unknown()
    seed: int = field(default_factory=lambda: random.randint(0, 2**32 - 1))
    replay: bool = False

    def resume(self, request: Optional[GenState], cursor: Optional[StreamCursor[Any]]) -> GenState:
        if request is None:
            return GenState.from_ast(ast=self.ast, seed=self.seed, replay=self.replay)
        raise SyncraftError("Generator does not support resuming from Incomplete states.", offender=request, expect="Not Incomplete")




def generator(syntax: Syntax) -> Algebra:
    """Build a generator algebra for a syntax.

    This is a low-level helper used by ``Grammar`` and runner APIs.
    """
    runner: Runner = Runner()
    return runner.algebra(syntax=syntax, alg_cls=Generator)

def validator(syntax: Syntax) -> Algebra:
    """Build a validator algebra for a syntax.

    Validation reuses generation machinery with replay-constrained behavior.
    """
    runner: Runner = Runner()
    return runner.algebra(syntax=syntax, alg_cls=Validator)
    
def generate_with(
    syntax: Syntax, 
    data: Optional[ParseResult] = None, 
    seed: Optional[int] = None,
    replay: bool = False
) -> AST:    
    """Generate an AST-like value from ``syntax``.

    Args:
        syntax: Syntax to generate with.
        data: Optional source value/AST. ``None`` is treated as ``Unknown()``.
        seed: Optional random seed for reproducible stochastic choices.
        replay: When ``True``, replay provided structure instead of freely
            sampling pruned/implicit parts.

    Returns:
        AST-like value extracted from generated ``LayoutDoc``.
    """
    from syncraft.format import LayoutDoc
    ret = syntax.generate(data=data, seed=seed, replay=replay)
    if isinstance(ret, LayoutDoc):
        return ret.ast
    return ret
    

def validate(syntax: Syntax, data: ParseResult[Any]) -> AST:
    """Validate ``data`` against ``syntax`` via replay-constrained generation."""
    return generate_with(syntax=syntax, data=data, seed=0, replay=True)

def generate(syntax, seed: Optional[int] = None) -> AST:
    """Generate from ``syntax`` with stochastic mode enabled by default."""
    return generate_with(syntax=syntax, data=None, seed=seed, replay=False)
    


    


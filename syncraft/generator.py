from __future__ import annotations
from typing import (
    Any, TypeVar, Tuple, Optional, Callable, Dict, Hashable,
    List, Generator as PyGenerator, cast, Self
)



import random

from dataclasses import dataclass, replace, field
from syncraft.algebra import (
    Algebra, YieldChannelType, Error
)

from syncraft.lexer import LexerBase, LexerProtocol
from syncraft.cache import Cache, Either, Left, Right

from syncraft.ast import (
    ParseResult, AST, Alt, Seq,
    Nothing, Lazy,
    Many, Unknown,
    SyncraftError
)
from syncraft.utils import callable_str

from syncraft.fa import Builder
from syncraft.token import TokenSpec
from syncraft.syntax import Syntax, RunnerProtocol

from syncraft.bimap import Bindable
from syncraft.input import StreamCursor




T = TypeVar('T', bound=Hashable)

B = TypeVar('B')


def debug_print(*arg, **kwargs) -> None:
    pass
    # print(*arg, **kwargs)

@dataclass(frozen=True, slots=True)
class GenState(Bindable):

    ast: Optional[ParseResult] = None
    restore_pruned: bool = False
    seed: int = 0
    id_cache: Dict[Any, int] = field(default_factory=dict, compare=False, hash=False, repr=False)

    def str_input(self, ul: bool) -> str:
        if not self.ast:
            return "<PRUNED>"
        s = str(self.ast)
        if len(s) > 20:
            return f"{self.ast.__class__.__name__}(...)"
        else:
            return s


    @property
    def ended(self) -> bool:
        return False

    def __post_init__(self):
        if self.ast is not None:
            self.mark_id(self.ast)

    def mark_id(self, data: Any) -> Any:
        if data not in self.id_cache:
            self.id_cache[data] = id(data)
        return data

    def transfer_id(self, source: Any, target: Any) -> None:
        if target not in self.id_cache and source in self.id_cache:
            self.id_cache[target] = self.id_cache[source]
            

    def get_id(self, data: Any) -> int:
        assert data in self.id_cache, f"Data object {data} does not have a generator state position marker"
        return self.id_cache[data]


    def __str__(self) -> str:
        return f"{self.__class__.__name__}(ast={self.ast})"
        
    def unused_cache_key(self) -> int:
        return 0

    def enter(self) -> Self: 
        return self
    
    def leave(self) -> Self: 
        return self
    
    
    def apply(self, f: Callable[..., Any]) -> GenState:
        if isinstance(self.ast, Unknown):            
            new_ast = self.ast
        else:
            new_ast = f(self.ast, self.ctx)            
        if new_ast is self.ast:
            return self
        else:
            self.transfer_id(self.ast, new_ast)
            return replace(self, ast=new_ast)
        

    @property
    def cache_key(self) -> int:
        return self.get_id(self.ast) 

    
    def inject(self, a: Any) -> GenState:
        return replace(self, ast=self.mark_id(a))
    
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
                 restore_pruned:bool=False) -> GenState:
        return GenState(ast=ast, seed=seed, restore_pruned=restore_pruned)
        

@dataclass(frozen=True, slots=True)
class Generator(Algebra[ParseResult[T], GenState]):      
    def bimap(self, 
              f: Callable[[ParseResult[T], Any], Any], 
              i: Callable[[Any, Any], ParseResult[T]]) -> Algebra[Any, GenState]:
        return self.imap(i)



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
                            debug_print(f"\nCALLING SEQ {callable_str(seq_run)} with {input.ast} -> FAILED")
                            return ERROR
                        case Right((value, next_input)):
                            input = next_input
                            result.append((value, keep))
                debug_print(f"\nCALLING SEQ {callable_str(seq_run)} with {input.ast} -> {Seq(value=tuple(result))}")
                return Right.new((Seq(value=tuple(result)), input))
            else:
                if not input.pruned and not isinstance(input.ast, Seq):
                    debug_print(f"\nCALLING SEQ {callable_str(seq_run)} with {input.ast} -> FAILED")
                    return Left.new(Error.new(this=input.ast, 
                                        message=f"Expect Seq got {input.ast}",
                                        state=input))
                result = []
                ast_seq = cast(Seq, input.ast)
                if len(ast_seq.value) != len(normaize_steps):
                    debug_print(f"\nCALLING SEQ {callable_str(seq_run)} with {input.ast} -> FAILED with wrong length")
                    return Left.new(Error.new(this=input.ast, 
                                        message=f"Expect Seq of length {len(normaize_steps)} got {len(ast_seq.value)}",
                                        state=input))
                inp = input
                for (step, keep), (ast_elem, _) in zip(normaize_steps, ast_seq.value):
                    if input.restore_pruned or keep:
                        tmp_state = inp.inject(ast_elem)
                        step_result = yield from step.run(tmp_state, cache)
                        debug_print(f"\nCALLING SEQ {callable_str(step.run_f)} with {ast_elem} -> {step_result}")
                    else:
                        tmp_state = inp.inject(Unknown())
                        step_result = yield from step.run(tmp_state, cache)
                        debug_print(f"\nCALLING SEQ {callable_str(step.run_f)} with {tmp_state.ast} -> {step_result}")
                    match step_result:
                        case Left() as ERROR:
                            debug_print(f"\nCALLING SEQ {callable_str(seq_run)} with {input.ast} -> FAILED at step with ast {ast_elem}")
                            return ERROR
                        case Right((value, next_input)):
                            inp = next_input
                            result.append((value, keep))    
                debug_print(f"\nCALLING SEQ {callable_str(seq_run)} with {input.ast} -> {Seq(value=tuple(result))}")
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
                while True:
                    forked_input = input.fork(tag=len(ret))
                    match (yield from self.run(forked_input, cache)):
                        case Right((value, _)):
                            if value is not Nothing:
                                ret.append(value)
                        case Left(_):
                            pass
                    if len(ret) >= at_least:
                        if (at_most is None or len(ret) < at_most):
                            if not forked_input.rng("many_continue").choice((True, False)):
                                break
                debug_print(f"\nCALLING MANY {callable_str(many_run)} with {input.ast} -> {Many(value=tuple(ret))}")
                return Right.new((Many(value=tuple(ret)), input))
            else:
                if not isinstance(input.ast, Many) or input.ast is Nothing:
                    debug_print(f"\nCALLING {callable_str(many_run)} with {input.ast} -> FAILED")
                    return Left.new(Error.new(this=self, 
                                      message=f"Expect Many got {input.ast}",
                                      state=input))
                ret = []
                tmp_state = input
                for x in input.ast.value:
                    tmp_state = input.inject(x)
                    self_result = yield from self.run(tmp_state, cache) 
                    match self_result:
                        case Right((value, _)):
                            if value is not Nothing:
                                ret.append(value)
                            if at_most is not None and len(ret) > at_most:
                                debug_print(f"\nCALLING {callable_str(many_run)} with {input.ast} -> FAILED with too many matches")
                                return Left.new(Error.new(
                                        message=f"Expected at most {at_most} matches, got {len(ret)}",
                                        this=self,
                                        state=tmp_state
                                    ))                             
                        case Left(_):
                            pass
                if len(ret) < at_least:
                    debug_print(f"\nCALLING {callable_str(many_run)} with {input.ast} -> FAILED with too few matches")
                    return Left.new(Error.new(
                        message=f"Expected at least {at_least} matches, got {len(ret)}",
                        this=self,
                        state=tmp_state
                    )) 
                debug_print(f"\nCALLING {callable_str(many_run)} with {input.ast} -> {Many(value=tuple(ret))}")
                return Right.new((Many(value=tuple(ret)), input))
        return replace(self, run_f=many_run).flag(intrinsic=True)  # type: ignore
    
 
    @classmethod
    def alt(cls, *options: Algebra[Any, GenState]) -> Algebra[Alt, GenState]:
        assert options, "At least one option is required for choice"
        def alt_run(input: GenState, cache: Cache[GenState]) -> PyGenerator[YieldChannelType, 
                                                                                     GenState, 
                                                                                     Either[Any, Tuple[Alt, GenState]]]:
            if input.pruned:
                indexes = list(range(len(options)))
                forked_input = input.fork(tag="alt")
                forked_input.rng("alt_index").shuffle(indexes)
                for idx in indexes:
                    selected = options[idx]
                    result = yield from selected.run(forked_input, cache)
                    match result:
                        case Right((value, next_input)):
                            debug_print(f"\nCALLING {callable_str(alt_run)} with {input.ast} -> {Alt(index=idx, value=value)}")
                            return Right.new((Alt(index=idx, value=value), next_input))
                        case Left() as ERROR:
                            last_error = ERROR
                            debug_print(f"\nCALLING {callable_str(alt_run)} with {input.ast} -> FAILED")
                            
                if last_error is not None:
                    return last_error
                else:
                    return Left.new(Error.new(
                        message="No options provided",
                        this=cls,
                        state=input
                    ))
            else:
                if not isinstance(input.ast, Alt):
                    debug_print(f"\nCALLING {callable_str(alt_run)} with {input.ast} -> FAILED")
                    return Left.new(Error.new(this=input.ast, 
                                      message=f"Expect Alt got {input.ast}",
                                      state=input))
                ast_choice = input.ast
                if ast_choice.index is None:
                    for i, option in enumerate(options):
                        tmp_state = input.inject(ast_choice.value)
                        result = yield from option.run(tmp_state, cache)
                        match result:
                            case Right((value, next_input)):
                                debug_print(f"\nCALLING {callable_str(alt_run)} with {input.ast} -> {Alt(index=i, value=value)}")
                                return Right.new((Alt(index=i, value=value), next_input))
                            case Left(err) as ERROR:
                                if isinstance(err, Error) and err.committed:
                                    debug_print(f"\nCALLING {callable_str(alt_run)} with {input.ast} -> FAILED with committed error")
                                    return ERROR
                    debug_print(f"\nCALLING {callable_str(alt_run)} with {input.ast} -> FAILED")
                    return Left.new(Error.new(this=input.ast, 
                                      message=f"None of the choices matched for {input.ast}",
                                      state=input))
                else:
                    selected = options[ast_choice.index]
                    tmp_state = input.inject(ast_choice.value)
                    result = yield from selected.run(tmp_state, cache)
                    match result:
                        case Right((value, next_input)):
                            debug_print(f"\nCALLING {callable_str(alt_run)} with {input.ast} -> {Alt(index=ast_choice.index, value=value)}")
                            return Right.new((Alt(index=ast_choice.index, value=value), next_input))
                        case Left() as ERROR:
                            debug_print(f"\nCALLING {callable_str(alt_run)} with {input.ast} -> FAILED")
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
                        debug_print(f"\nCALLING {callable_str(algebra_lazy_run)} with {input.ast} -> FAILED")
                        return ERROR
                    case Right((value, state)):
                        debug_print(f"\nCALLING {callable_str(algebra_lazy_run)} with {input.ast} -> {Lazy(value=value)}")
                        return Right.new((Lazy(value=value), state))
                    case _:
                        raise SyncraftError(f"Unexpected result type from lazy algebra {alg}", offender=result)
            else:
                current = input.ast
                if not isinstance(current, Lazy) or current is Nothing:
                    debug_print(f"\nCALLING {callable_str(algebra_lazy_run)} with {current} -> FAILED")
                    return Left.new(Error.new(this=alg, 
                                      message=f"Expect Lazy got {current}",
                                      state=input))
                new_state = input.inject(current.value)
                result = (yield from alg.run(new_state, cache))
                match result:
                    case Left() as ERROR:
                        debug_print(f"\nCALLING {callable_str(algebra_lazy_run)} with {current} -> FAILED")
                        return ERROR
                    case Right((value, state)):
                        debug_print(f"\nCALLING {callable_str(algebra_lazy_run)} with {current} -> {Lazy(value=value)}")
                        return Right.new((Lazy(value=value), state))
                    case _:
                        raise SyncraftError(f"Unexpected result type from lazy algebra {alg}", offender=result) 
        return cls(algebra_lazy_run).flag(intrinsic=True)
    

        
    @classmethod
    def lex(cls, args: Builder | TokenSpec, terminal_cls: Callable[..., Any] | None = None, **kwargs) -> Algebra[ParseResult[T], GenState]:
        terminal_cls = terminal_cls or cls.default_terminal_cls
        lexer:LexerProtocol[Any] | None
        lexer, remaining_kwargs = LexerBase.from_kwargs(args, **kwargs)
        assert lexer, f"Lexer could not be created with the given parameters, {args}, {kwargs}"
        ntags = lexer.tags()
        name = ','.join(str(tag) for tag in ntags)
        def lex_run(input: GenState, 
                    cache: Cache[GenState] | None) -> PyGenerator[
                              YieldChannelType, 
                              GenState, 
                              Either[Any, Tuple[ParseResult[T], GenState]]]:
            lexer.reset()
            yield from ()
            
            if input.pruned:
                
                tag = input.rng("lex_tag").choice(tuple(ntags))
                input = input.fork(tag=tag)
                args, kwargs = lexer.gen(tag, input.rng())
                generated = terminal_cls(*args, **kwargs)
                debug_print(f"\nCALLING {callable_str(lex_run)} with {input.ast} -> {generated}")
                return Right.new((cast(ParseResult[T], generated), input))
            else:
                current = input.ast
                if not lexer.varify(ntags, current):
                    debug_print(f"\nCALLING {callable_str(lex_run)} with {input.ast} -> FAILED")
                    return Left.new(
                            Error.new(
                                this=lex_run,
                                message=f"Expected token tag {name}, but got {current}.",
                                state=input,
                            )
                        )
                parsed_value = cast(ParseResult[T], current)
                if isinstance(parsed_value, AST):
                    parsed_value = replace(parsed_value) # type: ignore
                debug_print(f"\nCALLING {callable_str(lex_run)} with {current} -> {parsed_value}")
                return Right.new((parsed_value, input))

        return cls(lex_run).flag(intrinsic=True) 




@dataclass
class Runner(RunnerProtocol[ParseResult, GenState]):
    ast : ParseResult | None = None
    seed: int = field(default_factory=lambda: random.randint(0, 2**32 - 1))
    restore_pruned: bool = False

    def resume(self, request: Optional[GenState], cursor: Optional[StreamCursor[Any]]) -> GenState:
        if request is None:
            return GenState.from_ast(ast=self.ast, seed=self.seed, restore_pruned=self.restore_pruned)
        raise SyncraftError("Generator does not support resuming from Incomplete states.", offender=request, expect="Not Incomplete")




def generator(syntax: Syntax) -> Algebra:
    runner: Runner = Runner()
    return runner.algebra(syntax=syntax, alg_cls=Generator)

    
    
def generate_with(
    syntax: Syntax, 
    data: Optional[ParseResult] = None, 
    seed: Optional[int] = None,
    restore_pruned: bool = False
) -> AST:
    
    runner = Runner(ast=data if data is not None else Unknown(), 
                    seed=seed if seed is not None else random.randint(0, 2**32 - 1), 
                    restore_pruned=restore_pruned)

    v, s = runner.once(syntax=syntax, alg_cls=Generator, state=None, cursor=None, cache=None)
    return v

def validate(syntax: Syntax, data: ParseResult[Any]) -> AST:
    
    runner = Runner(ast=data, seed=0, restore_pruned=True)
    
    v, s = runner.once(syntax=syntax, alg_cls=Generator, state=None, cursor=None, cache=None)
    return v

def generate(syntax, seed: Optional[int] = None) -> AST:
    
    runner = Runner(ast=Unknown(), 
                    seed=seed if seed is not None else random.randint(0, 2**32 - 1), 
                    restore_pruned=False)
    
    v, s = runner.once(syntax=syntax, alg_cls=Generator, state=None, cursor=None, cache=None)
    return v
    



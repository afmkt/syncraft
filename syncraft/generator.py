from __future__ import annotations

from typing import (
    Any, TypeVar, Tuple, Optional, Callable, Generic, Hashable,
    List, Generator as PyGenerator, cast, Type, Self
)


import random

from dataclasses import dataclass, replace, field
from syncraft.algebra import (
    Algebra, YieldChannelType, Error
)

from syncraft.lexer import LexerBase, Lexer, LexerProtocol
from syncraft.cache import Cache, Either, Left, Right

from syncraft.ast import (
    ParseResult, AST, Token, Choice, Seq,
    Nothing, Lazy,
    OrElse, Many, OrElseKind,
    Then, ThenKind, SyncraftError
)
from syncraft.utils import FrozenDict

from syncraft.fa import Builder
from syncraft.token import TokenSpec
from syncraft.syntax import Syntax, RunnerProtocol

from syncraft.constraint import Bindable, Binding
from syncraft.input import StreamCursor




T = TypeVar('T', bound=Hashable)

B = TypeVar('B')


@dataclass(frozen=True, slots=True)
class GenState(Bindable, Generic[T]):
    binding: Binding = field(default_factory=Binding)
    ast: Optional[ParseResult[T]] = None
    restore_pruned: bool = False
    seed: int = 0

    @property
    def ended(self) -> bool:
        return False

    @classmethod
    def new(cls, 
            binding: Binding,
            ast: Optional[ParseResult[T]],
            restore_pruned: bool,
            seed: int) -> Self:
        obj = cls.__new__(cls)
        object.__setattr__(obj, 'binding', binding)
        object.__setattr__(obj, 'ast', ast)
        object.__setattr__(obj, 'restore_pruned', restore_pruned)
        object.__setattr__(obj, 'seed', seed)
        return obj

    def __str__(self) -> str:
        if isinstance(self.ast, AST):
            return f"{self.__class__.__name__}(ast={self.ast.mapped})"
        else:
            return f"{self.__class__.__name__}(ast={self.ast})"
        
    def unused_cache_key(self) -> int:
        return 0

    def bind(self, name: str, node:Any)->GenState[T]:
        """Return a copy with ``node`` recorded under ``name`` in bindings."""
        return GenState.new(
            binding=self.binding.bind(name, node),
            ast=self.ast,
            restore_pruned=self.restore_pruned,
            seed=self.seed
        )
    
    def replace(self, name: str, node:Any)->GenState[T]:
        """Return a copy with ``node`` replacing existing binding under ``name``."""
        return GenState.new(
            binding=self.binding.replace(name, node),
            ast=self.ast,
            restore_pruned=self.restore_pruned,
            seed=self.seed
        )
    
    @property
    def all_bindings(self) -> FrozenDict[str, Tuple[Any, ...]]:
        """Get all bindings recorded in this ParserState."""
        return self.binding.bindings


    def get(self, name: str, unwrapper: bool=True) -> Tuple[Any, ...] | Any: 
        """Get the binding(s) recorded under ``name``."""
        ret = self.binding.bindings.get(name, ())
        if len(ret) == 1:
            return ret[0] if unwrapper else ret
        elif len(ret) == 0:
            return ... if unwrapper else ()
        else:
            return ret

    def map(self, f: Callable[[Any], Any]) -> GenState[T]:
        return GenState.new(
            binding=self.binding,
            ast=f(self.ast),
            restore_pruned=self.restore_pruned,
            seed=self.seed
        )
    
    @property
    def cache_key(self) -> int:
        return id(self)

    def inject(self, a: Any) -> GenState[T]:
        return self.map(lambda _: a)
    
    def fork(self, tag: Any) -> GenState[T]:
        return GenState.new(
            binding=self.binding,
            ast=self.ast,
            restore_pruned=self.restore_pruned,
            seed=hash((self.seed, tag))
        )


    def rng(self, tag: Any = None) -> random.Random:
        return random.Random(self.seed if tag is None else hash((self.seed, tag)))

    @property
    def pruned(self)->bool:
        return self.ast is None
    
    def left(self)-> GenState[T]:
        if self.ast is None:
            return self
        if isinstance(self.ast, Then) and (self.ast.kind != ThenKind.RIGHT or self.restore_pruned):
            return GenState.new(
                binding=self.binding,
                ast=self.ast.left,
                restore_pruned=self.restore_pruned,
                seed=self.seed
            )
        return GenState.new(
            binding=self.binding,
            ast=None,
            restore_pruned=self.restore_pruned,
            seed=self.seed
        )
        

    def right(self) -> GenState[T]:
        if self.ast is None:
            return self
        if isinstance(self.ast, Then) and (self.ast.kind != ThenKind.LEFT or self.restore_pruned):
            return GenState.new(
                binding=self.binding,
                ast=self.ast.right,
                restore_pruned=self.restore_pruned,
                seed=self.seed
            )
        return GenState.new(
            binding=self.binding,
            ast=None,
            restore_pruned=self.restore_pruned,
            seed=self.seed
        )
        
    
    @classmethod
    def from_ast(cls, 
                 *, 
                 ast: Optional[ParseResult[T]], 
                 seed: int = 0, 
                 restore_pruned:bool=False) -> GenState[T]:
        return cls.new(
            binding=Binding(),
            ast=ast,
            restore_pruned=restore_pruned,
            seed=seed
        )
        

@dataclass(frozen=True, slots=True)
class Generator(Algebra[ParseResult[T], GenState[T]]):      
    @classmethod
    def seq(cls, *steps: Algebra[Any, GenState[T]] | Tuple[Algebra[Any, GenState[T]], bool]) -> Algebra[Seq, GenState[T]]:
        normaize_steps: List[Tuple[Algebra[Any, GenState[T]], bool]] = [X if isinstance(X, tuple) else (X, True) for X in steps]
        def seq_run(input: GenState[T], 
                    cache:Cache[GenState[T]]) -> PyGenerator[YieldChannelType, 
                                                           GenState[T], 
                                                           Either[Any, Tuple[Seq, GenState[T]]]]:
            if not input.pruned and not isinstance(input.ast, Seq):
                return Left.new(Error.new(this=input.ast, 
                                    message=f"Expect Seq got {input.ast}",
                                    state=input))
            if input.pruned:
                result = []
                for step, keep in normaize_steps:
                    step_result = yield from step.run(input, cache)
                    match step_result:
                        case Left(error) as ERROR:
                            return ERROR
                        case Right((value, next_input)):
                            input = next_input
                            result.append((value, keep))
                return Right.new((Seq(value=tuple(result), custom_mapping=None), input))
            else:
                result = []
                ast_seq = cast(Seq, input.ast)
                if len(ast_seq.value) != len(normaize_steps):
                    return Left.new(Error.new(this=input.ast, 
                                        message=f"Expect Seq of length {len(normaize_steps)} got {len(ast_seq.value)}",
                                        state=input))
                inp = input
                for (step, keep), (ast_elem, _) in zip(normaize_steps, ast_seq.value):
                    if input.restore_pruned or keep:
                        step_result = yield from step.run(inp.inject(ast_elem), cache)
                    else:
                        step_result = yield from step.run(inp.inject(None), cache)
                    match step_result:
                        case Left() as ERROR:
                            return ERROR
                        case Right((value, next_input)):
                            inp = next_input
                            result.append((value, keep))    
                return Right.new((Seq(value=tuple(result), custom_mapping=None), inp))
        return cls(run_f=seq_run) # type: ignore
    


    def flat_map(self, f: Callable[[ParseResult[T]], Algebra[B, GenState[T]]]) -> Algebra[B, GenState[T]]: 

        def flat_map_run(input: GenState[T], 
                         cache:Cache[GenState[T]]) -> PyGenerator[YieldChannelType, 
                                                                GenState[T], 
                                                                Either[Any, Tuple[B, GenState[T]]]]:
            if not input.pruned and (not isinstance(input.ast, Then) or input.ast is Nothing):
                return Left.new(Error.new(this=self, 
                                    message=f"Expect Then got {input.ast}",
                                    state=input))
            lft = input.left() 
            self_result = yield from self.run(lft, cache=cache)
            match self_result:
                case Left() as ERROR:
                    return ERROR
                case Right((value, next_input)):
                    r = input.right() 
                    other_result = yield from f(value).run(r, cache)
                    match other_result:
                        case Left() as ERROR:
                            return ERROR
                        case Right((result, next_input)):
                            return Right.new((result, next_input))
            raise SyncraftError("flat_map should always return a value or an error.", offender=self_result, expect=(Left, Right))
        return replace(self, run_f=flat_map_run) # type: ignore
        


    def many(self, *, at_least: int, at_most: Optional[int]) -> Algebra[Many[ParseResult[T]], GenState[T]]:
        """Apply ``self`` repeatedly with cardinality constraints.

        In pruned mode, generates a random number of items in the inclusive
        range ``[at_least, at_most or at_least+2]`` and attempts each
        independently. Otherwise, validates an existing ``Many`` node and
        applies ``self`` to each element.

        Args:
            at_least: Minimum number of successful applications required.
            at_most: Optional maximum number allowed.

        Returns:
            Algebra[Many[ParseResult[T]], GenState[T]]: An algebra that yields a
            ``Many`` of results.

        Raises:
            ValueError: If bounds are invalid.
        """
        assert at_least >= 0, "at_least must be non-negative"
        assert at_most is None or at_least <= at_most, "at_least must <= at_most"
        def many_run(input: GenState[T], 
                     cache:Cache[GenState[T]]) -> PyGenerator[YieldChannelType, 
                                                            GenState[T], 
                                                            Either[Any, Tuple[Many[ParseResult[T]], GenState[T]]]]:
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
                return Right.new((Many(value=tuple(ret), custom_mapping=None), input))
            else:
                if not isinstance(input.ast, Many) or input.ast is Nothing:
                    return Left.new(Error.new(this=self, 
                                      message=f"Expect Many got {input.ast}",
                                      state=input))
                ret = []
                for x in input.ast.value:
                    self_result = yield from self.run(input.inject(x), cache) 
                    match self_result:
                        case Right((value, _)):
                            if value is not Nothing:
                                ret.append(value)
                            if at_most is not None and len(ret) > at_most:
                                return Left.new(Error.new(
                                        message=f"Expected at most {at_most} matches, got {len(ret)}",
                                        this=self,
                                        state=input.inject(x)
                                    ))                             
                        case Left(_):
                            pass
                if len(ret) < at_least:
                    return Left.new(Error.new(
                        message=f"Expected at least {at_least} matches, got {len(ret)}",
                        this=self,
                        state=input.inject(x)
                    )) 
                return Right.new((Many(value=tuple(ret), custom_mapping=None), input))
        return replace(self, run_f=many_run)  # type: ignore
    
 
    @classmethod
    def choice(cls, *options: Algebra[Any, GenState[T]]) -> Algebra[Choice[Any], GenState[T]]:
        assert options, "At least one option is required for choice"
        def choice_run(input: GenState[T], cache: Cache[GenState[T]]) -> PyGenerator[YieldChannelType, 
                                                                                     GenState[T], 
                                                                                     Either[Any, Tuple[Choice[Any], GenState[T]]]]:
            if input.pruned:
                forked_input = input.fork(tag="choice")
                idx = forked_input.rng("choice_index").randint(0, len(options) - 1)
                selected = options[idx]
                result = yield from selected.run(forked_input, cache)
                match result:
                    case Right((value, next_input)):
                        return Right.new((Choice(index=idx, value=value, custom_mapping=None), next_input))
                    case Left() as ERROR:
                        return ERROR
            else:
                if not isinstance(input.ast, Choice):
                    return Left.new(Error.new(this=input.ast, 
                                      message=f"Expect Choice got {input.ast}",
                                      state=input))
                ast_choice = input.ast
                if ast_choice.index is None:
                    for i, option in enumerate(options):
                        result = yield from option.run(input.inject(ast_choice.value), cache)
                        match result:
                            case Right((value, next_input)):
                                return Right.new((Choice(index=i, value=value, custom_mapping=None), next_input))
                            case Left(err) as ERROR:
                                if isinstance(err, Error) and err.committed:
                                    return ERROR
                    return Left.new(Error.new(this=input.ast, 
                                      message=f"None of the choices matched for {input.ast}",
                                      state=input))
                else:
                    selected = options[ast_choice.index]
                    result = yield from selected.run(input.inject(ast_choice.value), cache)
                    match result:
                        case Right((value, next_input)):
                            return Right.new((Choice(index=ast_choice.index, value=value, custom_mapping=None), next_input))
                        case Left() as ERROR:
                            return ERROR
            raise SyncraftError("choice should always return a value or an error.", offender=result, expect=(Left, Right))
        return cls(run_f=choice_run)  # type: ignore


    def or_else(self, # type: ignore
                other: Algebra[ParseResult[T], GenState[T]]
                ) -> Algebra[OrElse[ParseResult[T], ParseResult[T]], GenState[T]]: 
        def or_else_run(input: GenState[T], 
                        cache:Cache[GenState[T]]) -> PyGenerator[YieldChannelType, 
                                                                GenState[T], 
                                                                Either[Any, Tuple[OrElse[ParseResult[T], ParseResult[T]], GenState[T]]]]:
            def exec(kind: OrElseKind | None, 
                     left: GenState[T], 
                     right: GenState[T]) -> PyGenerator[YieldChannelType, 
                                                        GenState[T], 
                                                        Either[Any, Tuple[OrElse[ParseResult[T], ParseResult[T]], GenState[T]]]]:
                match kind:
                    case OrElseKind.LEFT:
                        self_result = yield from self.run(left, cache)
                        match self_result:
                            case Right((value, next_input)):
                                return Right.new((OrElse(kind=OrElseKind.LEFT, value=value, custom_mapping=None), next_input))
                            case Left() as ERROR:
                                return ERROR
                    case OrElseKind.RIGHT:
                        other_result = yield from other.run(right, cache)
                        match other_result:
                            case Right((value, next_input)):
                                return Right.new((OrElse(kind=OrElseKind.RIGHT, value=value, custom_mapping=None), next_input))
                            case Left() as ERROR:
                                return ERROR
                    case None:

                        self_result = yield from self.run(left, cache)
                        match self_result:
                            case Right((value, next_input)):
                                return Right.new((OrElse(kind=OrElseKind.LEFT, value=value, custom_mapping=None), next_input))
                            case Left(error) as ERROR:
                                if isinstance(error, Error) and error.committed:
                                    return ERROR
                                other_result = yield from other.run(right, cache)
                                match other_result:
                                    case Right((value, next_input)):
                                        return Right.new((OrElse(kind=OrElseKind.RIGHT, value=value, custom_mapping=None), next_input))
                                    case Left() as ERROR:
                                        return ERROR
                raise SyncraftError(f"Invalid OrElseKind: {kind}", offender=kind, expect=(OrElseKind.LEFT, OrElseKind.RIGHT, None))

            if input.pruned:
                forked_input = input.fork(tag="or_else")
                which = forked_input.rng("or_else").choice((OrElseKind.LEFT, OrElseKind.RIGHT))
                result = yield from exec(which, forked_input, forked_input)
                return result
            else:
                if not isinstance(input.ast, OrElse):
                    return Left.new(Error.new(this=self, 
                                      message=f"Expect OrElse got {input.ast}",
                                      state=input))
                else:
                    result = yield from exec(input.ast.kind, 
                                input.inject(input.ast.value), 
                                input.inject(input.ast.value))
                    return result
        return replace(self, run_f=or_else_run) # type: ignore


    @classmethod
    def lazy(cls, 
             thunk: Callable[[], Algebra[ParseResult[T], GenState[T]]], 
             flatten:bool=False) -> Algebra[ParseResult[T], GenState[T]]:
        def algebra_lazy_run(input: GenState[T],
                             cache: Cache[GenState[T]]) -> PyGenerator[YieldChannelType,
                                                                        GenState[T],
                                                                        Either[Any, Tuple[ParseResult[T], GenState[T]]]]:
            # Defer acquiring the underlying algebra until invocation time.
            alg = thunk()
            if input.pruned:
                result = (yield from alg.run(input, cache))
                match result:
                    case Left() as ERROR:
                        return ERROR
                    case Right((value, state)):
                        return Right.new((Lazy(value=value, flatten=flatten, custom_mapping=None), state))
                    case _:
                        raise SyncraftError(f"Unexpected result type from lazy algebra {alg}", offender=result)
            else:
                current = input.ast
                if not isinstance(current, Lazy) or current is Nothing:
                    return Left.new(Error.new(this=alg, 
                                      message=f"Expect Lazy got {current}",
                                      state=input))
                result = (yield from alg.run(input.inject(current.value), cache))
                match result:
                    case Left() as ERROR:
                        return ERROR
                    case Right((value, state)):
                        return Right.new((Lazy(value=value, flatten=flatten, custom_mapping=None), state))
                    case _:
                        raise SyncraftError(f"Unexpected result type from lazy algebra {alg}", offender=result) 
        return cls(algebra_lazy_run)
    

        
    @classmethod
    def lex(cls, args: Builder | TokenSpec, terminal_cls: Callable[..., Any] | None = None, **kwargs) -> Algebra[ParseResult[T], GenState[T]]:
        terminal_cls = terminal_cls or cls.default_terminal_cls
        lexer:LexerProtocol[Any] | None
        lexer, remaining_kwargs = LexerBase.from_kwargs(args, **kwargs)
        assert lexer, f"Lexer could not be created with the given parameters, {args}, {kwargs}"
        ntags = lexer.tags()
        name = ','.join(str(tag) for tag in ntags)
        def lex_run(input: GenState[T], 
                    cache: Cache[GenState[T]]) -> PyGenerator[
                              YieldChannelType, 
                              GenState[T], 
                              Either[Any, Tuple[ParseResult[T], GenState[T]]]]:
            lexer.reset()
            yield from ()
            if input.pruned:
                tag = input.rng("lex_tag").choice(tuple(ntags))
                input = input.fork(tag=tag)
                generated = lexer.gen(tag, input.rng())
                generated = terminal_cls(text=generated, token_type=tag, custom_mapping=None)

                return Right.new((cast(ParseResult[T], generated), input))
            else:
                current = input.ast
                if not lexer.varify(ntags, current):
                    return Left.new(
                            Error.new(
                                this=lex_run,
                                message=f"Expected token tag {name}, but got {current}.",
                                state=input,
                            )
                        )
                parsed_value = cast(ParseResult[T], current)
                return Right.new((parsed_value, input))

        return cls(lex_run) 




@dataclass
class Runner(RunnerProtocol[ParseResult[T], GenState[T]]):
    ast : ParseResult[T] | None = None
    seed: int = field(default_factory=lambda: random.randint(0, 2**32 - 1))
    restore_pruned: bool = False

    
    def algebra(self, 
                  syntax: Syntax[ParseResult[T], GenState[T]], 
                  alg_cls: Type[Algebra[ParseResult[T], GenState[T]]]
                  ) -> Algebra[ParseResult[T], GenState[T]]:
        
        return syntax(alg_cls, syntax = syntax)
    
    def resume(self, request: Optional[GenState[T]], cursor: Optional[StreamCursor[Any]]) -> GenState[T]:
        if request is None:
            return GenState.from_ast(ast=self.ast, seed=self.seed, restore_pruned=self.restore_pruned)
        raise SyncraftError("Generator does not support resuming from Incomplete states.", offender=request, expect="Not Incomplete")




def generator(syntax: Syntax[Any, Any]) -> Algebra[Any, Any]:
    runner: Runner[Any] = Runner()
    return runner.algebra(syntax=syntax, alg_cls=Generator)

    
    
def generate_with(
    syntax: Syntax[Any, Any], 
    data: Optional[ParseResult[Any]] = None, 
    seed: Optional[int] = None,
    restore_pruned: bool = False
) -> Tuple[AST, None | FrozenDict[str, Tuple[AST, ...]]]:
    
    runner = Runner(ast=data, 
                    seed=seed if seed is not None else random.randint(0, 2**32 - 1), 
                    restore_pruned=restore_pruned)

    v, s = runner.once(syntax=syntax, alg_cls=Generator, state=None, cursor=None, cache=None)
    if s is not None:
        return v, s.binding.bindings
    else:
        return v, None    


def validate(syntax: Syntax[Any, Any], data: ParseResult[Any]) -> Tuple[AST, None | FrozenDict[str, Tuple[AST, ...]]]:
    
    runner = Runner(ast=data, seed=0, restore_pruned=True)
    
    v, s = runner.once(syntax=syntax, alg_cls=Generator, state=None, cursor=None, cache=None)
    if s is not None:
        return v, s.binding.bindings
    else:
        return v, None    


def generate(syntax, seed: Optional[int] = None) -> Tuple[AST, None | FrozenDict[str, Tuple[AST, ...]]]:
    
    runner = Runner(ast=None, 
                    seed=seed if seed is not None else random.randint(0, 2**32 - 1), 
                    restore_pruned=False)
    
    v, s = runner.once(syntax=syntax, alg_cls=Generator, state=None, cursor=None, cache=None)
    if s is not None:
        return v, s.binding.bindings
    else:
        return v, None
    



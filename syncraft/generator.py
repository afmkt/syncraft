from __future__ import annotations

from typing import (
    Any, TypeVar, Tuple, Optional, Callable, Generic, Hashable,
    List, Generator as PyGenerator, cast, Type
)
from functools import cached_property
from dataclasses import dataclass, replace, field
from syncraft.algebra import (
    Algebra, Error, YieldChannelType, SendChannelType
)
from syncraft.lexer import CacheWithLexer, ExtLexer, LexerProtocol
from syncraft.cache import Cache, Either, Left, Right

from syncraft.ast import (
    ParseResult, AST, Token, TokenClass, 
    Nothing, Lazy,
    Choice, Many, ChoiceKind,
    Then, ThenKind, SyncraftError
)
from syncraft.constraint import FrozenDict
from syncraft.syntax import Syntax, RunnerProtocol, Incomplete, PayloadKind
import random

from syncraft.constraint import Bindable


S = TypeVar('S', bound=Bindable)

T = TypeVar('T', bound=Hashable)

B = TypeVar('B')


@dataclass(frozen=True)
class GenState(Bindable, Generic[T]):
    """Lightweight state passed between generator combinators.

    Holds the current AST focus (or ``None`` when pruned), a flag controlling
    whether traversals are allowed to access pruned branches, and a deterministic
    seed for randomized generation paths.

    Attributes:
        ast: The current AST node or ``None`` if the branch is pruned.
        restore_pruned: When true, allows navigation into branches that would
            normally be considered pruned by the AST structure.
        seed: Integer seed used to derive reproducible random choices.
    """
    ast: Optional[ParseResult[T]] = None
    restore_pruned: bool = False
    seed: int = 0
    def map(self, f: Callable[[Any], Any]) -> GenState[T]:
        """Return a copy with ``ast`` replaced by ``f(ast)``.

        Args:
            f: Mapping function applied to the current ``ast``.

        Returns:
            GenState[T]: A new state with the mapped ``ast``.
        """
        return replace(self, ast=f(self.ast))
    
    def inject(self, a: Any) -> GenState[T]:
        """Return a copy with ``ast`` set to ``a``.

        Shorthand for ``map(lambda _: a)``.

        Args:
            a: The value to place into ``ast``.

        Returns:
            GenState[T]: A new state with ``ast`` equal to ``a``.
        """
        return self.map(lambda _: a)
    
    def fork(self, tag: Any) -> GenState[T]:
        """Create a deterministic fork of the state using ``tag``.

        The new ``seed`` is derived from the current ``seed`` and ``tag`` so
        that repeated forks with the same inputs are reproducible.

        Args:
            tag: Any value used to derive the child seed.

        Returns:
            GenState[T]: A new state with a forked ``seed``.
        """
        return replace(self, seed=hash((self.seed, tag)))

    def rng(self, tag: Any = None) -> random.Random:
        """Get a deterministic RNG for this state.

        If ``tag`` is provided, the RNG seed is derived from ``(seed, tag)``;
        otherwise the state's ``seed`` is used.

        Args:
            tag: Optional label to derive a sub-seed.

        Returns:
            random.Random: A RNG instance seeded deterministically.
        """
        return random.Random(self.seed if tag is None else hash((self.seed, tag)))



    @cached_property
    def pruned(self)->bool:
        """Whether the current branch is pruned (``ast`` is ``None``)."""
        return self.ast is None
    
    def left(self)-> GenState[T]:
        """Focus on the left side of a ``Then`` node or prune.

        When ``restore_pruned`` is true, traversal is allowed even if the
        ``Then`` is marked as coming from the right branch.

        Returns:
            GenState[T]: State focused on the left child or pruned when not
            applicable.
        """
        if self.ast is None:
            return self
        if isinstance(self.ast, Then) and (self.ast.kind != ThenKind.RIGHT or self.restore_pruned):
            return replace(self, ast=self.ast.left)
        return replace(self, ast=None) 

    def right(self) -> GenState[T]:
        """Focus on the right side of a ``Then`` node or prune.

        When ``restore_pruned`` is true, traversal is allowed even if the
        ``Then`` is marked as coming from the left branch.

        Returns:
            GenState[T]: State focused on the right child or pruned when not
            applicable.
        """
        if self.ast is None:
            return self
        if isinstance(self.ast, Then) and (self.ast.kind != ThenKind.LEFT or self.restore_pruned):
            return replace(self, ast=self.ast.right)
        return replace(self, ast=None)
    
    @classmethod
    def from_ast(cls, 
                 *, 
                 ast: Optional[ParseResult[T]], 
                 seed: int = 0, 
                 restore_pruned:bool=False) -> GenState[T]:
        return cls(ast=ast, seed=seed, restore_pruned=restore_pruned)
    




@dataclass(frozen=True)
class Generator(Algebra[ParseResult[T], GenState[T]]):      

    def flat_map(self, f: Callable[[ParseResult[T]], Algebra[B, GenState[T]]]) -> Algebra[B, GenState[T]]: 
        """Sequence a dependent generator using the left child value.

        Expects the input AST to be a ``Then`` node; applies ``self`` to the
        left side, then passes the produced value to ``f`` and applies the
        resulting algebra to the right side.

        Args:
            f: Function mapping the left value to the next algebra.

        Returns:
            Algebra[B, GenState[T]]: An algebra yielding the final result.
        """
        def flat_map_run(input: GenState[T], 
                         cache:Cache[GenState[T], Either[Any, Tuple[Any, GenState[T]]]]) -> PyGenerator[YieldChannelType, 
                                                                                           SendChannelType, 
                                                                                           Either[Any, Tuple[B, GenState[T]]]]:
            if not input.pruned and (not isinstance(input.ast, Then) or isinstance(input.ast, Nothing)):
                return Left(Error(this=self, 
                                    message=f"Expect Then got {input.ast}",
                                    state=input))
            lft = input.left() 
            self_result = yield from self.run(lft, cache=cache)
            match self_result:
                case Left(error):
                    return Left(error)
                case Right((value, next_input)):
                    r = input.right() 
                    other_result = yield from f(value).run(r, cache)
                    match other_result:
                        case Left(e):
                            return Left(e)
                        case Right((result, next_input)):
                            return Right((result, next_input))
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
        if at_least <=0 or (at_most is not None and at_most < at_least):
            raise SyncraftError(f"Invalid arguments for many: at_least={at_least}, at_most={at_most}", offender=(at_least, at_most), expect="at_least>0 and (at_most is None or at_most>=at_least)")
        def many_run(input: GenState[T], 
                     cache:Cache[GenState[T], Either[Any, Tuple[Any, GenState[T]]]]) -> PyGenerator[YieldChannelType, 
                                                                                       SendChannelType, 
                                                                                       Either[Any, Tuple[Many[ParseResult[T]], GenState[T]]]]:
            if input.pruned:
                ret: List[Any] = []
                while True:
                    forked_input = input.fork(tag=len(ret))
                    match (yield from self.run(forked_input, cache)):
                        case Right((value, _)):
                            ret.append(value)
                        case Left(_):
                            pass
                    if len(ret) >= at_least:
                        if (at_most is None or len(ret) < at_most):
                            if not forked_input.rng("many_continue").choice((True, False)):
                                break
                return Right((Many(value=tuple(ret)), input))
            else:
                if not isinstance(input.ast, Many) or isinstance(input.ast, Nothing):
                    return Left(Error(this=self, 
                                      message=f"Expect Many got {input.ast}",
                                      state=input))
                ret = []
                for x in input.ast.value:
                    self_result = yield from self.run(input.inject(x), cache) 
                    match self_result:
                        case Right((value, _)):
                            ret.append(value)
                            if at_most is not None and len(ret) > at_most:
                                return Left(Error(
                                        message=f"Expected at most {at_most} matches, got {len(ret)}",
                                        this=self,
                                        state=input.inject(x)
                                    ))                             
                        case Left(_):
                            pass
                if len(ret) < at_least:
                    return Left(Error(
                        message=f"Expected at least {at_least} matches, got {len(ret)}",
                        this=self,
                        state=input.inject(x)
                    )) 
                return Right((Many(value=tuple(ret)), input))
        return replace(self, run_f=many_run, _name=f"many({self.name})")  # type: ignore
    
 
    def or_else(self, # type: ignore
                other: Algebra[ParseResult[T], GenState[T]]
                ) -> Algebra[Choice[ParseResult[T], ParseResult[T]], GenState[T]]: 
        """Try ``self``; if it fails without commitment, try ``other``.

        In pruned mode, deterministically chooses a branch using a forked RNG.
        With an existing ``Choice`` AST, it executes the indicated branch.

        Args:
            other: Fallback algebra to try when ``self`` is not committed.

        Returns:
            Algebra[Choice[ParseResult[T], ParseResult[T]], GenState[T]]: An
            algebra yielding which branch succeeded and its value.
        """
        def or_else_run(input: GenState[T], 
                        cache:Cache[GenState[T], Either[Any, Tuple[Any, GenState[T]]]]) -> PyGenerator[YieldChannelType, 
                                                                                          SendChannelType, 
                                                                                          Either[Any, Tuple[Choice[ParseResult[T], ParseResult[T]], GenState[T]]]]:
            def exec(kind: ChoiceKind | None, 
                     left: GenState[T], 
                     right: GenState[T]) -> PyGenerator[YieldChannelType, 
                                                        SendChannelType, 
                                                        Either[Any, Tuple[Choice[ParseResult[T], ParseResult[T]], GenState[T]]]]:
                match kind:
                    case ChoiceKind.LEFT:
                        self_result = yield from self.run(left, cache)
                        match self_result:
                            case Right((value, next_input)):
                                return Right((Choice(kind=ChoiceKind.LEFT, value=value), next_input))
                            case Left(error):
                                return Left(error)
                    case ChoiceKind.RIGHT:
                        other_result = yield from other.run(right, cache)
                        match other_result:
                            case Right((value, next_input)):
                                return Right((Choice(kind=ChoiceKind.RIGHT, value=value), next_input))
                            case Left(error):
                                return Left(error)
                    case None:
                        cache_with_lexer: Optional[CacheWithLexer[Any, GenState[T], Either[Any, Tuple[Any, GenState[T]]]]] = None
                        lexer_snapshot = None
                        if isinstance(cache, CacheWithLexer):
                            cache_with_lexer = cache
                            current_lexer = cache.lexer
                            if current_lexer is not None:
                                lexer_snapshot = current_lexer.clone()

                        self_result = yield from self.run(left, cache)
                        match self_result:
                            case Right((value, next_input)):
                                return Right((Choice(kind=ChoiceKind.LEFT, value=value), next_input))
                            case Left(error):
                                if isinstance(error, Error):
                                    if error.committed:
                                        if cache_with_lexer is not None and lexer_snapshot is not None:
                                            cache_with_lexer.lexer = lexer_snapshot
                                        return Left(replace(error, committed=False))
                                if cache_with_lexer is not None and lexer_snapshot is not None:
                                    cache_with_lexer.lexer = lexer_snapshot
                                    lexer_snapshot = None
                                other_result = yield from other.run(right, cache)
                                match other_result:
                                    case Right((value, next_input)):
                                        return Right((Choice(kind=ChoiceKind.RIGHT, value=value), next_input))
                                    case Left(error):
                                        return Left(error)
                raise SyncraftError(f"Invalid ChoiceKind: {kind}", offender=kind, expect=(ChoiceKind.LEFT, ChoiceKind.RIGHT, None))

            if input.pruned:
                forked_input = input.fork(tag="or_else")
                which = forked_input.rng("or_else").choice((ChoiceKind.LEFT, ChoiceKind.RIGHT))
                result = yield from exec(which, forked_input, forked_input)
                return result
            else:
                if not isinstance(input.ast, Choice) or isinstance(input.ast, Nothing):
                    return Left(Error(this=self, 
                                      message=f"Expect Choice got {input.ast}",
                                      state=input))
                else:
                    result = yield from exec(input.ast.kind, 
                                input.inject(input.ast.value), 
                                input.inject(input.ast.value))
                    return result
        return replace(self, run_f=or_else_run, _name=f"({self.name} | {other.name})") # type: ignore


    @classmethod
    def lazy(cls, thunk: Callable[[], Algebra[ParseResult[T], GenState[T]]]) -> Algebra[ParseResult[T], GenState[T]]:
        def algebra_lazy_run(input: GenState[T],
                             cache: Cache[GenState[T], Either[Any, Tuple[ParseResult[T], GenState[T]]]]) -> PyGenerator[YieldChannelType,
                                                                                                                        SendChannelType,
                                                                                                                        Either[Any, Tuple[ParseResult[T], GenState[T]]]]:
            # Defer acquiring the underlying algebra until invocation time.
            alg = thunk()
            if input.pruned:
                result = (yield from alg.run(input, cache))
                match result:
                    case Left(err):
                        return Left(err)
                    case Right((value, state)):
                        return Right((Lazy(value), state))
                    case _:
                        raise SyncraftError(f"Unexpected result type from lazy algebra {alg}", offender=result)
            else:
                current = input.ast
                if not isinstance(current, Lazy) or isinstance(current, Nothing):
                    return Left(Error(this=alg, 
                                      message=f"Expect Lazy got {current}",
                                      state=input))
                result = (yield from alg.run(input.inject(current.value), cache))
                match result:
                    case Left(err):
                        return Left(err)
                    case Right((value, state)):
                        return Right((Lazy(value), state))
                    case _:
                        raise SyncraftError(f"Unexpected result type from lazy algebra {alg}", offender=result) 
        return cls(algebra_lazy_run, _name=lambda: ".lazy(...)")


    @classmethod
    def primitive(cls, 
                  *, 
                  predicate: Optional[Callable[[T], bool]]=None,
                  generator: Optional[Callable[..., T]] = None
                  )-> Algebra[ParseResult[T], GenState[T]]:
        name = generator.__name__ if generator is not None else "." 
        def primitive_run(input: GenState[T], 
                          cache:Cache[GenState[T], Either[Any, Tuple[ParseResult[T], GenState[T]]]]) -> PyGenerator[
                              YieldChannelType, 
                              SendChannelType, 
                              Either[Any, Tuple[ParseResult[T], GenState[T]]]]:
            if input.pruned:
                assert callable(generator), "In pruned mode, a generator function must be provided."
                return (yield from cache.return_value(Right((generator(input.rng()), input)), input, name=generator.__name__))
            else:
                current = input.ast
                assert callable(predicate), "In non-pruned mode, a predicate function must be provided."
                if not isinstance(current, Token) or not predicate(current): # type: ignore
                    return (yield from cache.return_value( 
                        Left(Error(None, 
                                  message=f"Expected a token, but got {current}.", 
                                  state=input)), input, name=predicate.__name__))
                else:
                    return (yield from cache.return_value(Right((current, input)), input, name=predicate.__name__)) # type: ignore
        return cls(primitive_run, _name=name)  # type: ignore
        


    @classmethod
    def token(
        cls,
        *,
        token_class: TokenClass,
        **kwargs: Any,
    ) -> Algebra[ParseResult[T], GenState[T]]:
        if token_class is None:
            raise SyncraftError(
                "TokenClass not configured for Generator",
                offender=cls,
                expect=TokenClass,
            )
        predicate = token_class.predicate(**kwargs)
        base_generator = token_class.generator(**kwargs)
        return cls.primitive(predicate=predicate, generator=base_generator)

        
    @classmethod
    def lex(cls,
            *,
            lexer_class: Type[LexerProtocol],
            **kwargs: Any) -> Algebra[T, GenState[T]]:
        tag = lexer_class.tag(**kwargs)
        def lex_run(input: GenState[T], 
                    cache: Cache[GenState[T], Either[Any, Tuple[ParseResult[T], GenState[T]]]]) -> PyGenerator[
                              YieldChannelType, 
                              SendChannelType, 
                              Either[Any, Tuple[ParseResult[T], GenState[T]]]]:
            if not isinstance(cache, CacheWithLexer):
                raise SyncraftError("Cache must be CacheWithLexer to use lex", offender=cache, expect="CacheWithLexer")
            lexer = cache.lexer
            if not isinstance(lexer, LexerProtocol):
                raise SyncraftError("Lexer not provided in cache.additional_kwargs", offender=cache, expect="lexer in cache.additional_kwargs")
            if input.pruned:
                input = input.fork(tag=tag)
                generated = lexer.gen(tag, input.rng())
                if isinstance(generated, (str, bytes, tuple)):
                    result_value = Token(text=generated, token_type=tag)
                else:
                    result_value = generated
                parsed_value = cast(ParseResult[T], result_value)
                return (yield from cache.return_value(Right((parsed_value, input)), input, name=str(tag)))
            else:
                current = input.ast
                if isinstance(lexer, ExtLexer):
                    is_valid = lexer.varify(tag, current)
                else:
                    is_valid = isinstance(current, Token) and lexer.varify(tag, current)
                if not is_valid:
                    return (yield from cache.return_value(
                        Left(
                            Error(
                                None,
                                message=f"Expected token tag {tag}, but got {current}.",
                                state=input,
                            )
                        ),
                        input,
                        name=str(tag),
                    ))
                parsed_value = cast(ParseResult[T], current)
                return (yield from cache.return_value(Right((parsed_value, input)), input, name=str(tag)))

        return cls(lex_run, _name=str(tag)) # type: ignore




@dataclass
class Runner(RunnerProtocol[ParseResult[T], GenState[T]]):
    ast : ParseResult[T] | None = None
    seed: int = field(default_factory=lambda: random.randint(0, 2**32 - 1))
    restore_pruned: bool = False
    def bootstrap(self, 
                  syntax: Syntax[ParseResult[T], GenState[T]], 
                  alg_cls: Type[Algebra[ParseResult[T], GenState[T]]]
                  ) -> Tuple[Algebra[ParseResult[T], GenState[T]], Cache[GenState[T], Either[Any, Tuple[Any, GenState[T]]]], GenState[T]]:
        
        initial_cache: CacheWithLexer[Any, GenState[T], Either[Any, Tuple[Any, GenState[T]]]] = CacheWithLexer()
        initial_state: GenState[T] = GenState.from_ast(ast=self.ast, seed=self.seed, restore_pruned=self.restore_pruned)
        return syntax(alg_cls), initial_cache, initial_state
    
    def resume(self, request: Incomplete[S]) -> S:
        raise SyncraftError("Generator does not support resuming from Incomplete states.", offender=request, expect="Not Incomplete")

    def payload_kind(self) -> Optional[PayloadKind]: 
        return None



def generate_with(
    syntax: Syntax[Any, Any], 
    data: Optional[ParseResult[Any]] = None, 
    seed: int = 0, 
    restore_pruned: bool = False
) -> Tuple[AST, None | FrozenDict[str, Tuple[AST, ...]]]:
    """
    Generate an AST from the given syntax, optionally constrained by a partial parse result.

    Args:
        syntax: The syntax specification to generate from.
        data: An optional partial parse result (AST) to constrain generation.
        seed: Random seed for reproducibility.
        restore_pruned: Whether to restore pruned branches in the AST.

    Returns:
        A tuple of (AST, variable bindings) if successful, or (None, None) on failure.
    """
    # from syncraft.syntax import run_state
    runner = Runner(ast=data, seed=seed, restore_pruned=restore_pruned)

    v, s = runner(syntax=syntax, alg_cls=Generator)
    if s is not None:
        return v, s.binding.bound()
    else:
        return v, None    


def validate(
    syntax: Syntax[Any, Any], 
    data: ParseResult[Any]
) -> Tuple[AST, None | FrozenDict[str, Tuple[AST, ...]]]:
    """
    Validate a parse result (AST) against the given syntax.

    Args:
        syntax: The syntax specification to validate against.
        data: The parse result (AST) to validate.

    Returns:
        A tuple of (AST, variable bindings) if valid, or (None, None) if invalid.
    """
    runner = Runner(ast=data, seed=0, restore_pruned=True)
    # from syncraft.syntax import run_state
    v, s = runner(syntax=syntax, alg_cls=Generator)
    if s is not None:
        return v, s.binding.bound()
    else:
        return v, None    


def generate(syntax) -> Tuple[AST, None | FrozenDict[str, Tuple[AST, ...]]]:
    """
    Generate a random AST that conforms to the given syntax.

    Args:
        syntax: The syntax specification to generate from.

    Returns:
        A tuple of (AST, variable bindings) if successful, or (None, None) on failure.
    """
    runner = Runner(ast=None, seed=random.randint(0, 2**32 - 1), restore_pruned=False)
    # from syncraft.syntax import run_state
    v, s = runner(syntax=syntax, alg_cls=Generator)
    if s is not None:
        return v, s.binding.bound()
    else:
        return v, None
    



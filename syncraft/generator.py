from __future__ import annotations

from typing import (
    Any, TypeVar, Tuple, Optional,  Callable, Generic, 
    List, Generator as PyGenerator
)
from functools import cached_property
from dataclasses import dataclass, replace
from syncraft.algebra import (
    Algebra, Either, Left, Right, Error, Incomplete
)
from syncraft.cache import Cache

from syncraft.ast import (
    ParseResult, AST, Token, TokenSpec, 
    Nothing, TokenProtocol,
    Choice, Many, ChoiceKind,
    Then, ThenKind, SyncraftError
)
from syncraft.constraint import FrozenDict
from syncraft.syntax import Syntax
from sqlglot import TokenType
import re
import rstr
from functools import lru_cache
import random

from syncraft.constraint import Bindable

T = TypeVar('T', bound=TokenProtocol)  

S = TypeVar('S', bound=Bindable)



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
    
@lru_cache(maxsize=None)
def token_type_from_string(token_type: Optional[TokenType], 
                           text: str, 
                           case_sensitive:bool = False)-> TokenType:
    if not isinstance(token_type, TokenType) or token_type == TokenType.VAR:
        if case_sensitive:
            for t in TokenType:
                if t.value == text:
                    return t
        else:
            text = text.lower()
            for t in TokenType:
                if t.value == text or str(t.value).lower() == text:
                    return t
        return TokenType.VAR
    return token_type


@dataclass(frozen=True)
class TokenGen(TokenSpec):

    def __str__(self) -> str:
        tt = self.token_type.name if self.token_type else ""
        txt = self.text if self.text else ""
        reg = self.regex.pattern if self.regex else ""
        return f"TokenGen({tt}, {txt}, {self.case_sensitive}, {reg})"
        
    
    def __repr__(self) -> str:
        return self.__str__()

    def gen(self) -> Token:
        """Generate a token consistent with this specification.

        Resolution order is: exact text, regex pattern, token type value, and
        finally a generic placeholder literal.

        Returns:
            Token: A token whose ``token_type`` is derived from the generated
            text when necessary.
        """
        text: str
        if self.text is not None:
            text = self.text
        elif self.regex is not None:
            try:
                text = rstr.xeger(self.regex)
            except Exception:
                # If the regex is invalid or generation fails
                text = self.regex.pattern  # fallback to pattern string
        elif self.token_type is not None:
            text = str(self.token_type.value)
        else:
            text = "VALUE"

        return Token(token_type=token_type_from_string(self.token_type, text, case_sensitive=False), text=text)        

    @staticmethod
    def from_string(string: str) -> Token:
        return Token(token_type=token_type_from_string(None, string, case_sensitive=False), text=string)


@dataclass(frozen=True)
class Generator(Algebra[ParseResult[T], GenState[T]]):  
    
    @classmethod
    def state(cls, ast: Optional[ParseResult[T]] = None, seed: int = 0, restore_pruned: bool = False)->GenState[T]: # type: ignore
        """Create an initial ``GenState`` for generation or checking.

        Args:
            ast: Optional root AST to validate/generate against.
            seed: Seed for deterministic random generation.
            restore_pruned: Allow traversing pruned branches.

        Returns:
            GenState[T]: The constructed initial state.
        """
        return GenState.from_ast(ast=ast, seed=seed, restore_pruned=restore_pruned)

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
        def flat_map_run(input: GenState[T], use_cache:bool) -> PyGenerator[Incomplete[GenState[T]], GenState[T], Either[Any, Tuple[B, GenState[T]]]]:
            if not isinstance(input.ast, Then) or isinstance(input.ast, Nothing):
                return Left(Error(this=self, 
                                    message=f"Expect Then got {input.ast}",
                                    state=input))
            lft = input.left() 
            self_result = yield from self.run(lft, use_cache=use_cache)
            match self_result:
                case Left(error):
                    return Left(error)
                case Right((value, next_input)):
                    r = input.right() 
                    other_result = yield from f(value).run(r, use_cache)
                    match other_result:
                        case Left(e):
                            return Left(e)
                        case Right((result, next_input)):
                            return Right((result, next_input))
            raise SyncraftError("flat_map should always return a value or an error.", offending=self_result, expect=(Left, Right))
        return self.__class__(flat_map_run, name=self.name, cache=self.cache) # type: ignore


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
            raise SyncraftError(f"Invalid arguments for many: at_least={at_least}, at_most={at_most}", offending=(at_least, at_most), expect="at_least>0 and (at_most is None or at_most>=at_least)")
        def many_run(input: GenState[T], use_cache:bool) -> PyGenerator[Incomplete[GenState[T]], GenState[T], Either[Any, Tuple[Many[ParseResult[T]], GenState[T]]]]:
            if input.pruned:
                upper = at_most if at_most is not None else at_least + 2
                count = input.rng("many").randint(at_least, upper)
                ret: List[Any] = []
                for i in range(count):
                    forked_input = input.fork(tag=len(ret))
                    self_result = yield from self.run(forked_input, use_cache)
                    match self_result:
                        case Right((value, _)):
                            ret.append(value)
                        case Left(_):
                            pass
                return Right((Many(value=tuple(ret)), input))
            else:
                if not isinstance(input.ast, Many) or isinstance(input.ast, Nothing):
                    return Left(Error(this=self, 
                                      message=f"Expect Many got {input.ast}",
                                      state=input))
                ret = []
                for x in input.ast.value:
                    self_result = yield from self.run(input.inject(x), use_cache) 
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
        return self.__class__(many_run, name=f"many({self.name})", cache=self.cache)  # type: ignore
    
 
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
        def or_else_run(input: GenState[T], use_cache:bool) -> PyGenerator[Incomplete[GenState[T]], GenState[T], Either[Any, Tuple[Choice[ParseResult[T], ParseResult[T]], GenState[T]]]]:
            def exec(kind: ChoiceKind | None, 
                     left: GenState[T], 
                     right: GenState[T]) -> PyGenerator[Incomplete[GenState[T]], GenState[T], Either[Any, Tuple[Choice[ParseResult[T], ParseResult[T]], GenState[T]]]]:
                match kind:
                    case ChoiceKind.LEFT:
                        self_result = yield from self.run(left, use_cache)
                        match self_result:
                            case Right((value, next_input)):
                                return Right((Choice(kind=ChoiceKind.LEFT, value=value), next_input))
                            case Left(error):
                                return Left(error)
                    case ChoiceKind.RIGHT:
                        other_result = yield from other.run(right, use_cache)
                        match other_result:
                            case Right((value, next_input)):
                                return Right((Choice(kind=ChoiceKind.RIGHT, value=value), next_input))
                            case Left(error):
                                return Left(error)
                    case None:
                        self_result = yield from self.run(left, use_cache)
                        match self_result:
                            case Right((value, next_input)):
                                return Right((Choice(kind=ChoiceKind.LEFT, value=value), next_input))
                            case Left(error):
                                if isinstance(error, Error):
                                    if error.fatal:
                                        return Left(error)
                                    elif error.committed:
                                        return Left(replace(error, committed=False))
                                other_result = yield from other.run(right, use_cache)
                                match other_result:
                                    case Right((value, next_input)):
                                        return Right((Choice(kind=ChoiceKind.RIGHT, value=value), next_input))
                                    case Left(error):
                                        return Left(error)
                raise SyncraftError(f"Invalid ChoiceKind: {kind}", offending=kind, expect=(ChoiceKind.LEFT, ChoiceKind.RIGHT, None))

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
                    
        return self.__class__(or_else_run, name=f"or_else({self.name} | {other.name})", cache=self.cache | other.cache) # type: ignore

    @classmethod
    def token(cls, 
              *,
              cache: Cache,
              token_type: Optional[TokenType] = None, 
              text: Optional[str] = None, 
              case_sensitive: bool = False,
              regex: Optional[re.Pattern[str]] = None,
              )-> Algebra[ParseResult[T], GenState[T]]:      
        """Match or synthesize a single token.

        When validating, succeeds if the current AST node is a ``Token`` that
        satisfies this spec. When generating (pruned), produces a token based on
        ``text``, ``regex``, or ``token_type``.

        Args:
            token_type: Expected token type.
            text: Exact text to match or produce.
            case_sensitive: Whether text matching respects case.
            regex: Regular expression to synthesize text from when generating.

        Returns:
            Algebra[ParseResult[T], GenState[T]]: An algebra producing a Token
            node or validating the current one.
        """
        gen = TokenGen(token_type=token_type, text=text, case_sensitive=case_sensitive, regex=regex)  
        lazy_self: Algebra[ParseResult[T], GenState[T]]
        def token_run(input: GenState[T], use_cache:bool) -> PyGenerator[Incomplete[GenState[T]], GenState[T], Either[Any, Tuple[ParseResult[Token], GenState[T]]]]:
            yield from ()
            if input.pruned:
                return Right((gen.gen(), input))
            else:
                current = input.ast
                if not isinstance(current, Token) or not gen.is_valid(current):
                    return Left(Error(None, 
                                      message=f"Expected a Token({gen.text}), but got {current}.", 
                                      state=input))
                return Right((current, input))
        lazy_self = cls(token_run, name=cls.__name__ + f'.token({token_type or text or regex})', cache=cache)  # type: ignore
        return lazy_self



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
    from syncraft.syntax import run
    v, s = run(syntax=syntax, alg=Generator, use_cache=not restore_pruned, ast=data, seed=seed, restore_pruned=restore_pruned)
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
    from syncraft.syntax import run
    v, s = run(syntax=syntax, alg=Generator, use_cache=True, ast=data, seed=0, restore_pruned=True)
    if s is not None:
        return v, s.binding.bound()
    else:
        return v, None    


def generate(
    syntax
) -> Tuple[AST, None | FrozenDict[str, Tuple[AST, ...]]]:
    """
    Generate a random AST that conforms to the given syntax.

    Args:
        syntax: The syntax specification to generate from.

    Returns:
        A tuple of (AST, variable bindings) if successful, or (None, None) on failure.
    """
    from syncraft.syntax import run
    v, s = run(syntax=syntax, alg=Generator, use_cache=False, ast=None, seed=random.randint(0, 2**32 - 1), restore_pruned=False)
    if s is not None:
        return v, s.binding.bound()
    else:
        return v, None
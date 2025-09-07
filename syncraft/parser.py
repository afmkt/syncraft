from __future__ import annotations
import re
from sqlglot import tokenize, TokenType, Parser as GlotParser, exp
from typing import (
    Optional, List, Any, Tuple, TypeVar,
    Generic, Generator
)
from syncraft.cache import Cache
from syncraft.constraint import FrozenDict
from syncraft.algebra import (
    Either, Left, Right, Error, Algebra, Incomplete
)
from dataclasses import dataclass, field, replace
from enum import Enum

from syncraft.syntax import Syntax, token

from syncraft.ast import Token, TokenSpec, AST, TokenProtocol, SyncraftError
from syncraft.constraint import Bindable


T = TypeVar('T', bound=TokenProtocol)


@dataclass(frozen=True)
class ParserState(Bindable, Generic[T]):
    """Immutable state for the SQL token stream during parsing.

    Keeps a tuple of tokens and the current index. The state is passed through
    parser combinators and can be copied or advanced safely.

    Attributes:
        input: The full, immutable sequence of tokens.
        index: Current position within ``input``.
    """
    input: Tuple[T, ...] = field(default_factory=tuple)
    index: int = 0
    final: bool = False  # Whether this is a final state (for error reporting)

    def __repr__(self) -> str:
        return (f"ParserState("
                f"input=[{self.before() + (' ' if len(self.before())>0 else '')}\u25cf{(' ' if len(self.after()) > 0 else '') + self.after()}], "
                f"ended={self.ended()}, "
                f"pending={self.pending()})")

    def __str__(self) -> str:
        return self.__repr__()
    
    def __add__(self, other: 'ParserState[T]') -> 'ParserState[T]':
        if not isinstance(other, ParserState):
            raise SyncraftError("Can only concatenate ParserState with another ParserState", offending=self, expect="ParserState")
        if self.final:
            raise SyncraftError("Cannot concatenate to a final ParserState", offending=self, expect="not final")
        return replace(self, input=self.input + other.input, final=other.final)

    def token_sample_string(self)-> str:
        def encode_tokens(*tokens:T) -> str:
            return ",".join(f"{token.token_type.name}({token.text})" for token in tokens)
        return encode_tokens(*self.input[self.index:self.index + 2])

    def before(self, length: Optional[int] = 3)->str:
        """Return a string with up to ``length`` tokens before the cursor.

        Args:
            length: Maximum number of tokens to include.

        Returns:
            str: Space-separated token texts before the current index.
        """
        length = min(self.index, length) if length is not None else self.index
        return " ".join(token.text for token in self.input[self.index - length:self.index])
    
    def after(self, length: Optional[int] = 3)->str:
        """Return a string with up to ``length`` tokens from the cursor on.

        Args:
            length: Maximum number of tokens to include.

        Returns:
            str: Space-separated token texts starting at the current index.
        """
        length = min(length, len(self.input) - self.index) if length is not None else len(self.input) - self.index
        ret = " ".join(token.text for token in self.input[self.index:self.index + length])
        return ret


    def current(self)->T:
        """Get the current token at ``index``.

        Returns:
            T: The token at the current index.

        Raises:
            IndexError: If attempting to read past the end of the stream.
        """
        if self.index >= len(self.input):
            raise SyncraftError("Attempted to access token beyond end of stream", offending=self, expect="index < len(input)")
        return self.input[self.index]
    

    def pending(self) -> bool:
        return self.index >= len(self.input) and not self.final

    def ended(self) -> bool:
        """Whether the cursor is at or past the end of the token stream."""
        return self.index >= len(self.input) and self.final

    def advance(self) -> ParserState[T]:
        """Return a new state advanced by one token (bounded at end)."""
        return replace(self, index=min(self.index + 1, len(self.input)))
            
    
    @classmethod
    def from_tokens(cls, tokens: Tuple[T, ...]) -> ParserState[T]:
        return cls(input=tokens, index=0, final=True)




    
@dataclass(frozen=True)
class Parser(Algebra[T, ParserState[T]]):
    @classmethod
    def state(cls, sql: str, dialect: str) -> ParserState[T]: # type: ignore
        """Tokenize SQL text into an initial ``ParserState``.

        Uses ``sqlglot.tokenize`` for the given dialect and wraps tokens into
        the project's ``Token`` type.

        Args:
            sql: The SQL text to tokenize.
            dialect: The sqlglot dialect name (e.g. "sqlite", "duckdb").

        Returns:
            ParserState[T]: Initial parser state at index 0.
        """
        tokens = tuple([Token(token_type=token.token_type, text=token.text) for token in tokenize(sql, dialect=dialect)])
        return ParserState.from_tokens(tokens)  # type: ignore

    @classmethod
    def token(cls, 
              *,
              cache: Cache,
              token_type: Optional[Enum] = None, 
              text: Optional[str] = None, 
              case_sensitive: bool = False,
              regex: Optional[re.Pattern[str]] = None
              )-> Algebra[T, ParserState[T]]:
        """Match a single token according to a specification.

        Succeeds when the current token satisfies the provided
        ``TokenSpec`` (by type, exact text, or regex). On failure,
        an informative ``Error`` is produced with location context.

        Args:
            token_type: Expected enum type of the token.
            text: Exact token text to match.
            case_sensitive: Whether text matching is case sensitive.
            regex: Regular expression pattern to match token text.

        Returns:
            Algebra[T, ParserState[T]]: An algebra yielding the matched token.
        """
        spec = TokenSpec(token_type=token_type, text=text, case_sensitive=case_sensitive, regex=regex)
        def token_run(state: ParserState[T], use_cache:bool) -> Generator[Incomplete[ParserState[T]],ParserState[T], Either[Any, Tuple[T, ParserState[T]]]]:
            while True:
                if state.ended():
                    return Left(state)
                elif state.pending():
                    state = yield Incomplete(state)
                else:
                    token = state.current()
                    if token is None or not spec.is_valid(token):
                        return Left(state)
                    else:
                        return Right((Token(token_type = token.token_type, text=token.text), state.advance()))  # type: ignore
        captured: Algebra[T, ParserState[T]] = cls(token_run, name=cls.__name__ + f'.token({token_type}, {text})', cache=cache)
        def error_fn(err: Any) -> Error:
            if isinstance(err, ParserState):
                return Error(message=f"Cannot match token at {err}", this=captured, state=err)            
            else:
                return Error(message="Cannot match token at unknown state", this=captured)
        # assign the updated parser(with description) to bound variable so the Error.this could be set correctly
        captured = captured.map_error(error_fn)
        return captured        




def sqlglot(parser: Syntax[Any, Any], 
            dialect: str) -> Syntax[List[exp.Expression], ParserState[Any]]:
    """Map token tuples into sqlglot expressions for a given dialect.

    Wraps a ``Syntax`` so its result is parsed by ``sqlglot.Parser``
    using ``raw_tokens`` and returns only non-``None`` expressions.

    Args:
        parser: A syntax that produces a sequence of tokens.
        dialect: sqlglot dialect name used to parse tokens.

    Returns:
        Syntax[List[exp.Expression], ParserState[Any]]: Syntax yielding a list
        of parsed expressions.
    """
    gp = GlotParser(dialect=dialect)
    return parser.map(lambda tokens: [e for e in gp.parse(raw_tokens=tokens) if e is not None])


    
def identifier(value: str | None = None) -> Syntax[Any, Any]:
    """Match an identifier token, optionally with exact text.

    Args:
        value: Exact identifier text to match, or ``None`` for any identifier.

    Returns:
        Syntax[Any, Any]: A syntax matching one identifier token.
    """
    if value is None:
        return token(token_type=TokenType.IDENTIFIER)
    else:
        return token(token_type=TokenType.IDENTIFIER, text=value)

def variable(value: str | None = None) -> Syntax[Any, Any]:
    """Match a variable token, optionally with exact text.

    Args:
        value: Exact variable text to match, or ``None`` for any variable.

    Returns:
        Syntax[Any, Any]: A syntax matching one variable token.
    """
    if value is None:
        return token(token_type=TokenType.VAR)
    else:
        return token(token_type=TokenType.VAR, text=value)


def number() -> Syntax[Any, Any]:
    """Match a number token."""
    return token(token_type=TokenType.NUMBER)


def string() -> Syntax[Any, Any]:
    """Match a string literal token."""
    return token(token_type=TokenType.STRING)






def parse(syntax: Syntax[Any, Any], sql: str, dialect: str) -> Tuple[Any, None | FrozenDict[str, Tuple[AST, ...]]]:
    """Parse SQL text with a ``Syntax`` using the ``Parser`` backend.

    Tokenizes the SQL with the specified dialect and executes ``syntax``.

    Args:
        syntax: The high-level syntax to run.
        sql: SQL text to tokenize and parse.
        dialect: sqlglot dialect name used for tokenization.

    Returns:
        Tuple[AST, FrozenDict[str, Tuple[AST, ...]]] | Tuple[Any, None]:
        The produced AST and collected marks, or a tuple signaling failure.
    """
    from syncraft.syntax import run
    v, s = run(syntax=syntax, alg=Parser, use_cache=True, sql=sql, dialect=dialect)
    if s is not None:
        return v, s.binding.bound()
    else:
        return v, None
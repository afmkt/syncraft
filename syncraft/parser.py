from __future__ import annotations
import re
from sqlglot import tokenize, TokenType, Parser as GlotParser, exp
from typing import (
    Optional, List, Any, Tuple, TypeVar,
    Generic
)
from syncraft.constraint import FrozenDict
from syncraft.algebra import (
    Either, Left, Right, Error, Algebra
)
from dataclasses import dataclass, field, replace
from enum import Enum
from functools import reduce
from syncraft.syntax import Syntax

from syncraft.ast import Token, TokenSpec, AST, TokenProtocol
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

    
    def token_sample_string(self)-> str:
        def encode_tokens(*tokens:T) -> str:
            return ",".join(f"{token.token_type.name}({token.text})" for token in tokens)
        return encode_tokens(*self.input[self.index:self.index + 2])

    def before(self, length: Optional[int] = 5)->str:
        """Return a string with up to ``length`` tokens before the cursor.

        Args:
            length: Maximum number of tokens to include.

        Returns:
            str: Space-separated token texts before the current index.
        """
        length = min(self.index, length) if length is not None else self.index
        return " ".join(token.text for token in self.input[self.index - length:self.index])
    
    def after(self, length: Optional[int] = 5)->str:
        """Return a string with up to ``length`` tokens from the cursor on.

        Args:
            length: Maximum number of tokens to include.

        Returns:
            str: Space-separated token texts starting at the current index.
        """
        length = min(length, len(self.input) - self.index) if length is not None else len(self.input) - self.index
        return " ".join(token.text for token in self.input[self.index:self.index + length])


    def current(self)->T:
        """Get the current token at ``index``.

        Returns:
            T: The token at the current index.

        Raises:
            IndexError: If attempting to read past the end of the stream.
        """
        if self.ended():
            raise IndexError("Attempted to access token beyond end of stream")
        return self.input[self.index]
    
    def ended(self) -> bool:
        """Whether the cursor is at or past the end of the token stream."""
        return self.index >= len(self.input)

    def advance(self) -> ParserState[T]:
        """Return a new state advanced by one token (bounded at end)."""
        return replace(self, index=min(self.index + 1, len(self.input)))
            
    def delta(self, new_state: ParserState[T]) -> Tuple[T, ...]:
        assert self.input is new_state.input, "Cannot calculate differences between different input streams"
        assert 0 <= self.index <= new_state.index <= len(self.input), "Segment indices out of bounds"
        return self.input[self.index:new_state.index]
    
    def copy(self) -> ParserState[T]:
        return self.__class__(input=self.input, index=self.index)

    @classmethod
    def from_tokens(cls, tokens: Tuple[T, ...]) -> ParserState[T]:
        return cls(input=tokens, index=0)




    
@dataclass(frozen=True)
class Parser(Algebra[T, ParserState[T]]):
    @classmethod
    def state(cls, sql: str, dialect: str) -> ParserState[T]:
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
        def token_run(state: ParserState[T], use_cache:bool) -> Either[Any, Tuple[T, ParserState[T]]]:
            if state.ended():
                return Left(state)
            token = state.current()
            if token is None or not spec.is_valid(token):
                return Left(state)
            return Right((Token(token_type = token.token_type, text=token.text), state.advance()))  # type: ignore
        captured: Algebra[T, ParserState[T]] = cls(token_run, name=cls.__name__ + f'.token({token_type}, {text})')
        def error_fn(err: Any) -> Error:
            if isinstance(err, ParserState):
                return Error(message=f"Cannot match token at {err}", this=captured, state=err)            
            else:
                return Error(message="Cannot match token at unknown state", this=captured)
        # assign the updated parser(with description) to bound variable so the Error.this could be set correctly
        captured = captured.map_error(error_fn)
        return captured        


    @classmethod
    def until(cls, 
              *open_close: Tuple[Algebra[Any, ParserState[T]], Algebra[Any, ParserState[T]]],
              terminator: Optional[Algebra[Any, ParserState[T]]] = None,
              inclusive: bool = True, 
              strict: bool = True) -> Algebra[Any, ParserState[T]]:
        """Consume tokens until a terminator while respecting nested pairs.

        Tracks nesting of one or more opener/closer parser pairs. When not
        nested, an optional ``terminator`` may end the scan. If ``inclusive``
        is true, boundary tokens (openers/closers/terminator) are included in
        the returned tuple. If ``strict`` is true, the next token must match an
        opener before scanning continues; otherwise content may start
        immediately.

        Args:
            open_close: One or more pairs of (open, close) parsers.
            terminator: Optional parser that ends scanning at top level.
            inclusive: Include matched structural tokens in the result.
            strict: Require the very next token to be an opener when provided.

        Returns:
            Algebra[Any, ParserState[T]]: An algebra yielding a tuple of
            collected tokens upon success.
        """
        def until_run(state: ParserState[T], use_cache:bool) -> Either[Any, Tuple[Any, ParserState[T]]]:
            # Use a stack to enforce proper nesting across multiple open/close pairs.
            tokens: List[Any] = []
            if not terminator and len(open_close) == 0:
                return Left(Error(this=until_run, message="No terminator and no open/close parsers, nothing to parse", state=state))

            # Helper to try matching any of the parsers once, returning early on first match
            def try_match(s: ParserState[T], *parsers: Algebra[Any, ParserState[T]]) -> Tuple[bool, Optional[int], Optional[Any], ParserState[T]]:
                for i, p in enumerate(parsers):
                    res = p.run(s, use_cache)
                    if isinstance(res, Right):
                        val, ns = res.value
                        return True, i, val, ns
                return False, None, None, s

            opens, closes = zip(*open_close) if len(open_close) > 0 else ((), ())
            tmp_state: ParserState[T] = state.copy()
            stack: List[int] = []  # indices into open_close indicating expected closer

            # If strict, require the very next token to be an opener of any kind
            if strict and len(opens) > 0:
                c = reduce(lambda a, b: a.or_else(b), opens).run(tmp_state, use_cache)
                if c.is_left():
                    return Left(Error(this=until_run, message="No opening parser matched", state=tmp_state))

            while not tmp_state.ended():
                # Try to open
                o_matched, o_idx, o_tok, o_state = try_match(tmp_state, *opens)
                if o_matched and o_idx is not None:
                    stack.append(o_idx)
                    if inclusive:
                        tokens.append(o_tok)
                    tmp_state = o_state
                    continue

                # Try to close
                c_matched, c_idx, c_tok, c_state = try_match(tmp_state, *closes)
                if c_matched and c_idx is not None:
                    if not stack or stack[-1] != c_idx:
                        return Left(Error(this=until_run, message="Mismatched closing parser", state=tmp_state))
                    stack.pop()
                    if inclusive:
                        tokens.append(c_tok)
                    tmp_state = c_state
                    # After closing, if stack empty, we may terminate on a terminator
                    if len(stack) == 0:
                        if terminator:
                            term = terminator.run(tmp_state, use_cache)
                            if isinstance(term, Right):
                                if inclusive:
                                    tokens.append(term.value[0])
                                return Right((tuple(tokens), term.value[1]))
                        else:
                            return Right((tuple(tokens), tmp_state))
                    continue

                # If nothing structural matched, check termination when not nested
                if len(stack) == 0:
                    if terminator:
                        term2 = terminator.run(tmp_state, use_cache)
                        if isinstance(term2, Right):
                            if inclusive:
                                tokens.append(term2.value[0])
                            return Right((tuple(tokens), term2.value[1]))
                    else:
                        return Right((tuple(tokens), tmp_state))

                # Otherwise, consume one token as payload and continue
                tokens.append(tmp_state.current())
                tmp_state = tmp_state.advance()

            # Reached end of input
            if len(stack) != 0:
                return Left(Error(this=until_run, message="Unterminated group", state=tmp_state))
            return Right((tuple(tokens), tmp_state))
        return cls(until_run, name=cls.__name__ + '.until')

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


def parse(syntax: Syntax[Any, Any], sql: str, dialect: str) -> Tuple[AST, FrozenDict[str, Tuple[AST, ...]]] | Tuple[Any, None]:
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
    return run(syntax, Parser, True, sql=sql, dialect=dialect)




def token(token_type: Optional[Enum] = None, 
          text: Optional[str] = None, 
          case_sensitive: bool = False,
          regex: Optional[re.Pattern[str]] = None
          ) -> Syntax[Any, Any]:
    """Build a ``Syntax`` that matches a single token.

    Convenience wrapper around ``Parser.token``. You can match by
    type, exact text, or regex.

    Args:
        token_type: Expected token enum type.
        text: Exact token text to match.
        case_sensitive: Whether text matching respects case.
        regex: Pattern to match token text.

    Returns:
        Syntax[Any, Any]: A syntax that matches one token.
    """
    token_type_txt = token_type.name if token_type is not None else None
    token_value_txt = text if text is not None else None
    msg = 'token(' + ','.join([x for x in [token_type_txt, token_value_txt, str(regex)] if x is not None]) + ')'
    return Syntax(
        lambda cls: cls.factory('token', token_type=token_type, text=text, case_sensitive=case_sensitive, regex=regex)
        ).describe(name=msg, fixity='prefix') 

    
def identifier(value: str | None = None) -> Syntax[Any, Any]:
    """Match an identifier token, optionally with exact text.

    Args:
        value: Exact identifier text to match, or ``None`` for any identifier.

    Returns:
        Syntax[Any, Any]: A syntax matching one identifier token.
    """
    if value is None:
        return token(TokenType.IDENTIFIER)
    else:
        return token(TokenType.IDENTIFIER, text=value)

def variable(value: str | None = None) -> Syntax[Any, Any]:
    """Match a variable token, optionally with exact text.

    Args:
        value: Exact variable text to match, or ``None`` for any variable.

    Returns:
        Syntax[Any, Any]: A syntax matching one variable token.
    """
    if value is None:
        return token(TokenType.VAR)
    else:
        return token(TokenType.VAR, text=value)

def literal(lit: str) -> Syntax[Any, Any]:
    """Match an exact literal string (case-sensitive)."""
    return token(token_type=None, text=lit, case_sensitive=True)

def regex(regex: re.Pattern[str]) -> Syntax[Any, Any]:
    """Match a token whose text satisfies the given regular expression."""
    return token(token_type=None, regex=regex, case_sensitive=True)

def lift(value: Any)-> Syntax[Any, Any]:
    """Lift a Python value into the nearest matching token syntax.

    - ``str`` -> ``literal``
    - ``re.Pattern`` -> ``token`` with regex
    - ``Enum`` -> ``token`` with type
    - otherwise -> succeed with the value
    """
    if isinstance(value, str):
        return literal(value)
    elif isinstance(value, re.Pattern):
        return token(regex=value)
    elif isinstance(value, Enum):
        return token(value)
    else:
        return Syntax(lambda cls: cls.success(value))

def number() -> Syntax[Any, Any]:
    """Match a number token."""
    return token(TokenType.NUMBER)


def string() -> Syntax[Any, Any]:
    """Match a string literal token."""
    return token(TokenType.STRING)



def until(*open_close: Tuple[Syntax[Tuple[T, ...] | T, ParserState[T]], Syntax[Tuple[T, ...] | T, ParserState[T]]],
          terminator: Optional[Syntax[Tuple[T, ...] | T, ParserState[T]]] = None,
          inclusive: bool = True, 
          strict: bool = True) -> Syntax[Any, Any]:
    """Syntax wrapper to scan until a terminator while handling nesting.

    Equivalent to ``Parser.until`` but at the ``Syntax`` layer, converting the
    provided syntaxes into parser algebras under the hood.

    Args:
        open_close: One or more pairs of (open, close) syntaxes.
        terminator: Optional syntax that ends scanning at top level.
        inclusive: Include matched boundary tokens in the result.
        strict: Require the very next token to be an opener when provided.

    Returns:
        Syntax[Any, Any]: A syntax yielding a tuple of collected tokens.
    """
    return Syntax(
        lambda cls: cls.factory('until', 
                           *[(left.alg(cls), right.alg(cls)) for left, right in open_close], 
                           terminator=terminator.alg(cls) if terminator else None, 
                           inclusive=inclusive, 
                           strict=strict)
        ).describe(name="until", fixity='prefix') 


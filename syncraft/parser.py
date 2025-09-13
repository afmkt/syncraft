from __future__ import annotations
import re

from typing import (
    Optional, List, Any, Tuple, TypeVar,Hashable,
    Generic, Generator, Callable
)
from syncraft.cache import Cache
from syncraft.constraint import FrozenDict
from syncraft.algebra import (
    Either, Left, Right, Error, Algebra, Incomplete
)
from dataclasses import dataclass, field, replace
from enum import Enum

from syncraft.syntax import Syntax

from syncraft.ast import Token, TokenClass, AST, SyncraftError
from syncraft.constraint import Bindable


T = TypeVar('T', bound=Hashable)  


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



    def before(self, length: Optional[int] = 3)->str:
        """Return a string with up to ``length`` tokens before the cursor.

        Args:
            length: Maximum number of tokens to include.

        Returns:
            str: Space-separated token texts before the current index.
        """
        length = min(self.index, length) if length is not None else self.index
        return " ".join(str(token) for token in self.input[self.index - length:self.index])
    
    def after(self, length: Optional[int] = 3)->str:
        """Return a string with up to ``length`` tokens from the cursor on.

        Args:
            length: Maximum number of tokens to include.

        Returns:
            str: Space-separated token texts starting at the current index.
        """
        length = min(length, len(self.input) - self.index) if length is not None else len(self.input) - self.index
        ret = " ".join(str(token) for token in self.input[self.index:self.index + length])
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
    def state(cls, tokens: List[T]) -> ParserState[T]: # type: ignore
        return ParserState.from_tokens(tuple(tokens))  

    @classmethod
    def primitive(cls, 
                  *, 
                  predicate: Optional[Callable[[T], bool]]=None,
                  generator: Optional[Callable[..., T]] = None
                  )-> Algebra[T, ParserState[T]]:
        def primitive_run(state: ParserState[T], 
                          cache:Cache[Either[Any, Tuple[Any, ParserState[T]]]]) -> Generator[
                              Incomplete[ParserState[T]], 
                              ParserState[T], 
                              Either[Any, Tuple[T, ParserState[T]]]]:
            while True:
                if state.ended():
                    return (yield from cache.return_value(Left(state)))
                elif state.pending():
                    state = yield Incomplete(state)
                else:
                    token = state.current()
                    assert callable(predicate), "Predicate must be callable"
                    if token is None or not predicate(token):
                        return (yield from cache.return_value(Left(state)))
                    else:
                        return (yield from cache.return_value(Right((token, state.advance()))))
        name = cls.__name__ + f'.primitive({predicate.__name__})' if predicate is not None else cls.__name__ + '.primitive(None)'
        captured: Algebra[T, ParserState[T]] = cls(primitive_run, _name=name)
        def error_fn(err: Any) -> Error:
            if isinstance(err, ParserState):
                return Error(message=f"Cannot match token at {err}", this=captured, state=err)            
            else:
                return Error(message="Cannot match token at unknown state", this=captured)
        # assign the updated parser(with description) to bound variable so the Error.this could be set correctly
        captured = captured.map_error(error_fn)
        return captured        

    @classmethod
    def token(cls, 
              *,
              text: Optional[str | re.Pattern[str]] = None, 
              token_type: Optional[Enum] = None,           
              case_sensitive: bool = False
              ) -> Algebra[T, ParserState[T]]:
        token_class: TokenClass = cls.config(TokenClass, TokenClass.simple())
        pred = token_class.predicate(token_type=token_type, 
                         text=text, 
                         case_sensitive=case_sensitive)
        return cls.primitive(predicate=pred)  




# def sqlglot(parser: Syntax[Any, Any], dialect: str) -> Syntax[List[Any], ParserState[Any]]:
#     """Map token tuples into sqlglot expressions for a given dialect via adapter.

#     If sqlglot isn't available, this fails early with a clear error.
#     """
#     if not SQLGLOT_AVAILABLE:
#         raise RuntimeError("sqlglot() requested but sqlglot is not installed. Install with: pip install sqlglot")
#     return parser.map(lambda tokens: sqlglot_parse_expressions(tokens, dialect))



def token(*,
          text: Optional[str | re.Pattern[str]] = None, 
          token_type: Optional[Enum] = None,           
          case_sensitive: bool = False) -> Syntax[Any, Any]:
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
    return Syntax(
        lambda cls: cls.factory('token', 
                                token_type=token_type, 
                                text=text, 
                                case_sensitive=case_sensitive)
        ).describe(name=f'token({str(text)})', fixity='prefix')

    

def literal(lit: str | re.Pattern[str]) -> Syntax[Any, Any]:
    """Match an exact literal string (case-sensitive)."""
    return token(token_type=None, 
                 text=lit, 
                 case_sensitive=True)


def lift(value: Any)-> Syntax[Any, Any]:
    """Lift a Python value into the nearest matching token syntax.

    - ``str`` -> ``literal``
    - ``re.Pattern`` -> ``token`` with regex
    - ``Enum`` -> ``token`` with type
    - otherwise -> succeed with the value
    """
    if isinstance(value, (str, re.Pattern)):
        return literal(value)
    elif isinstance(value, Enum):
        return token(token_type=value)
    else:
        return Syntax(lambda cls: cls.success(value))


def parse_sql(syntax: Syntax[Any, Any], sql: str, dialect: str, *, adapter_lex=sqlglot_lex) -> Tuple[Any, None | FrozenDict[str, Tuple[AST, ...]]]:
    tokens = adapter_lex(sql, dialect)
    return parse(syntax, tokens)

    
def parse(syntax: Syntax[Any, Any], tokens: List[Token]) -> Tuple[Any, None | FrozenDict[str, Tuple[AST, ...]]]:
    from syncraft.syntax import run
    v, s = run(syntax=syntax, alg=Parser, tokens=tokens)
    if s is not None:
        return v, s.binding.bound()
    else:
        return v, None

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

from syncraft.ast import Token, TokenClass, AST, SyncraftError, word_lexer
from syncraft.constraint import Bindable


T = TypeVar('T', bound=Hashable)  


def underline(text: str) -> str:
    return f"\033[4m{text}\033[0m"
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
                f"@({self.current() if not self.ended() else 'EOF'}), "
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
        length = min(self.index, length) if length is not None else self.index
        ret = " ".join(f"{underline(str(token))}" for token in self.input[self.index - length:self.index])
        if self.index - length > 0:
            ret = "... " + ret
        return ret
    
    def after(self, length: Optional[int] = 3)->str:
        length = min(length, len(self.input) - self.index) if length is not None else len(self.input) - self.index
        ret = " ".join(f"{underline(str(token))}" for token in self.input[self.index:self.index + length])
        if self.index + length < len(self.input):
            ret = ret + " ..."
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
        name = predicate.__name__ if predicate is not None else "." 
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
        captured: Algebra[T, ParserState[T]] = cls(primitive_run, _name=name)
        def error_fn(err: Any) -> Error:
            if isinstance(err, ParserState):
                return Error(message=f"Cannot match token expect {name}, got '{err.current() if not err.ended() or err.pending() else 'EOF'}'", this=captured, state=err)            
            else:
                return Error(message="Cannot match token at unknown state", this=captured)
        # assign the updated parser(with description) to bound variable so the Error.this could be set correctly
        captured = captured.map_error(error_fn)
        return captured        

    @classmethod
    def token(cls,
              *, 
              token_class:TokenClass, 
              **kwargs: Any) -> Algebra[T, ParserState[T]]:
        if token_class is None:
            raise SyncraftError("TokenClass not configured for Parser", offending=cls, expect=TokenClass)
        pred = token_class.predicate(**kwargs)
        return cls.primitive(predicate=pred)



def parse_word(syntax: Syntax[Any, Any], sql: str) -> Tuple[Any, None | FrozenDict[str, Tuple[AST, ...]]]:
    tokens = word_lexer(sql)
    return parse(syntax, tokens)

    
def parse(syntax: Syntax[Any, Any], tokens: List[Token]) -> Tuple[Any, None | FrozenDict[str, Tuple[AST, ...]]]:
    from syncraft.syntax import run
    v, s = run(syntax=syntax, alg=Parser, tokens=tokens)
    if s is not None:
        return v, s.binding.bound()
    else:
        return v, None

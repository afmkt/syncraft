from __future__ import annotations
from typing import (
    Optional, List, Any, Tuple, TypeVar,Hashable,
    Generic, Generator, Callable
)
from syncraft.cache import Cache, Either, Left, Right, Incomplete
from syncraft.constraint import FrozenDict
from syncraft.algebra import (
     Error, Algebra, YieldChannelType, SendChannelType
)
from dataclasses import dataclass, field, replace
from functools import total_ordering
from syncraft.lexer import LexBuilder
from syncraft.syntax import Syntax

from syncraft.ast import Token, TokenClass, AST, SyncraftError, word_lexer
from syncraft.constraint import Bindable

T = TypeVar('T', bound=Hashable)  


def underline(text: str) -> str:
    return ''.join(ch + '\u0332' for ch in text)

@total_ordering
@dataclass(frozen=True)
class ParserState(Bindable, Generic[T]):

    input: Tuple[T, ...] = field(default_factory=tuple)
    index: int = 0
    base: int = 0
    final: bool = False  

    def __repr__(self) -> str:
        indicator = '.'
        indicator = '\u25cf'
        indicator = '\u007c\u25BA'  
        parts = [f"input=[{' '.join(self.before() + [indicator] + self.after())}]"]
        if self.ended():
            parts.append("ended=True")
        if self.pending():
            parts.append("pending=True")
        return f"ParserState({', '.join(parts)})"

    def __str__(self) -> str:
        return self.__repr__()


    def before(self, length: Optional[int] = 3)->List[str]:
        length = min(self.index, length) if length is not None else self.index
        ret = [underline(str(token)) for token in self.input[self.index - length:self.index]]
        if self.index - length > 0:
            ret = ["..."] + ret
        return ret
    
    def after(self, length: Optional[int] = 3)->List[str]:
        length = min(length, len(self.input) - self.index) if length is not None else len(self.input) - self.index
        ret = [underline(str(token)) for token in self.input[self.index:self.index + length]]
        if self.index + length < len(self.input):
            ret = ret + ["..."]
        return ret

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ParserState):
            return False
        return (self.base, self.index) == (other.base, other.index)

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, ParserState):
            return NotImplemented
        return (self.base, self.index) < (other.base, other.index)

    def __add__(self, other: ParserState[T]) -> ParserState[T]:
        if not isinstance(other, ParserState):
            raise SyncraftError("Can only concatenate ParserState with another ParserState", offender=self, expect="ParserState")
        if self.final:
            raise SyncraftError("Cannot concatenate to a final ParserState", offender=self, expect="not final")
        if self.base + len(self.input) != other.base:
            raise SyncraftError("Cannot concatenate ParserState with non-matching base", offender=self, expect=f"base {self.base} + len(input) {len(self.input)} == other.base {other.base}")
        return replace(self, 
                       input=self.input[self.index:] + other.input, 
                       final=other.final, 
                       base=self.base + self.index, 
                       index=0)
    
    def current(self)->T:
        if self.index >= len(self.input):
            raise SyncraftError("Attempted to access token beyond end of stream", offender=self, expect="index < len(input)")
        return self.input[self.index]
    

    def pending(self) -> bool:
        return self.index >= len(self.input) and not self.final

    def ended(self) -> bool:
        return self.index >= len(self.input) and self.final

    def advance(self) -> ParserState[T]:
        return replace(self, index=min(self.index + 1, len(self.input)))
            
    
    
@dataclass(frozen=True)
class Parser(Algebra[T, ParserState[T]]):
    
    @classmethod
    def state(cls, tokens: List[T]) -> ParserState[T]: # type: ignore
        return ParserState(input=tuple(tokens), index=0, final=True, base=0)

    @classmethod
    def primitive(cls, 
                  *, 
                  predicate: Optional[Callable[[T], bool]]=None,
                  generator: Optional[Callable[..., T]] = None
                  )-> Algebra[T, ParserState[T]]:
        name = predicate.__name__ if predicate is not None else "." 
        def primitive_run(state: ParserState[T], 
                          cache:Cache[ParserState[T], Either[Any, Tuple[Any, ParserState[T]]]]) -> Generator[
                              YieldChannelType, 
                              SendChannelType, 
                              Either[Any, Tuple[T, ParserState[T]]]]:
            while True:
                if state.ended():
                    return (yield from cache.return_value(Left(state), state, name=predicate.__name__ if predicate else 'EOF'))
                elif state.pending():
                    tmp = yield Incomplete(state)
                    assert isinstance(tmp, ParserState), "Incomplete must yield a ParserState"
                    state = tmp
                else:
                    token = state.current()
                    assert callable(predicate), "Predicate must be callable"
                    if token is None or not predicate(token):
                        return (yield from cache.return_value(Left(state), state, name=predicate.__name__))
                    else:
                        return (yield from cache.return_value(Right((token, state.advance())), state, name=predicate.__name__))
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
            raise SyncraftError("TokenClass not configured for Parser", offender=cls, expect=TokenClass)
        pred = token_class.predicate(**kwargs)
        return cls.primitive(predicate=pred)

    @classmethod
    def lex(cls, pattern: LexBuilder) -> Algebra[T, ParserState[T]]:
        if pattern.suggested_tag is None:
            raise SyncraftError("Pattern must have a suggested_tag to be used in Parser.re", offender=pattern, expect="suggested_tag")
        return cls.token(token_class=TokenClass(pattern.suggested_tag))


def parse_word(syntax: Syntax[Any, Any], sql: str, *, cache: Optional[Cache[Any, Any]] = None) -> Tuple[Any, None | FrozenDict[str, Tuple[AST, ...]]]:
    tokens = word_lexer(sql)
    return parse(syntax, tokens, cache=cache)

    
def parse(syntax: Syntax[Any, Any], 
          tokens: List[Token],
          *,
          cache: Optional[Cache[Any, Any]] = None) -> Tuple[Any, None | FrozenDict[str, Tuple[AST, ...]]]:
    from syncraft.syntax import run
    v, s = run(syntax=syntax, alg=Parser, tokens=tokens, cache=cache)
    if s is not None:
        return v, s.binding.bound()
    else:
        return v, None

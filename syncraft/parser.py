from __future__ import annotations
from typing import (
    Optional, List, Any, Tuple, TypeVar,Hashable,
    Generic, Generator, Callable, Type, Mapping
)
from syncraft.lexer import (
    Lexer,
    CacheWithLexer,
    LexerResult,
    LexerProtocol,
    ExtLexer,
)
from syncraft.cache import Cache, Either, Left, Right, Incomplete
from syncraft.constraint import FrozenDict
from syncraft.algebra import (
     Error, Algebra, YieldChannelType, SendChannelType
)
from dataclasses import dataclass, field, replace
from functools import total_ordering

from syncraft.syntax import Syntax, RunnerProtocol, PayloadKind
from syncraft.input import Input, StreamCursor

from syncraft.ast import Token, AST, SyncraftError
from syncraft.constraint import Bindable
import re

T = TypeVar('T', bound=Hashable)  
A = TypeVar('A')


def underline(text: str) -> str:
    return ''.join(ch + '\u0332' for ch in text)

@total_ordering
@dataclass(frozen=True)
class ParserState(Bindable, Generic[T]):

    input: Tuple[T, ...] | str | bytes = field(default_factory=tuple, compare=False, hash=False)
    index: int = 0
    base: int = 0

    final: bool = False  
    safe_base: int = 0
    choice_depth: int = 0

    def slice(self, start: int, end: int) -> Tuple[T, ...] | str | bytes:
        start_rel = start - self.base
        end_rel = end - self.base
        assert start_rel >= 0 and end_rel <= len(self.input), f"Lexed span no longer buffered {start_rel}:{end_rel}"
        return self.input[start_rel:end_rel]

    def __hash__(self) -> int:
        return self.base + self.index

    def __post_init__(self):
        if isinstance(self.input, list):
            object.__setattr__(self, 'input', tuple(self.input))
        elif not isinstance(self.input, (tuple, str, bytes)):
            raise SyncraftError("Input must be a sequence type", offender=self.input, expect="tuple, str, or bytes")

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

    def _slice_to_display(self, start: int, end: int) -> list[str]:
        segment = self.input[start:end]
        if isinstance(self.input, str):
            return [underline(str(ch)) for ch in segment]
        elif isinstance(self.input, bytes):
            # Decode printable ASCII bytes, otherwise use hex
            result = []
            for b in segment:
                if isinstance(b, int) and 32 <= b < 127:
                    result.append(underline(chr(b)))
                elif isinstance(b, int):
                    result.append(f"\\x{b:02x}")
                else:
                    result.append(str(b))
            return result
        else:
            # Generic token list
            return [underline(str(token)) for token in segment]


    def before(self, length: Optional[int] = 3) -> list[str]:
        length = min(self.index, length) if length is not None else self.index
        ret = self._slice_to_display(self.index - length, self.index)
        if self.index - length > 0:
            ret = ["..."] + ret
        return ret

    def after(self, length: Optional[int] = 3) -> list[str]:
        remaining = len(self.input) - self.index
        length = min(length, remaining) if length is not None else remaining
        ret = self._slice_to_display(self.index, self.index + length)
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

    def gc(self)-> ParserState[T]:
        if self.safe_base > self.base:
            drop = min(self.safe_base - self.base, len(self.input))
            return replace(
                self,
                input=self.input[drop:],
                base=self.safe_base,
                index=max(0, self.index - drop),
            )
        return self

    def extend(self, more: str | bytes | Tuple[T, ...], *, final: bool = False) -> "ParserState[T]":
        if self.final:
            raise SyncraftError("Cannot concatenate to a final ParserState", offender=self, expect="not final")
        if self.safe_base > self.base:
            drop = self.safe_base - self.base
            # We cannot drop more than we have buffered
            drop = min(drop, len(self.input))
            new_input = self.input[drop:] + more # type: ignore
            new_base = self.safe_base
            new_index = max(0, self.index - drop)
        else:
            new_input = self.input + more # type: ignore
            new_base = self.base
            new_index = self.index

        # ---- Step 2: Return new ParserState ----
        return replace(
            self,
            input=new_input,
            base=new_base,
            index=new_index,
            final=self.final or final,
        )

    def abs_index(self) -> int:
        return self.base + self.index    
    
    def current(self)->T:
        if self.index >= len(self.input):
            raise SyncraftError("Attempted to access token beyond end of stream", offender=self, expect="index < len(input)")
        return self.input[self.index] # type: ignore
    

    def pending(self) -> bool:
        return self.index >= len(self.input) and not self.final

    def ended(self) -> bool:
        return self.index >= len(self.input) and self.final

    def advance(self) -> ParserState[T]:
        return replace(self, index=min(self.index + 1, len(self.input)))
            
    
    
@dataclass(frozen=True)
class Parser(Algebra[T, ParserState[T]]):

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
    def token(
        cls,
        *,
        lexer_class: Type[LexerProtocol],
        **kwargs: Any,
    ) -> Algebra[T, ParserState[T]]:
        return cls.lex(lexer_class=lexer_class, **kwargs)

    @classmethod
    def lex(cls, 
            *,
            lexer_class: Type[LexerProtocol],
            **kwargs: Any) -> Algebra[T, ParserState[T]]:
        
        
        def lex_run(state: ParserState[T], 
                    cache: Cache[ParserState[T], Either[Any, Tuple[Any, ParserState[T]]]]) -> Generator[
                              YieldChannelType, 
                              SendChannelType, 
                              Either[Any, Tuple[T, ParserState[T]]]]:
            if not isinstance(cache, CacheWithLexer):
                raise SyncraftError("Cache must be CacheWithLexer to use lex", offender=cache, expect="CacheWithLexer")
            if not isinstance(cache.lexer, LexerProtocol):
                raise SyncraftError("Lexer not provided in cache.additional_kwargs", offender=cache, expect="lexer in cache.additional_kwargs")
            lexer = cache.lexer
            ntag = lexer.tag(**kwargs)
            while True:
                if state.ended():
                    err = Error(message="Cannot match token at end of input", this=lex_run, state=state)
                    return (yield from cache.return_value(Left(err), state, name='EOF'))
                elif state.pending():
                    tmp = yield Incomplete(state)
                    assert isinstance(tmp, ParserState), "Incomplete must yield a ParserState"
                    state = tmp
                else:
                    match lexer.match(ntag, state.current(), state.abs_index()):
                        case Left(err_msg):
                            err = Error(message=err_msg, this=lex_run, state=state)            
                            return (yield from cache.return_value(Left(err), state, name=str(ntag)))
                        case Right(None):
                            state = state.advance()
                        case Right(LexerResult(tag=tag, start=start, end=end, value=lexeme)):
                            if lexeme is None:
                                token = Token(text=state.slice(start, end), token_type=tag)
                            else:
                                token = lexeme
                            return (yield from cache.return_value(Right((token, state.advance())), state, name=str(ntag)))
                        case _:
                            raise SyncraftError("Unknown result from lexer", offender=state, expect="LexerResult or None")

        return cls(lex_run, _name=lexer_class.name(**kwargs))



@dataclass
class Runner(RunnerProtocol[Any, ParserState[T]]):
    input : Input[T] 
    chunk_size: int = 4096
    cursor : StreamCursor[T] = field(init=False, repr=False, compare=False, hash=False)
    
    def __post_init__(self):    
        assert self.input is not None, "Input must be provided to Runner"
        self.cursor = StreamCursor(self.input, chunk_size=self.chunk_size)
    def bootstrap(self, 
                  syntax: Syntax[Any, ParserState[T]], 
                  alg_cls: Type[Algebra[Any, ParserState[T]]],
                  cache: Optional[Cache[ParserState[T], Either[Any, Tuple[Any, ParserState[T]]]]] = None
                  ) -> Tuple[Algebra[Any, ParserState[T]], Cache[ParserState[T], Either[Any, Tuple[Any, ParserState[T]]]], ParserState[T]]:
        assert cache is None or isinstance(cache, CacheWithLexer), "Cache must be CacheWithLexer or None"
        parser = syntax(alg_cls)
        cache = cache or CacheWithLexer()
        buffer, final = self.cursor.initial_buffer()
        initial_state = ParserState(input=buffer, index=0, base=0, final=final)
        cache.lexer = self._instantiate_lexer(syntax=syntax, config=parser.config(), kind=self.input.payload_kind)

        return syntax(alg_cls), cache, initial_state
    
    def resume(self, request: Incomplete[ParserState[T]]) -> ParserState[T]:
        state = request.state
        if state.final:
            raise SyncraftError("Cannot resume parser: input is final", offender=state, expect="not final")
        chunk, final = self.cursor.next_chunk()
        return state.extend(chunk, final=final)

    def payload_kind(self) -> Optional[PayloadKind]: 
        return {
            'text': PayloadKind.TEXT,
            'bytes': PayloadKind.BINARY,
            'tokens': PayloadKind.TOKEN,
        }.get(self.input.payload_kind, None)
        

    def _instantiate_lexer(
            self,
            *,
            syntax: Syntax[Any, Any],
            config: Mapping[str, Any],
            kind: str,
        ) -> LexerProtocol[Any]:
        bound_cls = config.get("lexer_class")
        if not isinstance(bound_cls, type) or not issubclass(bound_cls, LexerProtocol):
            raise SyncraftError("Lexer class must be a subclass of LexerProtocol", offender=bound_cls, expect="subclass of LexerProtocol")
        if kind in ('text', 'bytes'):
            if bound_cls is None or not issubclass(bound_cls, Lexer):
                raise SyncraftError(f'The lexer class for text input must be a subclass of Lexer, got {bound_cls}', offender=bound_cls, expect="subclass of Lexer")
        else:
            if bound_cls is None or not issubclass(bound_cls, ExtLexer):
                raise SyncraftError(f'The lexer class for token input must be a subclass of ExtLexer, got {bound_cls}', offender=bound_cls, expect="subclass of ExtLexer")
        lexer = bound_cls.from_syntax(syntax)
        assert isinstance(lexer, LexerProtocol)
        return lexer




def parse_word(syntax: Syntax[Any, Any], 
               sql: str, 
               *, 
               cache: None| CacheWithLexer[Any, Any, Any] = None
               ) -> Tuple[Any, None | FrozenDict[str, Tuple[AST, ...]]]:
    tokens: List[Token]  = [Token(t) for t in re.split(r'[\x00-\x1F\x7F\s]+', sql)]
    return parse_data(syntax, tokens, cache=cache)

    
def parse_data(syntax: Syntax[Any, Any], 
          tokens: List[Token],
          *,
          cache: None|CacheWithLexer[Any, ParserState[T], Either[Any, Tuple[Any, ParserState[T]]]] = None
          ) -> Tuple[Any, None | FrozenDict[str, Tuple[AST, ...]]]:
    runner = Runner(input=Input.from_data(tokens))
    v, s = runner(syntax=syntax, alg_cls=Parser, cache=cache)
    if s is not None:
        return v, s.binding.bound()
    else:
        return v, None


def parse(syntax: Syntax[Any, Any],
          input: Input[T],
          *,
          cache: None | CacheWithLexer[Any, ParserState[T], Either[Any, Tuple[Any, ParserState[T]]]] = None
          ) -> Tuple[Any, None | ParserState[T]]:
    runner = Runner(input=input)
    return runner(syntax=syntax, alg_cls=Parser, cache=cache)


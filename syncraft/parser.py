from __future__ import annotations
from typing import (
    Optional, List, Any, Tuple, TypeVar,Hashable, Literal,
    Generic, Generator, Type, Union
)
from syncraft.lexer import (
    LexerBase,
    LexerResult,
    LexerProtocol
)
from syncraft.cache import Cache, Either, Left, Right, Incomplete
from syncraft.utils import FrozenDict
from syncraft.algebra import (
     Error, Algebra, YieldChannelType, SendChannelType
)
from dataclasses import dataclass, field, replace
from functools import total_ordering

from syncraft.syntax import Syntax, RunnerProtocol
from syncraft.input import StreamCursor, PayloadKind

from syncraft.ast import Token, AST, SyncraftError
from syncraft.constraint import Bindable
import re

from pathlib import Path
import io
import asyncio


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

    @property
    def cache_key(self) -> int:
        return self.base + self.index

    def unused_cache_key(self) -> int:
        return self.safe_base

    def enter(self) -> ParserState[T]:
        return replace(self, choice_depth=self.choice_depth + 1)
    
    def leave(self) -> ParserState[T]:
        if self.choice_depth > 1:
            return replace(self, choice_depth=self.choice_depth - 1) 
        else:
            return replace(self, choice_depth=0, safe_base=max(self.base + self.index, self.safe_base)) 


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
    def lex(cls, 
            *,
            lexer_class: Type[LexerProtocol] | None = None,
            **kwargs: Any) -> Algebra[T, ParserState[T]]:
        if lexer_class is None:
            lexer:LexerProtocol[Any] | None = LexerBase.from_kwargs(**kwargs)
        else:
            lexer = lexer_class.from_kwargs(**kwargs)            
        if lexer is None:
            raise SyncraftError("Lexer could not be created with the given parameters.", offender=kwargs, expect="Valid lexer parameters")
        ntags = lexer.tags()
        name = f"{','.join([str(tag) for tag in ntags])}"
        def lex_run(state: ParserState[T], 
                    cache: Cache[ParserState[T]]) -> Generator[
                              YieldChannelType, 
                              SendChannelType, 
                              Either[Any, Tuple[T, ParserState[T]]]]:
            lexer.reset()
            yield from ()
            while True:
                if state.ended():
                    match lexer.candidate():
                        
                        case Right(LexerResult(tag=tag, start=start, end=end, value=lexeme)):
                            if lexeme is None:
                                token = Token(text=state.slice(start, end), token_type=tag)
                            else:
                                token = lexeme
                            return Right((token, state.advance())) # type: ignore
                        case _:
                            return Left(Error(message=f"Cannot match token at end of input, expect {name}", this=lex_run, state=state))
                elif state.pending():
                    tmp = yield Incomplete(state)
                    assert isinstance(tmp, ParserState), "Incomplete must yield a ParserState"
                    state = tmp
                else:
                    match lexer.match(ntags, state.current(), state.abs_index()):
                        case Left(err_msg):
                            return Left(Error(message=f"{err_msg}, expect {name}", this=lex_run, state=state))
                        case Right(None):
                            state = state.advance()
                        case Right(LexerResult(tag=tag, start=start, end=end, value=lexeme)):
                            if lexeme is None:
                                token = Token(text=state.slice(start, end), token_type=tag)
                            else:
                                token = lexeme
                            if end > state.index:
                                state = state.advance()
                            return Right((token, state)) # type: ignore
                        case _:
                            raise SyncraftError("Unknown result from lexer", offender=state, expect="LexerResult or None")

        return cls(lex_run)



@dataclass
class Runner(RunnerProtocol[Any, ParserState[T]]):
    def algebra(self, 
                syntax: Syntax[Any, ParserState[T]], 
                alg_cls: Type[Algebra[Any, ParserState[T]]],
                payload_kind: Optional[PayloadKind]=None) -> Algebra[Any, ParserState[T]]:

        return syntax(alg_cls, payload_kind=payload_kind)
    
    def resume(self, request: Optional[ParserState[T]], cursor: Optional[StreamCursor[T]]) -> ParserState[T]:
        assert cursor is not None, "Cursor must be provided to resume Parser"
        if request is not None:
            if request.final:
                raise SyncraftError("Cannot resume parser: input is final", offender=request, expect="not final")
            chunk, final = cursor.next_chunk()
            return request.extend(chunk, final=final)
        else:
            buffer, final = cursor.next_chunk()
            return ParserState(input=buffer, index=0, base=0, final=final)

        

def parser(syntax: Syntax[Any, Any], payload_kind: PayloadKind) -> Algebra[Any, Any]:
    runner: Runner[Any] = Runner()
    return runner.algebra(syntax=syntax, alg_cls=Parser, payload_kind=payload_kind)


def parse(syntax: Syntax[Any, Any],
          cursor: StreamCursor[Any],
          *,
          cache: None | Cache[ParserState[T]] = None
          ) -> Tuple[Any, Any]:
    runner: Runner[T] = Runner()
    return runner(syntax=syntax, alg_cls=Parser, cursor=cursor, cache=cache)



def parse_word(syntax: Syntax[Any, Any], 
               data: str, 
               *, 
               cache: None| Cache[Any] = None
               ) -> Tuple[Any, None | FrozenDict[str, Tuple[AST, ...]]]:
    tokens: List[Token]  = [Token(t) for t in re.split(r'[\x00-\x1F\x7F\s]+', data)]
    return parse_data(syntax, tokens, cache=cache)

    
def parse_data(syntax: Syntax[Any, Any], 
          data: List[T],
          *,
          cache: None | Cache[ParserState[T]] = None
          ) -> Tuple[Any, None | FrozenDict[str, Tuple[AST, ...]]]:
    input : StreamCursor[T] = StreamCursor.from_data(data)
    v, s = parse(syntax, input, cache=cache)
    if s is not None:
        return v, s.binding.bound()
    else:
        return v, None


def parse_string(syntax: Syntax[Any, Any],
                 data: str,
                 *,
                 cache: None | Cache[ParserState[str]] = None
                 ) -> Tuple[Any, None | ParserState[str]]:
    input : StreamCursor[str] = StreamCursor.from_data(data)
    return parse(syntax, input, cache=cache)

def parse_bytes(syntax: Syntax[Any, Any],
                data: bytes,
                *,
                cache: None | Cache[ParserState[bytes]] = None
                ) -> Tuple[Any, None | ParserState[bytes]]:
    input : StreamCursor[bytes] = StreamCursor.from_data(data)
    return parse(syntax, input, cache=cache)

def parse_file(syntax: Syntax[Any, Any],
               filepath: str | Path,
               *,
               mode: Literal['text', 'binary'] = 'text', 
               cache: None | Cache[ParserState[str | bytes]] = None
               ) -> Tuple[Any, None | ParserState[str | bytes]]:
    if mode == 'text':        
        input : StreamCursor[str] = StreamCursor.from_path(filepath, mode=mode)
        return parse(syntax, input, cache=cache)
    else:
        inputb : StreamCursor[bytes] = StreamCursor.from_path(filepath, mode=mode)
        return parse(syntax, inputb, cache=cache)

def parse_stream(syntax: Syntax[Any, Any],
                 stream: Union[io.TextIOBase, io.BufferedIOBase, asyncio.StreamReader],
                 *,
                 mode: Literal['text', 'binary'] = 'text', 
                 cache: None | Cache[ParserState[str | bytes]] = None
                 ) -> Tuple[Any, None | ParserState[str | bytes]]:
    input : StreamCursor[str | bytes] = StreamCursor.from_stream(stream, mode=mode) # type: ignore
    return parse(syntax, input, cache=cache)

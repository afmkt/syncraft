from __future__ import annotations
from typing import (
    Optional, List, Any, Tuple, TypeVar,Hashable, Literal,
    Generic, Generator, Type, Union
)
from syncraft.lexer import (
    LexerBase,
    LexerResult,
    LexerProtocol,
    LexerError
)
from syncraft.cache import Cache, Either, Left, Right, Incomplete
from syncraft.utils import FrozenDict
from syncraft.algebra import (
     Algebra, YieldChannelType, SendChannelType, Error
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
import os

def get_tab_width() -> int:
    """Get the tab width from system settings, defaulting to 8 if unavailable."""
    try:
        # Try to get from TABSIZE environment variable
        if 'TABSIZE' in os.environ:
            return int(os.environ['TABSIZE'])
        
        # Try to get from common shell variables
        for var in ['COLUMNS', 'TERM']:
            if var in os.environ:
                # Check if there are any editor-specific tab settings
                pass
        
        # Try to read from common editor config files
        home = os.path.expanduser('~')
        config_files = [
            os.path.join(home, '.vimrc'),
            os.path.join(home, '.editorconfig'),
            os.path.join('.editorconfig')
        ]
        
        for config_file in config_files:
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r') as f:
                        content = f.read()
                        # Look for tab width settings
                        import re
                        # Vim style: set tabstop=4
                        vim_match = re.search(r'(?:set\s+)?tabstop\s*[=:]\s*(\d+)', content, re.IGNORECASE)
                        if vim_match:
                            return int(vim_match.group(1))
                        # EditorConfig style: tab_width = 4
                        ec_match = re.search(r'tab_width\s*=\s*(\d+)', content, re.IGNORECASE)
                        if ec_match:
                            return int(ec_match.group(1))
                except (IOError, ValueError):
                    continue
        
        # Default to standard tab width
        return 8
    except (ValueError, OSError):
        return 8


T = TypeVar('T', bound=Hashable)  
A = TypeVar('A')


def underline(text: str, ul: bool) -> str:
    if ul:
        return ''.join(ch + '\u0332' for ch in text)
    else:
        return text

@total_ordering
@dataclass(frozen=True)
class ParserState(Bindable, Generic[T]):

    input: Tuple[T, ...] | str | bytes = field(default_factory=tuple, compare=False, hash=False)
    index: int = 0
    base: int = 0

    final: bool = False  
    safe_base: int = 0
    choice_depth: int = 0

    line: int = 0
    column: int = 0

    @property
    def payload_kind(self) -> PayloadKind:
        if isinstance(self.input, bytes):
            return 'bytes'
        elif isinstance(self.input, tuple):
            return 'token'
        elif isinstance(self.input, str):
            return 'text'
        else:
            raise SyncraftError("Unknown input type for ParserState", offender=self.input, expect="str, bytes, or tuple")

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
        elif isinstance(self.input, str):
            if self.line == 0 and self.column == 0:
                object.__setattr__(self, 'line', 1)
                object.__setattr__(self, 'column', 1)
        elif not isinstance(self.input, (tuple, str, bytes)):
            raise SyncraftError("Input must be a sequence type", offender=self.input, expect="tuple, str, or bytes")

    @property
    def cursor(self) -> str:
        indicator = '.'
        indicator = '\u25cf'
        indicator = '\u007c\u25BA'  
        return indicator

    def format_input(self, template:str, ul: bool = True) -> List[str]:
        ret = []  
        ln = template.format(self.str_input(ul=ul))
        next = ' ' * self.cursor_at(ln) + '^'
        ret.append(ln)
        ret.append(next)
        return ret


    def str_input(self, ul: bool) -> str:
        return f"[ {' '.join(self.before(ul=ul) + [self.cursor] + self.after(ul=ul))} ]"
    
    def cursor_at(self, input: str) -> int:
        ret = 0
        tab_width = get_tab_width()
        for i in range(len(input)):
            char = input[i]
            # Reset position only on newline (starts new line)
            if char == '\n':
                ret = 0
                continue
            # Handle tab character with dynamic tab width
            elif char == '\t':
                ret = (ret // tab_width + 1) * tab_width  # Move to next tab stop
                continue
            # Handle other control characters (don't affect position tracking)
            elif ord(char) < 32:
                continue
            
            if input[i:i+len(self.cursor)] == self.cursor:
                return ret + len(self.cursor) + 1
            ret += 1
        return -1


    @property
    def str_line(self) -> str:
        if self.line > 0:
            return f"line={self.line}"
        return ''
    
    @property
    def str_column(self) -> str:
        if self.column > 0:
            return f"column={self.column}"
        return ''
    
    @property
    def str_ended(self) -> str:
        if self.ended:
            return "ended=True"
        return ''
    @property
    def str_pending(self) -> str:
        if self.pending:
            return "pending=True"
        return ''

    def __str__(self) -> str:
        parts = [f"input={self.str_input(ul=True)}"]
        if self.ended:
            parts.append(self.str_ended)
        if self.pending:
            parts.append(self.str_pending)
        if self.line > 0:
            parts.append(self.str_line)
        if self.column > 0:
            parts.append(self.str_column)
        return f"{self.__class__.__name__}({', '.join(parts)})"

    def __pretty__(self) -> str:
        return self.__str__()
    
    def __rich__(self) -> str:
        return self.__str__()


    def _slice_to_display(self, start: int, end: int, ul: bool) -> list[str]:
        segment = self.input[start:end]
        if isinstance(self.input, str):
            return [underline(str(ch), ul) for ch in segment]
        elif isinstance(self.input, bytes):
            # Decode printable ASCII bytes, otherwise use hex
            result = []
            for b in segment:
                if isinstance(b, int) and 32 <= b < 127:
                    result.append(underline(chr(b), ul))
                elif isinstance(b, int):
                    result.append(f"\\x{b:02x}")
                else:
                    result.append(str(b))
            return result
        else:
            # Generic token list
            return [underline(str(token), ul) for token in segment]


    def before(self, length: Optional[int] = 3, ul: bool = True) -> list[str]:
        length = min(self.index, length) if length is not None else self.index
        ret = self._slice_to_display(self.index - length, self.index, ul)
        if self.index - length > 0:
            ret = ["..."] + ret
        return ret

    def after(self, length: Optional[int] = 3, ul: bool = True) -> list[str]:
        remaining = len(self.input) - self.index
        length = min(length, remaining) if length is not None else remaining
        ret = self._slice_to_display(self.index, self.index + length, ul)
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
        if not isinstance(self.input, more.__class__):
            raise SyncraftError("Cannot extend ParserState with different input type", offender=more.__class__, expect=self.input.__class__)
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
    
    @property
    def current(self) -> T:
        if self.index >= len(self.input):
            raise SyncraftError("Attempted to access token beyond end of stream", offender=self, expect="index < len(input)")
        return self.input[self.index] # type: ignore
    
    @property
    def pending(self) -> bool:
        return self.index >= len(self.input) and not self.final
    
    @property
    def ended(self) -> bool:
        return self.index >= len(self.input) and self.final

    def advance(self) -> ParserState[T]:
        if isinstance(self.input, str):
            if self.current == '\n':
                return replace(self, index=min(self.index + 1, len(self.input)), line=self.line + 1, column=1)
            else:
                return replace(self, index=min(self.index + 1, len(self.input)), column=self.column + 1)
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
        # name = f"{','.join([str(tag) for tag in ntags])}"
        def lex_run(state: ParserState[T], 
                    cache: Cache[ParserState[T]]) -> Generator[
                              YieldChannelType, 
                              SendChannelType, 
                              Either[Any, Tuple[T, ParserState[T]]]]:
            lexer.reset()
            yield from ()
            while True:
                if state.ended:
                    match lexer.candidate():
                        case Right(LexerResult(tag=tag, start=start, end=end, value=lexeme)):
                            if lexeme is None:
                                token = Token(text=state.slice(start, end), token_type=tag)
                            else:
                                token = lexeme
                            return Right((token, state.advance())) # type: ignore
                        case Left(LexerError(message=err_msg, index=index, offender=offender, expect=expect)):
                            return Left(Error(message="Cannot match token at end of input", this=lex_run, state=state, error=LexerError(message=err_msg, index=index, offender=offender, expect=expect)))
                        case e:
                            raise SyncraftError("Unknown result from lexer", offender=e, expect="LexerResult or LexerError")
                elif state.pending:
                    tmp = yield Incomplete(state)
                    assert isinstance(tmp, ParserState), "Incomplete must yield a ParserState"
                    state = tmp
                else:
                    match lexer.match(ntags, state.current, state.abs_index()):
                        case Left(LexerError(message=err_msg, index=index, offender=offender, expect=expect)):
                            return Left(Error(message=err_msg, this=lex_run, state=state, error=LexerError(message=err_msg, index=index, offender=offender, expect=expect)))
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
                        case e:
                            raise SyncraftError("Unknown result from lexer", offender=e, expect="LexerResult or None or LexerError")

        return cls(lex_run)



@dataclass
class Runner(RunnerProtocol[Any, ParserState[T]]):
    def algebra(self, 
                syntax: Syntax[Any, ParserState[T]], 
                alg_cls: Type[Algebra[Any, ParserState[T]]],
                payload_kind: Optional[PayloadKind]=None) -> Algebra[Any, ParserState[T]]:

        return syntax(alg_cls, payload_kind=payload_kind)
    
    def resume(self, request: Optional[ParserState[T]], cursor: Optional[StreamCursor[T]]) -> ParserState[T]:
        assert cursor or request, "Either cursor or request must be provided to resume Parser"
        if request is not None:
            if cursor is None:
                return request
            if request.final:
                raise SyncraftError("Cannot resume parser: input is final", offender=request, expect="not final")
            chunk, final = cursor.next_chunk()
            return request.extend(chunk, final=final)
        else:
            assert cursor is not None, "Cursor must be provided to resume Parser"
            buffer, final = cursor.next_chunk()
            return ParserState(input=buffer, index=0, base=0, final=final)

        

def parser(syntax: Syntax[Any, Any], payload_kind: PayloadKind) -> Algebra[Any, Any]:
    runner: Runner[Any] = Runner()
    return runner.algebra(syntax=syntax, alg_cls=Parser, payload_kind=payload_kind)


def parse(syntax: Syntax[Any, Any],
          data: StreamCursor[Any] | ParserState[Any],
          *,
          cache: None | Cache[ParserState[T]]
          ) -> Tuple[Any, Any]:
    runner: Runner[T] = Runner()
    if isinstance(data, ParserState):
        return runner.once(syntax=syntax, alg_cls=Parser, state=data, cursor=None, cache=cache)
    else:
        return runner.once(syntax=syntax, alg_cls=Parser, state=None, cursor=data, cache=cache)



def parse_word(syntax: Syntax[Any, Any], 
               data: str, 
               *, 
               cache: None| Cache[Any]
               ) -> Tuple[Any, None | FrozenDict[str, Tuple[AST, ...]]]:
    tokens: List[Token]  = [Token(t) for t in re.split(r'[\x00-\x1F\x7F\s]+', data)]
    return parse_data(syntax, tokens, cache=cache)

    
def parse_data(syntax: Syntax[Any, Any], 
          data: List[T],
          *,
          cache: None | Cache[ParserState[T]]
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
                 cache: None | Cache[ParserState[str]]
                 ) -> Tuple[Any, None | ParserState[str]]:
    input : StreamCursor[str] = StreamCursor.from_data(data)
    return parse(syntax, input, cache=cache)

def parse_bytes(syntax: Syntax[Any, Any],
                data: bytes,
                *,
                cache: None | Cache[ParserState[bytes]]
                ) -> Tuple[Any, None | ParserState[bytes]]:
    input : StreamCursor[bytes] = StreamCursor.from_data(data)
    return parse(syntax, input, cache=cache)

def parse_file(syntax: Syntax[Any, Any],
               filepath: str | Path,
               *,
               mode: Literal['text', 'binary'] = 'text', 
               cache: None | Cache[ParserState[str | bytes]]
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
                 cache: None | Cache[ParserState[str | bytes]]
                 ) -> Tuple[Any, None | ParserState[str | bytes]]:
    input : StreamCursor[str | bytes] = StreamCursor.from_stream(stream, mode=mode) # type: ignore
    return parse(syntax, input, cache=cache)

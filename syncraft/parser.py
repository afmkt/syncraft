from __future__ import annotations
from typing import (
    Optional, List, Any, Tuple, TypeVar,Hashable,
    Generic, Generator, Callable, Type
)
from syncraft.charset import CodeUniverse
from syncraft.lexer import Lexer, CacheWithLexer, LexerResult
from syncraft.cache import Cache, Either, Left, Right, Incomplete
from syncraft.constraint import FrozenDict
from syncraft.algebra import (
     Error, Algebra, YieldChannelType, SendChannelType
)
from dataclasses import dataclass, field, replace
from functools import total_ordering
from syncraft.fa import FABuilder
from syncraft.syntax import Syntax
from syncraft.input import Input, StreamCursor

from syncraft.ast import Token, TokenClass, AST, SyncraftError, word_lexer
from syncraft.constraint import Bindable

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
    def token(cls,
              *, 
              token_class:TokenClass, 
              **kwargs: Any) -> Algebra[T, ParserState[T]]:
        if token_class is None:
            raise SyncraftError("TokenClass not configured for Parser", offender=cls, expect=TokenClass)
        pred = token_class.predicate(**kwargs)
        return cls.primitive(predicate=pred)

    @classmethod
    def lex(cls, pattern: FABuilder) -> Algebra[T, ParserState[T]]:
        name = str(pattern)
        def lex_run(state: ParserState[T], 
                    cache: Cache[ParserState[T], Either[Any, Tuple[Any, ParserState[T]]]]) -> Generator[
                              YieldChannelType, 
                              SendChannelType, 
                              Either[Any, Tuple[T, ParserState[T]]]]:
            if not isinstance(cache, CacheWithLexer):
                raise SyncraftError("Cache must be CacheWithLexer to use lex", offender=cache, expect="CacheWithLexer")

            if cache.lexer is None:
                raise SyncraftError("Lexer not provided in cache.additional_kwargs", offender=cache, expect="lexer in cache.additional_kwargs")
            lexer = cache.lexer
            while True:
                if state.ended():
                    return (yield from cache.return_value(Left(state), state, name='EOF'))
                elif state.pending():
                    tmp = yield Incomplete(state)
                    assert isinstance(tmp, ParserState), "Incomplete must yield a ParserState"
                    state = tmp
                else:
                    match lexer.match(state.current(), state.abs_index()):
                        case Left(err_msg):
                            err = Error(message=err_msg, this=lex_run, state=state)            
                            return (yield from cache.return_value(Left(err), state, name=name))
                        case Right(None):
                            state = state.advance()
                        case Right(LexerResult(tag=tag, start=start, end=end, value=lexeme)):
                            if isinstance(lexeme, Token):
                                token = lexeme
                            elif lexeme is not None:
                                token = Token(text=lexeme, token_type=tag)
                            else:
                                token = Token(text=state.slice(start, end), token_type=tag)
                            return (yield from cache.return_value(Right((token, state.advance())), state, name=name))
                        case _:
                            raise SyncraftError("Unknown result from lexer", offender=state, expect="LexerResult or None")

        return cls(lex_run, _name=name)


def parse_word(syntax: Syntax[Any, Any], sql: str, *, cache: Cache[Any, Any]) -> Tuple[Any, None | FrozenDict[str, Tuple[AST, ...]]]:
    tokens = word_lexer(sql)
    return parse(syntax, tokens, cache=cache)

    
def parse(syntax: Syntax[Any, Any], 
          tokens: List[Token],
          *,
          cache: Cache[ParserState[T], Either[Any, Tuple[Any, ParserState[T]]]]
          ) -> Tuple[Any, None | FrozenDict[str, Tuple[AST, ...]]]:
    from syncraft.syntax import run_state
    state = ParserState(input=tuple(tokens), index=0, final=True, base=0)
    v, s = run_state(syntax=syntax, alg=Parser, state=state, cache=cache)
    if s is not None:
        return v, s.binding.bound()
    else:
        return v, None


def run(*,
        syntax: Syntax[A, ParserState[T]],
        alg: Type[Algebra[A, ParserState[T]]],
        source: Input[T],
        chunk_size: int = 4096,
        universe: CodeUniverse[Any], 
        cache: Optional[CacheWithLexer[Any, ParserState[T], Either[Any, Tuple[A, ParserState[T]]]]] = None,
        ) -> Tuple[Any, None | ParserState[T]]:
    
    gen_cache = cache or CacheWithLexer()
    assert isinstance(gen_cache, CacheWithLexer), "Cache must be CacheWithLexer or None"
    
    gen_cache.lexer = Lexer.from_builders(universe, *syntax.fabuilder())

    parser = syntax(alg)
    
    cursor = StreamCursor(source, chunk_size=chunk_size)
    buffer, final = cursor.initial_buffer()
    state = ParserState(input=buffer, index=0, base=0, final=final)
    parser_gen = parser.run(state, cache=gen_cache)

    try:
        result = next(parser_gen)
        while True:
            if isinstance(result, Incomplete):
                pending_state: ParserState[T] = result.state

                if pending_state.final:
                    raise SyncraftError("Parser requested more input but input is final", offender=pending_state, expect="not final")

                chunk, final = cursor.next_chunk()
                pending_state = pending_state.extend(chunk, final=final)
                result = parser_gen.send(pending_state)
            else:
                raise AssertionError("Unexpected yield from algebra: expected Incomplete")  # pragma: no cover
    except StopIteration as e:
        result = e.value
        if isinstance(result, Right):
            return result.value[0], result.value[1]
        if isinstance(result, Left):
            return result.value, None
        return Error(this=result, message="Algebra returned data that is not Left or Right"), None


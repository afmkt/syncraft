from __future__ import annotations
import pytest
from dataclasses import dataclass, replace, field

from syncraft.cache import Cache
from syncraft.syntax import Syntax
# from rich import print
from syncraft.constraint import Bindable, Binding
from syncraft.ast import Token
from syncraft.fa import Builder
from syncraft.input import StreamCursor
from syncraft.parser import parse as parser_run


from syncraft.regex import benchmark_fair, verify
from syncraft.alphabet import Alphabet
from syncraft.parser import  parse_word
import syncraft.generator as gen
from rich import print
from syncraft.parser import parse_word

from syncraft.regex import benchmark_fair, verify


from typing import Any, Generic, TypeVar, Protocol, runtime_checkable

@runtime_checkable
class X(Protocol):
    @property
    def binding(self) -> Binding: ...

T = TypeVar('T')
@dataclass(slots=True)
class TokenWithBytes(X, Generic[T]):
    binding: Binding = field(default_factory=Binding)

    index: int = 0
    base : int = 0
    final: bool = False
    input: str = ''
    choice: int = 0
    safe: int = 0
    line: int = 0
    column: int = 0 

    @classmethod
    def new(cls, binding: Binding, index: int, base: int, final: bool, input: str, choice: int, safe: int, line: int, column: int) -> TokenWithBytes:
        obj = cls.__new__(cls)
        object.__setattr__(obj, 'binding', binding)
        object.__setattr__(obj, 'index', index)
        object.__setattr__(obj, 'base', base)
        object.__setattr__(obj, 'final', final)
        object.__setattr__(obj, 'input', input)
        object.__setattr__(obj, 'choice', choice)
        object.__setattr__(obj, 'safe', safe)
        object.__setattr__(obj, 'line', line)
        object.__setattr__(obj, 'column', column)
        return obj
    
def rep():
    import timeit
    obj = TokenWithBytes.new(binding=Binding(), index=1, base=2, final=True, input="input", choice=3, safe=4, line=5, column=6)
    reptime = timeit.timeit(lambda: replace(obj, choice=obj.choice+1), number=1000000)
    print(f"replace time: {reptime:.6f} seconds")
    newtime = timeit.timeit(lambda: TokenWithBytes.new(binding=obj.binding, index=obj.index, base=obj.base, final=obj.final, input=obj.input, choice=obj.choice+1, safe=obj.safe, line=obj.line, column=obj.column), number=1000000)
    print(f"new time: {newtime:.6f} seconds")
    mutabletime = timeit.timeit(lambda: setattr(obj, 'choice', obj.choice+1), number=1000000)
    print(f"mutable time: {mutabletime:.6f} seconds")
    print(f"ratio (replace/mutable): {reptime/mutabletime:.2f}")
    print(f"ratio (replace/new): {reptime/newtime:.2f}")


def test1_simple_then() -> None:
    A, B, C = Syntax.literal("a"), Syntax.literal("b"), Syntax.literal("c")
    syntax = A // B // C
    sql = "a b c"
    ast, bound = parse_word(syntax, sql, cache=Cache())
    print("---" * 40)
    print(ast)
    generated, bound = gen.generate_with(syntax, ast)
    print("---" * 40)
    print(generated)
    assert ast == generated
    value, bmap = generated.bimap
    # print(value)
    u, v = gen.generate_with(syntax, bmap(value))
    assert u == generated


def test_parse_bytes_input_with_lexer_bind() -> None:
    syntax_cls = Syntax.config(alphabet=Alphabet(bytes))
    byte_token = syntax_cls.lex(BYTE=Builder.lit(b"\x01"))

    value, state = parser_run(syntax=byte_token, data=StreamCursor.from_data(b"\x01"), cache=None)

    assert isinstance(value, Token)
    assert value.token_type == "BYTE"
    assert isinstance(value.text, bytes)
    assert value.text == b"\x01"
    assert state is not None
    assert state.ended

if __name__ == "__main__":
    # rep()
    benchmark_fair()
    # test1_simple_then()

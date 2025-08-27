from __future__ import annotations

from typing import (
    Any, Tuple, Generator as YieldGen
)
from dataclasses import dataclass
from syncraft.algebra import (
    Algebra, Either, Right, 
)
from syncraft.ast import T, ParseResult, Choice, Many, Then, Marked

from syncraft.generator import GenState, Generator

from syncraft.syntax import Syntax



@dataclass(frozen=True)
class Finder(Generator[T]):
    @classmethod
    def anything(cls)->Algebra[Any, GenState[T]]:
        def anything_run(input: GenState[T], use_cache:bool) -> Either[Any, Tuple[Any, GenState[T]]]:
            return Right((input.ast, input))
        return cls(anything_run, name=cls.__name__ + '.anything()')



anything = Syntax(lambda cls: cls.factory('anything')).describe(name="anything", fixity='infix') 

def matches(syntax: Syntax[Any, Any], data: ParseResult[T])-> bool:
    gen = syntax(Finder)
    state = GenState.from_ast(ast = data, restore_pruned=True)
    result = gen.run(state, use_cache=True)
    return isinstance(result, Right)


def find(syntax: Syntax[Any, Any], data: ParseResult[T]) -> YieldGen[ParseResult[T], None, None]:
    if matches(syntax, data):
        yield data
    match data:
        case Then(left=left, right=right):
            if left is not None:
                yield from find(syntax, left)
            if right is not None:
                yield from find(syntax, right)
        case Many(value = value):
            for e in value:
                yield from find(syntax, e)
        case Marked(value=value):
            yield from find(syntax, value)
        case Choice(left=left, right=right):
            if left is not None:
                yield from find(syntax, left)
            if right is not None:
                yield from find(syntax, right)
        case _:
            pass

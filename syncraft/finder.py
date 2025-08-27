from __future__ import annotations

from typing import (
    Any, Tuple, Optional, Generator as YieldGen
)
from dataclasses import dataclass, replace
from syncraft.algebra import (
    Algebra, Either, Right, 
)
from syncraft.ast import T, ParseResult, Choice, Many, Then, Marked

from syncraft.generator import GenState, Generator
from sqlglot import TokenType
from syncraft.syntax import Syntax
import re


@dataclass(frozen=True)
class Finder(Generator[T]):      
    def many(self, *, at_least: int, at_most: Optional[int]) -> Algebra[Many[ParseResult[T]], GenState[T]]:
        assert at_least > 0, "at_least must be greater than 0"
        assert at_most is None or at_least <= at_most, "at_least must be less than or equal to at_most"
        return self.map_state(lambda s: replace(s, restore_pruned = True)).many(at_least=at_least, at_most=at_most)
    
 
    def or_else(self, # type: ignore
                other: Algebra[ParseResult[T], GenState[T]]
                ) -> Algebra[Choice[ParseResult[T]], GenState[T]]: 
        return self.map_state(lambda s: replace(s, restore_pruned = True)).or_else(other) 
        

    @classmethod
    def token(cls, 
              token_type: Optional[TokenType] = None, 
              text: Optional[str] = None, 
              case_sensitive: bool = False,
              regex: Optional[re.Pattern[str]] = None
              )-> Algebra[ParseResult[T], GenState[T]]: 
        return super().token(token_type=token_type, 
                               text=text, 
                               case_sensitive=case_sensitive, 
                               regex=regex).map_state(lambda s: replace(s, restore_pruned = True)) # type: ignore


    @classmethod
    def anything(cls)->Algebra[Any, GenState[T]]:
        def anything_run(input: GenState[T], use_cache:bool) -> Either[Any, Tuple[Any, GenState[T]]]:
            return Right((input.ast, input))
        return cls(anything_run, name=cls.__name__ + '.anything()')



anything = Syntax(lambda cls: cls.factory('anything')).describe(name="anything", fixity='infix') 

def matches(syntax: Syntax[Any, Any], data: ParseResult[T])-> bool:
    gen = syntax(Finder)
    state = GenState.from_ast(ast = data)
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

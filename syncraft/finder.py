from __future__ import annotations

from typing import (
    Any, Tuple, Optional, Generator as YieldGen
)
from dataclasses import dataclass, replace
from syncraft.algebra import (
    Algebra, Either, Right, 
    OrResult, ManyResult, ThenResult, MarkedResult
)

from syncraft.ast import T, ParseResult, AST
from syncraft.generator import GenState, Generator
from sqlglot import TokenType
from syncraft.syntax import Syntax
import re


@dataclass(frozen=True)
class Finder(Generator[T]):      
    def many(self, *, at_least: int, at_most: Optional[int]) -> Algebra[ManyResult[ParseResult[T]], GenState[T]]:
        assert at_least > 0, "at_least must be greater than 0"
        assert at_most is None or at_least <= at_most, "at_least must be less than or equal to at_most"
        return self.map_state(lambda s: replace(s, is_pruned = False)).many(at_least=at_least, at_most=at_most)
    
 
    def or_else(self, # type: ignore
                other: Algebra[ParseResult[T], GenState[T]]
                ) -> Algebra[OrResult[ParseResult[T]], GenState[T]]: 
        return self.map_state(lambda s: replace(s, is_pruned = False)).or_else(other) 
        

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
                               regex=regex).map_state(lambda s: replace(s, is_pruned = False)) # type: ignore


    @classmethod
    def anything(cls)->Algebra[ParseResult[T], GenState[T]]:
        def anything_run(input: GenState[T], use_cache:bool) -> Either[Any, Tuple[ParseResult[T], GenState[T]]]:
            wrapper = input.wrapper()
            return Right((wrapper(input.focus), input))
        return cls(anything_run, name=cls.__name__ + '.anything()')



anything = Syntax(lambda cls: cls.factory('anything')).describe(name="anything", fixity='infix') 

def matches(syntax: Syntax[Any, Any], data: AST[Any])-> bool:
    gen = syntax(Finder)
    state = GenState.from_ast(data)
    result = gen.run(state, use_cache=True)
    return isinstance(result, Right)


def find(syntax: Syntax[Any, Any], data: AST[Any]) -> YieldGen[AST[Any], None, None]:
    if matches(syntax, data):
        yield data
    match data.focus:
        case ThenResult(left = left, right=right):
            yield from find(syntax, AST(left))
            yield from find(syntax, AST(right))
        case ManyResult(value = value):
            for e in value:
                yield from find(syntax, AST(e))
        case MarkedResult(value=value):
            yield from find(syntax, AST(value))
        case OrResult(value=value):
            yield from find(syntax, AST(value))
        case _:
            pass

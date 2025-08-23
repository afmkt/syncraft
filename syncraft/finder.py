from __future__ import annotations

from typing import (
    Any, Tuple, Optional,  Callable,
    List, Generator as YieldGen
)
from dataclasses import dataclass
from syncraft.algebra import (
    Algebra, Either, Left, Right, Error, 
    OrResult, ManyResult
)

from syncraft.ast import T, ParseResult, Token
from syncraft.generator import GenState, TokenGen, B
from sqlglot import TokenType
import re

@dataclass(frozen=True)
class Generator(Algebra[ParseResult[T], GenState[T]]):  
    def flat_map(self, f: Callable[[ParseResult[T]], Algebra[B, GenState[T]]]) -> Algebra[B, GenState[T]]: 
        def flat_map_run(original: GenState[T], use_cache:bool) -> Either[Any, Tuple[B, GenState[T]]]:
            wrapper = original.wrapper()
            input = original if not original.is_named else original.down(0)  # If the input is named, we need to go down to the first child
            try:
                lft = input.left() 
                match self.run(lft, use_cache=use_cache):
                    case Left(error):
                        return Left(error)
                    case Right((value, next_input)):
                        r = input.right() 
                        match f(value).run(r, use_cache):
                            case Left(e):
                                return Left(e)
                            case Right((result, next_input)):
                                return Right((wrapper(result), next_input))
                raise ValueError("flat_map should always return a value or an error.")
            except Exception as e:
                return Left(Error(
                    message=str(e),
                    this=self,
                    state=original,
                    error=e
                ))
        return Generator(run_f = flat_map_run, name=self.name) # type: ignore


    def many(self, *, at_least: int, at_most: Optional[int]) -> Algebra[ManyResult[ParseResult[T]], GenState[T]]:
        assert at_least > 0, "at_least must be greater than 0"
        assert at_most is None or at_least <= at_most, "at_least must be less than or equal to at_most"
        def many_run(input: GenState[T], use_cache:bool) -> Either[Any, Tuple[ManyResult[ParseResult[T]], GenState[T]]]:
            wrapper = input.wrapper()
            input = input if not input.is_named else input.down(0)  # If the input is named, we need to go down to the first child
            if input.pruned:
                upper = at_most if at_most is not None else at_least + 2
                count = input.rng("many").randint(at_least, upper)
                ret: List[Any] = []
                for i in range(count):
                    forked_input = input.down(0).fork(tag=len(ret))
                    match self.run(forked_input, use_cache):
                        case Right((value, next_input)):
                            ret.append(value)
                        case Left(_):
                            pass
                return Right((wrapper(ManyResult(tuple(ret))), input))
            else:
                ret = []
                for index in range(input.how_many): 
                    match self.run(input.down(index), use_cache):
                        case Right((value, next_input)):
                            ret.append(value)
                            if at_most is not None and len(ret) > at_most:
                                return Left(Error(
                                        message=f"Expected at most {at_most} matches, got {len(ret)}",
                                        this=self,
                                        state=input.down(index)
                                    ))                             
                        case Left(_):
                            pass
                if len(ret) < at_least:
                    return Left(Error(
                        message=f"Expected at least {at_least} matches, got {len(ret)}",
                        this=self,
                        state=input.down(index)
                    )) 
                return Right((wrapper(ManyResult(tuple(ret))), input))
        return self.__class__(many_run, name=f"many({self.name})")  # type: ignore
    
 
    def or_else(self, # type: ignore
                other: Algebra[ParseResult[T], GenState[T]]
                ) -> Algebra[OrResult[ParseResult[T]], GenState[T]]: 
        def or_else_run(input: GenState[T], use_cache:bool) -> Either[Any, Tuple[OrResult[ParseResult[T]], GenState[T]]]:
            wrapper = input.wrapper()
            input = input if not input.is_named else input.down(0)  # If the input is named, we need to go down to the first child
            if input.pruned:
                forked_input = input.fork(tag="or_else")
                match forked_input.rng("or_else").choice((self, other)).run(forked_input, use_cache):
                    case Right((value, next_input)):
                        return Right((wrapper(OrResult(value)), next_input))
                    case Left(error):
                        return Left(error)
            else:
                match self.run(input.down(0), use_cache):
                    case Right((value, next_input)):
                        return Right((wrapper(OrResult(value)), next_input))
                    case Left(error):
                        match other.run(input.down(0), use_cache):
                            case Right((value, next_input)):
                                return Right((wrapper(OrResult(value)), next_input))
                            case Left(error):
                                return Left(error)
            raise ValueError("or_else should always return a value or an error.")
        return self.__class__(or_else_run, name=f"or_else({self.name} | {other.name})") # type: ignore

    @classmethod
    def token(cls, 
              token_type: Optional[TokenType] = None, 
              text: Optional[str] = None, 
              case_sensitive: bool = False,
              regex: Optional[re.Pattern[str]] = None
              )-> Algebra[ParseResult[T], GenState[T]]:      
        gen = TokenGen(token_type=token_type, text=text, case_sensitive=case_sensitive, regex=regex)  
        lazy_self: Algebra[ParseResult[T], GenState[T]]
        def token_run(input: GenState[T], use_cache:bool) -> Either[Any, Tuple[ParseResult[Token], GenState[T]]]:
            wrapper = input.wrapper()
            input = input if not input.is_named else input.down(0)  # If the input is named, we need to go down to the first child
            if input.pruned:
                return Right((gen.gen(), input))
            else:
                current = input.focus
                if not isinstance(current, Token) or not gen.is_valid(current):
                    return Left(Error(None, 
                                      message=f"Expected a Token, but got {type(current)}.", 
                                      state=input))
                return Right((wrapper(current), input))
        lazy_self = cls(token_run, name=cls.__name__ + f'.token({token_type or text or regex})')  # type: ignore
        return lazy_self

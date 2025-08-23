from __future__ import annotations

from typing import (
    Any, TypeVar, Tuple, Optional,  Callable, Generic, 
    List, 
)
from functools import cached_property
from dataclasses import dataclass, replace
from syncraft.algebra import (
    Algebra, Either, Left, Right, Error, 
    OrResult, ManyResult
)

from syncraft.ast import T, ParseResult, AST, Token, TokenSpec
from syncraft.syntax import Syntax
from sqlglot import TokenType
import re
import rstr
from functools import lru_cache
import random

B = TypeVar('B')


@dataclass(frozen=True)
class GenState(Generic[T]):
    ast: Optional[AST[T]]
    seed: int

    def fork(self, tag: Any) -> GenState[T]:
        return replace(self, seed=hash((self.seed, tag)))

    def rng(self, tag: Any = None) -> random.Random:
        return random.Random(self.seed if tag is None else hash((self.seed, tag)))

    def to_string(self, interested: Callable[[Any], bool]) -> str | None:
        return f"GenState(current={self.focus})"

    @cached_property
    def pruned(self)->bool:
        return self.ast is None or self.ast.pruned
    

    @property
    def focus(self) -> Optional[ParseResult[T]]:
        if self.ast is None:
            return None
        return self.ast.focus

    @property
    def is_named(self)->bool:
        return self.ast is not None and self.ast.is_named()
    
    def wrapper(self)->Callable[[Any], Any]:
        if self.ast is not None:
            return self.ast.wrapper()
        else:
            return lambda x: x

    def left(self)-> GenState[T]:
        if self.ast is None:
            return self
        return replace(self, ast=self.ast.left())

    def right(self) -> GenState[T]:
        if self.ast is None:
            return self
        return replace(self, ast=self.ast.right())
    

    
    def down(self, index: int) -> GenState[T]:
        if self.ast is None:
            return self
        return replace(self, ast=self.ast.down(index))
    
    @cached_property
    def how_many(self) -> int:
        if self.ast is None:
            return 0
        return self.ast.how_many()

    @classmethod
    def from_ast(cls, ast: Optional[AST[T]], seed: int = 0) -> GenState[T]:
        return cls(ast=ast, seed=seed)


    @classmethod
    def from_parse_result(cls, parse_result: Optional[ParseResult[T]], seed: int = 0) -> GenState[T]:
        return cls.from_ast(AST(parse_result) if parse_result else None, seed)





@lru_cache(maxsize=None)
def token_type_from_string(token_type: Optional[TokenType], text: str, case_sensitive:bool)-> TokenType:
    if not isinstance(token_type, TokenType) or token_type == TokenType.VAR:
        for t in TokenType:
            if t.value == text or str(t.value).lower() == text.lower():
                return t
        return TokenType.VAR
    return token_type


@dataclass(frozen=True)
class TokenGen(TokenSpec):

    def __str__(self) -> str:
        tt = self.token_type.name if self.token_type else ""
        txt = self.text if self.text else ""
        reg = self.regex.pattern if self.regex else ""
        return f"TokenGen({tt}, {txt}, {self.case_sensitive}, {reg})"
        
    
    def __repr__(self) -> str:
        return self.__str__()

    def gen(self) -> Token:
        text: str
        if self.text is not None:
            text = self.text
        elif self.regex is not None:
            try:
                text = rstr.xeger(self.regex)
            except Exception as e:
                # If the regex is invalid or generation fails
                text = self.regex.pattern  # fallback to pattern string
        elif self.token_type is not None:
            text = str(self.token_type.value)
        else:
            text = "VALUE"

        return Token(token_type= token_type_from_string(self.token_type,
                                                        text, 
                                                        self.case_sensitive), 
                     text=text)        

    @staticmethod
    def from_string(string: str)->Token:
        return Token(token_type=token_type_from_string(None, string, case_sensitive=False), text=string)


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



def generate(syntax: Syntax[Any, Any], data: Optional[AST[Any]] = None, seed: int = 0) -> AST[Any] | Any:
    gen = syntax(Generator)
    state = GenState.from_ast(data, seed)
    result = gen.run(state, use_cache=False)
    if isinstance(result, Right):
        return AST(result.value[0])
    assert isinstance(result, Left), "Generator must return Either[Any, Tuple[Any, Any]]"
    return result.value


    
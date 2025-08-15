from __future__ import annotations

from typing import (
    Any, TypeVar, Tuple, Optional,  Callable, Generic, Union, Iterable, Hashable, 
    cast, List
)

from dataclasses import dataclass, replace
from syncraft.algebra import (
    Algebra, ThenResult, Either, Left, Right, Error, Insptectable, 
    NamedResult, OrResult, ManyResult
)
from syncraft.parser import TokenProtocol, ParseResult, AST, Token, TokenSpec, Crumb
from sqlglot import TokenType
import re
from rich import print
import rstr
from functools import lru_cache
import random


A = TypeVar('A')
B = TypeVar('B')
T = TypeVar('T', bound=TokenProtocol)  

GenResult = Union[
    ThenResult['GenResult[T]', 'GenResult[T]'], 
    ManyResult['GenResult[T]'],
    OrResult['GenResult[T]'],
    Iterable[T],
    T
]




E = TypeVar('E', bound=Hashable)
F = TypeVar('F', bound=Hashable)

@dataclass(frozen=True)
class GenState(Generic[T], Insptectable):
    ast: Optional[AST[T]]
    seed: int

    def fork(self, tag: Any) -> GenState[T]:
        return replace(self, seed=hash((self.seed, tag)))

    def rng(self, tag: Any = None) -> random.Random:
        return random.Random(self.seed if tag is None else hash((self.seed, tag)))

    def to_string(self, interested: Callable[[Any], bool]) -> str | None:
        return f"GenState(current={self.focus})"

    @property
    def is_freeform(self) -> bool:
        if self.ast is None:
            return True
        return self.ast.is_pruned
    
    @property
    def ended(self) -> bool:
        return self.ast is None
    

    @property
    def focus(self) -> Optional[ParseResult[T]]:
        if self.ast is None:
            return None
        return self.ast.focus
    

    def leftmost(self)-> GenState[T]:
        if self.ast is None:
            return self
        return replace(self, ast=self.ast.leftmost)

    def down_left(self) -> GenState[T]:
        if self.ast is None:
            return self
        return replace(self, ast=self.ast.down_left())
        
    def right(self) -> GenState[T]:
        if self.ast is None:
            return self    
        return replace(self, ast=self.ast.right())

    def advance(self, filter: Callable[[Any], bool]) -> GenState[T]:
        if self.ast is None:
            return self        
        def filtered(z: GenState[T]) -> GenState[T]:
            return z if z.ast is None or filter(z.ast.focus) else z.advance(filter=filter)
        z = self.down_left()
        if z.ast is not None:
            return filtered(z)
        z = self.right()
        if z.ast is not None:
            return filtered(z)
        
        zs = self.ast
        while tmp_z := zs.up():
            if next_z := tmp_z.right():
                return filtered(replace(self, ast=next_z))
            zs = tmp_z
        return filtered(replace(self, ast=None))

        
        
    @staticmethod
    def only_terminal(node: Any) -> bool:
        return not isinstance(node, (ManyResult, ThenResult, NamedResult, OrResult))
    
    def copy(self) -> GenState[T]:
        return self.__class__(ast=self.ast, seed=self.seed)

    def delta(self, new_state: GenState[T]) -> Tuple[T, ...]:
        return tuple()

    def scoped(self) -> GenState[T]:
        return ScopedState(ast=self.ast, 
                           seed=self.seed,
                           scope=self.ast.breadcrumbs[-1] if self.ast and self.ast.breadcrumbs else None)

    def freeform(self) -> GenState[T]:
        return FreeformState(ast=None, seed=self.seed)
    
    @classmethod
    def from_ast(cls, ast: Optional[AST[T]], seed: int = 0) -> GenState[T]:
        return cls(ast=ast, seed=seed)

    @classmethod
    def from_parse_result(cls, parse_result: Optional[ParseResult[T]], seed: int = 0) -> GenState[T]:
        ret = cls(ast=AST(parse_result) if parse_result else None, seed=seed)
        return ret if parse_result is not None else ret.freeform()
    



@dataclass(frozen=True)
class ScopedState(GenState[T]):
    scope: None | Crumb[T]
    @property
    def ended(self) -> bool:
        return self.ast is None or self.scope in self.ast.closed
    
    def right(self)-> GenState[T]:
        ret: ScopedState[T] = cast(ScopedState[T], super().right())
        if ret.ast is not None and self.scope is not None:
            if self.scope not in ret.ast.closed and self.scope not in ret.ast.breadcrumbs:
                return replace(ret, scope=ret.ast.breadcrumbs[-1] if ret.ast.breadcrumbs else None)
        return ret
            

@dataclass(frozen=True)
class FreeformState(GenState[T]):
    @property
    def ended(self) -> bool:
        return False

    def scoped(self) -> GenState[T]:
        return self

    def advance(self, filter: Callable[[Any], bool]) -> GenState[T]:
        return self


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




@dataclass(frozen=True)
class Generator(Algebra[GenResult[T], GenState[T]]):  
    def flat_map(self, f: Callable[[GenResult[T]], Algebra[B, GenState[T]]]) -> Algebra[B, GenState[T]]: 
        def flat_map_run(input: GenState[T], use_cache:bool) -> Either[Any, Tuple[B, GenState[T]]]:
            left = input.down_left()
            s = left.scoped()
            match self.run(s, use_cache=use_cache):
                case Left(error):
                    return Left(error)
                case Right((value, next_input)):
                    return f(value).run(left.right(), use_cache)
            raise ValueError("flat_map should always return a value or an error.")
        return Generator(run_f = flat_map_run, name=self.name) # type: ignore  

    def gen(self, 
            freeform: Algebra[Any, GenState[T]], 
            default: Algebra[Any, GenState[T]]
            ) -> Algebra[Any, GenState[T]]:
        def gen_run(input: GenState[T], use_cache:bool) -> Either[Any, Tuple[Any, GenState[T]]]:
            if input.ended:
                return Left(Error(this=self, 
                                  message=f"{input.__class__.__name__} has ended, cannot run many.",
                                  state=input))
            elif input.is_freeform:            
                return freeform.run(input, use_cache)
            else:
                return default.run(input, use_cache)
        return self.__class__(gen_run, name=default.name) 

    def gen_many(self, 
                 at_least: int, 
                 at_most: Optional[int] = None
                 ) -> Algebra[ManyResult[GenResult[T]], GenState[T]]: 
        def gen_many_run(input: GenState[T], 
                         use_cache:bool
                         ) -> Either[Any, Tuple[ManyResult[GenResult[T]], GenState[T]]]:
            upper = at_most if at_most is not None else at_least + 2
            count = input.rng("many").randint(at_least, upper)
            ret: List[Any] = []
            current_input: GenState[T] = input.freeform()
            for _ in range(count):
                forked_input = current_input.fork(tag=len(ret))
                match self.run(forked_input, use_cache):
                    case Right((value, next_input)):
                        current_input = next_input
                        ret.append(value)
                    case Left(_):
                        break
            return Right((ManyResult(tuple(ret)), input))
        return self.__class__(run_f=gen_many_run, name=f"free_many({self.name})")  # type: ignore
        

    def many(self, *, at_least: int, at_most: Optional[int]) -> Algebra[ManyResult[GenResult[T]], GenState[T]]:
        assert at_least > 0, "at_least must be greater than 0"
        assert at_most is None or at_least <= at_most, "at_least must be less than or equal to at_most"
        return self.gen(freeform=self.gen_many(at_least, at_most), 
                        default=super().many(at_least=at_least, at_most=at_most)) 
    
    def gen_or_else(self, 
                 other: Algebra[GenResult[T], GenState[T]]) -> Algebra[OrResult[GenResult[T]], GenState[T]]:
        def gen_or_else_run(input: GenState[T], 
                            use_cache:bool
                            )->Either[Any, Tuple[OrResult[GenResult[T]], GenState[T]]]:
            forked_input = input.fork(tag="or_else")
            match forked_input.rng("or_else").choice((self, other)).run(forked_input.freeform(), use_cache):
                case Right((value, next_input)):
                    return Right((OrResult(value), next_input))
                case Left(error):
                    return Left(error)
            raise TypeError(f"Unexpected result type from {self}")
        return self.__class__(gen_or_else_run, name=f"free_or({self.name} | {other.name})") # type: ignore
 

    def or_else(self, # type: ignore
                other: Algebra[GenResult[T], GenState[T]]
                ) -> Algebra[OrResult[GenResult[T]], GenState[T]]: 
        return self.gen(freeform=self.gen_or_else(other), 
                        default=super().or_else(other))  


    @classmethod
    def token(cls, 
              token_type: Optional[TokenType] = None, 
              text: Optional[str] = None, 
              case_sensitive: bool = False,
              regex: Optional[re.Pattern[str]] = None
              )-> Algebra[GenResult[T], GenState[T]]:      
        gen = TokenGen(token_type=token_type, text=text, case_sensitive=case_sensitive, regex=regex)  
        lazy_self: Algebra[GenResult[T], GenState[T]]
        def token_run(input: GenState[T], use_cache:bool) -> Either[Any, Tuple[GenResult[Token], GenState[T]]]:
            print('token', gen, input)
            if input.ended:
                return Left(Error(None,
                                  message=f"{input.__class__.__name__} has ended, cannot run token.", 
                                  state=input))
            elif input.is_freeform:
                return Right((gen.gen(), input.advance(GenState.only_terminal)))  
            else:
                input = input.leftmost()
                current = input.focus
                if not isinstance(current, Token) or not gen.is_valid(current):
                    return Left(Error(None, 
                                      message=f"Expected a Token, but got {type(current)}.", 
                                      state=input))
                return Right((current, input.advance(GenState.only_terminal)))
        lazy_self = cls(token_run, name=cls.__name__ + f'.token({token_type or text or regex})')  # type: ignore
        return lazy_self



def generate(gen: Algebra[Any, Any], data: Optional[AST[Any]] = None, seed: int = 0) -> AST[Any] | Any:
    state = GenState.from_ast(data, seed)
    result = gen.run(state, use_cache=False)
    if isinstance(result, Right):
        return AST(result.value[0])
    assert isinstance(result, Left), "Parser must return Either[E, Tuple[A, S]]"
    return result.value


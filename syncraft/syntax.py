from __future__ import annotations

from typing import (
    Optional, List, Any, TypeVar, Generic, Callable, Tuple, cast,
    Type, Literal
)
from dataclasses import dataclass, field, replace
from functools import reduce
from syncraft.algebra import Algebra, Error, Either, ThenResult, ManyResult, ThenKind, NamedResult
from types import MethodType, FunctionType




A = TypeVar('A')  # Result type
B = TypeVar('B')  # Result type for mapping
C = TypeVar('C')  # Result type for else branch
S = TypeVar('S')  # State type


class Variable(Generic[A]):
    def __init__(self, name: Optional[str] = None):
        self.name = name
        self.initialized = False
        self._value = None
    def __call__(self, a: Any) -> Any:
        if self.initialized:
            if self._value != a:
                raise ValueError(f"Variable {self.name or ''} is already initialized")
            else:
                return a
        elif self.name is not None and isinstance(a, NamedResult):
            if a.name == self.name:
                self._value = a.value
                self.initialized = True
        else:
            self._value = a
            self.initialized = True
        return a
    @property
    def value(self) -> A:
        if self.initialized is False or self._value is None:
            raise ValueError(f"Variable {self.name or ''} is not initialized")
        return self._value


@dataclass(frozen=True)
class Description:
    name: Optional[str] = None
    newline: Optional[str] = None
    fixity: Literal['infix', 'prefix', 'postfix'] = 'infix'
    parameter: List[Any] = field(default_factory=list)

    def update(self, 
               *,
               newline: Optional[str] = None,
               name: Optional[str] = None,
               fixity: Optional[Literal['infix', 'prefix', 'postfix']] = None,
               parameter: Optional[List[Any]] = None) -> 'Description':
        return Description(
            name=name if name is not None else self.name,
            newline= newline if newline is not None else self.newline,
            fixity=fixity if fixity is not None else self.fixity,
            parameter=parameter if parameter is not None else self.parameter
        )
        
    def to_string(self, interested: Callable[[Any], bool]) -> Optional[str]:
        if self.name is not None:
            if self.fixity == 'infix':
                assert len(self.parameter) == 2, "Expected exactly two parameters for infix operator"
                left  = self.parameter[0].to_string(interested) if interested(self.parameter[0]) else '...'
                right = self.parameter[1].to_string(interested) if interested(self.parameter[1]) else '...'
                if self.parameter[1].meta.newline is not None:
                    dot = '\u25cf'  
                    rarrow = '\u2794'
                    new = '\u2570' #'\u2936'
                    return f"{left}\n{new} \"{self.parameter[1].meta.newline}\" {self.name} {right}"
                return f"{left} {self.name} {right}"
            elif self.fixity == 'prefix':
                if len(self.parameter) == 0:
                    return self.name
                tmp = [x.to_string(interested) if interested(x) else '...' for x in self.parameter]
                return f"{self.name}({','.join(str(x) for x in tmp)})" 
            elif self.fixity == 'postfix':
                if len(self.parameter) == 0:
                    return self.name
                tmp = [x.to_string(interested) if interested(x) else '...' for x in self.parameter]
                return f"({','.join(str(x) for x in tmp)}).{self.name}" 
            else:
                return f"Invalid fixity: {self.fixity}"
        return None




@dataclass(frozen=True)
class Syntax(Generic[A, S]):
    alg: Callable[[Type[Algebra[Any, Any]]], Algebra[A, S]]
    meta: Description = field(default_factory=Description, repr=False)

    def algebra(self, name: str | MethodType | FunctionType, *args: Any, **kwargs: Any)-> Syntax[A, S]:
        def algebra_run(cls: Type[Algebra[Any, S]]) -> Algebra[Any, S]:
            a = self.alg(cls)
            if isinstance(name, str):
                attr = getattr(a, name, None) or getattr(cls, name, None)
                if attr is None:
                    return a
                if isinstance(attr, (staticmethod, classmethod)):
                    # These are descriptors: unwrap then call
                    attr = attr.__get__(None, cls)
                elif isinstance(attr, FunctionType):
                    # Unbound function (e.g., static method not wrapped)
                    attr = MethodType(attr, a)
                else:
                    return a
                return cast(Algebra[Any, S], attr(*args, **kwargs))
            elif isinstance(name, MethodType):
                f = MethodType(name.__func__, a)
                return cast(Algebra[Any, S], f(*args, **kwargs))
            elif isinstance(name, FunctionType):
                f = MethodType(name, a)
                return cast(Algebra[Any, S], f(*args, **kwargs))
            else:
                return a
        return self.__class__(alg=algebra_run, meta=self.meta)
                

    def as_(self, typ: Type[B])->B:
        return cast(typ, self) # type: ignore
        
    def __call__(self, alg: Type[Algebra[Any, Any]]) -> Algebra[A, S]:
        return self.alg(alg)
    
    def to_string(self, interested: Callable[[Any], bool]) -> Optional[str]:
        return self.meta.to_string(interested)

        
    def describe(self, 
                 *, 
                 newline: Optional[str] = None,
                 name: Optional[str] = None, 
                 fixity: Optional[Literal['infix', 'prefix', 'postfix']] = None, 
                 parameter: Optional[List[Syntax[Any, S]]] = None) -> Syntax[A, S]:
        return self.__class__(alg=self.alg,
                              meta=self.meta.update(name=name,
                                    newline=newline,
                                    fixity=fixity,
                                    parameter=parameter))
    
    def newline(self, info: str='')-> Syntax[A, S]:
        return self.describe(newline=info)

    def terminal(self, name: str)->Syntax[A, S]:
        return self.describe(name=name, fixity='prefix', parameter=[])

######################################################## value transformation ########################################################
    def map(self, f: Callable[[A], B]) -> Syntax[B, S]:
        return self.__class__(lambda cls: self.alg(cls).map(f), meta = self.meta) # type: ignore

    def map_error(self, f: Callable[[Optional[Any]], Any]) -> Syntax[A, S]:
        return self.__class__(lambda cls: self.alg(cls).map_error(f), meta=self.meta)
    
    def map_state(self, f: Callable[[S], S]) -> Syntax[A, S]:
        return self.__class__(lambda cls: self.alg(cls).map_state(f), meta=self.meta)

    def flat_map(self, f: Callable[[A], Algebra[B, S]]) -> Syntax[B, S]:
        return self.__class__(lambda cls: self.alg(cls).flat_map(f)) # type: ignore

    def many(self, *, at_least: int = 1, at_most: Optional[int] = None) -> Syntax[ManyResult[A], S]:
        return self.__class__(lambda cls:self.alg(cls).many(at_least=at_least, at_most=at_most)).describe(name='*', # type: ignore
                                                 fixity='prefix', 
                                                 parameter=[self])  
    
################################################ facility combinators ############################################################



    def between(self, left: Syntax[Any, S], right: Syntax[Any, S]) -> Syntax[ThenResult[None, ThenResult[A, None]], S]:
        return left >> self // right

    def sep_by(self, sep: Syntax[Any, S]) -> Syntax[ThenResult[A, ManyResult[ThenResult[None, A]]], S]:
        return (self + (sep >> self).many()).describe(
            name='sep_by',
            fixity='prefix',
            parameter=[self, sep]
        )
    
    def parens(self, sep: Syntax[Any, S], open: Syntax[Any, S], close: Syntax[Any, S]) -> Syntax[Any, S]:
        return self.sep_by(sep=sep).between(left=open, right=close)
            
    def optional(self, default: Optional[B] = None) -> Syntax[Optional[A | B], S]:
        return (self | success(default)).describe(name='~', fixity='prefix', parameter=[self])


    def cut(self) -> Syntax[A, S]:
        return self.__class__(lambda cls:self.alg(cls).cut())


####################################################### operator overloading #############################################
    def __ge__(self, f: Callable[[A], Algebra[B, S]]) -> Syntax[B, S]:
        return self.flat_map(f).describe(name='>=', fixity='infix', parameter=[self])


    def __gt__(self, other: Callable[[A], B])->Syntax[B, S]:
        return self.map(other)


    def __floordiv__(self, other: Syntax[B, S]) -> Syntax[ThenResult[A, None], S]:
        other = other if isinstance(other, Syntax) else self.lift(other).as_(Syntax[B, S])
        return self.__class__(
            lambda cls: self.alg(cls).then_left(other.alg(cls))   # type: ignore
            ).describe(name=ThenKind.LEFT.value, fixity='infix', parameter=[self, other]).as_(Syntax[ThenResult[A, None], S]) 

    def __rfloordiv__(self, other: Syntax[B, S]) -> Syntax[ThenResult[B, None], S]:
        other = other if isinstance(other, Syntax) else self.lift(other).as_(Syntax[B, S])
        return other.__floordiv__(self)

    def __invert__(self) -> Syntax[A | None, S]:
        return self.optional()

    def __radd__(self, other: Syntax[B, S]) -> Syntax[ThenResult[B, A], S]:
        other = other if isinstance(other, Syntax) else self.lift(other).as_(Syntax[B, S])
        return other.__add__(self)

    def __add__(self, other: Syntax[B, S]) -> Syntax[ThenResult[A, B], S]:
        other = other if isinstance(other, Syntax) else self.lift(other).as_(Syntax[B, S])
        return self.__class__( 
            lambda cls: self.alg(cls).then_both(other.alg(cls)) # type: ignore
            ).describe(name=ThenKind.BOTH.value, fixity='infix', parameter=[self, other])

    def __rshift__(self, other: Syntax[B, S]) -> Syntax[ThenResult[None, B], S]:
        other = other if isinstance(other, Syntax) else self.lift(other).as_(Syntax[B, S])
        return self.__class__(
            lambda cls: self.alg(cls).then_right(other.alg(cls))   # type: ignore
            ).describe(name=ThenKind.RIGHT.value, fixity='infix', parameter=[self, other]).as_(Syntax[ThenResult[None, B], S])   


    def __rrshift__(self, other: Syntax[B, S]) -> Syntax[ThenResult[None, A], S]:
        other = other if isinstance(other, Syntax) else self.lift(other).as_(Syntax[B, S])
        return other.__rshift__(self)  


    def __or__(self, other: Syntax[B, S]) -> Syntax[A | B, S]:
        other = other if isinstance(other, Syntax) else self.lift(other).as_(Syntax[B, S])
        return self.__class__(lambda cls: self.alg(cls).or_else(other.alg(cls))).describe(name='|', fixity='infix', parameter=[self, other]) # type: ignore


    def __ror__(self, other: Syntax[B, S]) -> Syntax[A | B, S]:
        other = other if isinstance(other, Syntax) else self.lift(other).as_(Syntax[B, S])
        return other.__or__(self).as_(Syntax[A | B, S]) 


######################################################################## data processing combinators #########################################################
    def bind(self, name: str) -> Syntax[NamedResult[A], S]:
        def bind_f(value: A) -> NamedResult[A]:
            if isinstance(value, NamedResult):
                return replace(value, name=name)    
            else:
                return NamedResult(name=name, value=value)
        return self.map(bind_f).describe(name=f'bind("{name}")', fixity='postfix', parameter=[self]) 

    def assign(self, var: Variable[A]) -> Syntax[A, S]:
        return self.map(var).describe(name=f'assign({var.name or ""})', fixity='postfix', parameter=[self])

    def dump_error(self, formatter: Optional[Callable[[Error], None]] = None) -> Syntax[A, S]:
        def dump_error_run(err: Any)->Any:
            if isinstance(err, Error) and formatter is not None:
                formatter(err) 
            return err
        return self.__class__(lambda cls: self.alg(cls).map_error(dump_error_run))


    def debug(self, 
              label: str, 
              formatter: Optional[Callable[[Algebra[Any, S], S, Either[Any, Tuple[Any, S]]], None]] = None) -> Syntax[A, S]:
        return self.__class__(lambda cls:self.alg(cls).debug(label, formatter), meta=self.meta)


    
def lazy(thunk: Callable[[], Syntax[A, S]]) -> Syntax[A, S]:
    return Syntax(lambda cls: cls.lazy(lambda: thunk()(cls))).describe(name='lazy(?)', fixity='postfix') 

def fail(error: Any) -> Syntax[Any, Any]:
    return Syntax(lambda alg: alg.fail(error)).describe(name=f'fail({error})', fixity='prefix')

def success(value: Any) -> Syntax[Any, Any]:
    return Syntax(lambda alg: alg.success(value)).describe(name=f'success({value})', fixity='prefix')

def choice(*parsers: Syntax[Any, S]) -> Syntax[Any, S]:
    return reduce(lambda a, b: a | b, parsers) if len(parsers) > 0 else success(None)


def all(*parsers: Syntax[Any, S]) -> Syntax[ThenResult[Any, Any], S]:
    return reduce(lambda a, b: a + b, parsers) if len(parsers) > 0 else success(None)

def first(*parsers: Syntax[Any, S]) -> Syntax[Any, S]:
    return reduce(lambda a, b: a // b, parsers) if len(parsers) > 0 else success(None)

def last(*parsers: Syntax[Any, S]) -> Syntax[Any, S]:
    return reduce(lambda a, b: a >> b, parsers) if len(parsers) > 0 else success(None)

def named(* parsers: Syntax[Any, S] | Tuple[str, Syntax[Any, S]]) -> Syntax[Any, S]:
    def is_named_parser(x: Any) -> bool:
        return isinstance(x, tuple) and len(x) == 2 and isinstance(x[0], str) and isinstance(x[1], Syntax)
    
    def to_parser(x: Syntax[Any, S] | Tuple[str, Syntax[Any, S]])->Syntax[Any, S]:
        if isinstance(x, tuple) and len(x) == 2 and isinstance(x[0], str) and isinstance(x[1], Syntax):
            return x[1].bind(x[0])
        elif isinstance(x, Syntax):
            return x
        else:
            raise ValueError(f"Invalid parser or tuple: {x}", x)
    ret: Optional[Syntax[Any, S]] = None
    has_data = False
    for p in parsers:
        just_parser = to_parser(p)
        if has_data:
            if ret is not None:
                if is_named_parser(p):
                    ret = ret + just_parser
                else:
                    ret = ret // just_parser
            else:
                ret = just_parser
        else:
            has_data = is_named_parser(p)
            if ret is None:
                ret = just_parser
            else:
                ret = ret >> just_parser
    
    return ret if ret is not None else success(None) 


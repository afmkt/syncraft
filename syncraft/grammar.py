from __future__ import annotations
from typing import Callable, Any, overload, Dict, Set, Literal
from syncraft.ast import AST, SyncraftError
from syncraft.syntax import Syntax, Collector
from syncraft.algebra import Algebra
from syncraft.parser import parser
from syncraft.generator import generator
from syncraft.cache import Cache
from syncraft.input import StreamCursor
from syncraft.utils import file as get_file, line as get_line, func as get_func




AUTUO_NAME = "<auto_name>"





class LazyHolder:
    def __init__(self, 
                 thunk: Callable[[Any], Syntax], 
                 root: bool,
                 name: str | None, 
                 need_name: bool, 
                 file: str | None, 
                 line: int | None, 
                 func: str | None):
        self.root = root
        self.thunk = thunk
        self.name = name
        self.need_name = need_name
        self.file = file
        self.line = line
        self.func = func

    def __str__(self) -> str:
        return f"LazyHolder({self.name}, {self.thunk})"
    
    def rule(self, S: Any, MAX_NAME_LENGTH: int, key_name: str) -> Syntax:

        rule = S.lazy(lambda: self.thunk(S))
        if self.need_name:            
            rule_name = str(rule)
            if self.name == AUTUO_NAME:
                self.name = None
                if (len(rule_name) > MAX_NAME_LENGTH or 'UNSOLVED' in rule_name):
                    self.name = key_name                        
            rule = rule._named(name=self.name, file=self.file, line=self.line, func=self.func)
        else:
            rule = rule._named(name=None, file=self.file, line=self.line, func=self.func)

        return rule.marked_as_root() if self.root else rule


@overload
def lazy(thunk: str, *, root:Literal[False]=False) -> Callable[[Callable[[Any], Syntax]], Any]: ...
@overload
def lazy(thunk: str, *, root:Literal[True]=True) -> Callable[[Callable[[Any], Syntax]], Any]: ...

@overload
def lazy(thunk: bool, *, root:Literal[False]=False) -> Callable[[Callable[[Any], Syntax]], Any]: ...
@overload
def lazy(thunk: bool, *, root:Literal[True]=True) -> Callable[[Callable[[Any], Syntax]], Any]: ...

@overload
def lazy(thunk: None=None, *, root:Literal[False]=False) -> Callable[[Callable[[Any], Syntax]], Any]: ...
@overload
def lazy(thunk: None=None, *, root:Literal[True]=True) -> Callable[[Callable[[Any], Syntax]], Any]: ...

@overload
def lazy(thunk: Callable[[Any], Syntax], *, root:Literal[False]=False) -> Any: ...
@overload
def lazy(thunk: Callable[[Any], Syntax], *, root:Literal[True]=True) -> Any: ...

def lazy(thunk: str | Callable[[Any], Syntax] | bool | None = None, *, root:bool=False) -> Any | Callable[[Any], Any]:
    """
    Decorator for lazy grammar rules.
    @lazy
    def rule(cls):...    rule is named 'rule'

    @lazy("name")
    def rule(cls):...    rule is named 'name'

    @lazy(NO_NAME)
    def rule(cls):...    rule is unnamed

    @lazy(True)
    def rule(cls):...    rule is named 'rule'

    @lazy(False)
    def rule(cls):...    rule is unnamed
    """
    level = 1
    file, line, func = get_file(level), get_line(level), get_func(level)
    if callable(thunk):
        return LazyHolder(thunk, root=root, name=AUTUO_NAME, need_name=True, file=file, line=line, func=func)
    elif isinstance(thunk, str):
        def wrapper(f: Callable[[Any], Syntax]) -> LazyHolder:
            return LazyHolder(f, root=root, name=thunk, need_name=True, file=file, line=line, func=func)
        return wrapper
    elif isinstance(thunk, bool):
        def wrapper(f: Callable[[Any], Syntax]) -> LazyHolder:
            return LazyHolder(f, root=root, name=None if not thunk else AUTUO_NAME, need_name=thunk, file=file, line=line, func=func)
        return wrapper
    elif thunk is None:
        def wrapper(f: Callable[[Any], Syntax]) -> LazyHolder:
            return LazyHolder(f, root=root, name=AUTUO_NAME, need_name=True, file=file, line=line, func=func)
        return wrapper
    else:
        raise TypeError("Invalid argument to lazy decorator")



def rule(syntax: Syntax, name: str | None = AUTUO_NAME, level: int = 1) -> Syntax:
    if not isinstance(syntax, Syntax):
        raise TypeError("Argument to rule must be a Syntax instance")
    file, line, func = get_file(level), get_line(level), get_func(level)
    return syntax._named(name=name, file=file, line=line, func=func)

def root(syntax: Syntax, name: str | None = AUTUO_NAME) -> Syntax:
    if not isinstance(syntax, Syntax):
        raise TypeError("Argument to rule must be a Syntax instance")
    return rule(syntax.marked_as_root(), name=name, level=2)



class Mapper:
    @staticmethod
    def eval(func: Any, value: Any) -> Any:
        if isinstance(func, Mapper):
            return func(value)
        else:
            return func
    def __init__(self, func: Callable[[Any], Any]):
        self.func = func

    def __call__(self, value: Any) -> Any:
        return self.func(value)
    
    def __add__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: self.func(t) + Mapper.eval(other, t))
    
    def __radd__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: Mapper.eval(other, t) + self.func(t))
    
    def __mul__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: self.func(t) * Mapper.eval(other, t))
    
    def __rmul__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: Mapper.eval(other, t) * self.func(t))
    
    def __div__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: self.func(t) / Mapper.eval(other, t))
    
    def __rdiv__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: Mapper.eval(other, t) / self.func(t))
    
    def __floordiv__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: self.func(t) // Mapper.eval(other, t))
    
    def __rfloordiv__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: Mapper.eval(other, t) // self.func(t))
    
    def __sub__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: self.func(t) - Mapper.eval(other, t))
    
    def __rsub__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: Mapper.eval(other, t) - self.func(t))
    
    def __neg__(self) -> Mapper:
        return Mapper(lambda t: -self.func(t))
    
    def __pos__(self) -> Mapper:
        return Mapper(lambda t: +self.func(t))  
    
    def __abs__(self) -> Mapper:
        return Mapper(lambda t: abs(self.func(t)))
    
    def __getitem__(self, index: Any ) -> Mapper:
        return Mapper(lambda t: self.func(t)[Mapper.eval(index, t)])
    
    def __or__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: self.func(t) | Mapper.eval(other, t))
    
    def __ror__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: Mapper.eval(other, t) | self.func(t))
    
    def __and__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: self.func(t) & Mapper.eval(other, t))
    
    def __rand__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: Mapper.eval(other, t) & self.func(t))
    
    def __invert__(self) -> Mapper:
        return Mapper(lambda t: ~self.func(t))  
    
    @property
    def not_(self) -> Mapper:
        return Mapper(lambda t: not self.func(t))
    
    def __xor__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: self.func(t) ^ Mapper.eval(other, t))
    
    def __rxor__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: Mapper.eval(other, t) ^ self.func(t))
    
    def bool(self) -> Mapper:
        return Mapper(lambda t: bool(self.func(t)))
    
    def __not__(self) -> Mapper:
        return Mapper(lambda t: not self.func(t))
    
    def __int__(self) -> Mapper:
        return Mapper(lambda t: int(self.func(t)))
    
    def __float__(self) -> Mapper:
        return Mapper(lambda t: float(self.func(t)))
        
    def __length_hint__(self) -> Mapper:
        return Mapper(lambda t: len(self.func(t)))
    
    def __len__(self) -> Mapper:
        return Mapper(lambda t: len(self.func(t)))  
    
    def __contains__(self, item: Any) -> Mapper:
        return Mapper(lambda t: Mapper.eval(item, t) in self.func(t))
    
    def __iter__(self) -> Mapper:
        return Mapper(lambda t: iter(self.func(t)))
    
    def __reversed__(self) -> Mapper:
        return Mapper(lambda t: reversed(self.func(t)))
    
    def __eq__(self, other: Any):
        return Mapper(lambda t: self.func(t) == Mapper.eval(other, t))
    
    def __ne__(self, other: Any):
        return Mapper(lambda t: self.func(t) != Mapper.eval(other, t))
    
    def __lt__(self, other: Any) -> Mapper:
        return Mapper(lambda t: self.func(t) < Mapper.eval(other, t))
    
    def __le__(self, other: Any) -> Mapper:
        return Mapper(lambda t: self.func(t) <= Mapper.eval(other, t))
    
    def __gt__(self, other: Any) -> Mapper:
        return Mapper(lambda t: self.func(t) > Mapper.eval(other, t))
    
    def __ge__(self, other: Any) -> Mapper:
        return Mapper(lambda t: self.func(t) >= Mapper.eval(other, t))
    
    def apply(self, func: Callable[[Any], Any]) -> Mapper:
        return Mapper(lambda t: func(self.func(t)))
    
    def if_then_else(self, then_mapper: Mapper | Any, else_mapper: Mapper | Any) -> Mapper:
        return Mapper(lambda t: Mapper.eval(then_mapper, t) if self.func(t) else Mapper.eval(else_mapper, t))
    
    @property
    def list(self) -> Mapper:
        def to_list(t: Any) -> list:
            return [self.func(t)]
        return Mapper(to_list)
    
    @property
    def tuple(self) -> Mapper:
        def to_tuple(t: Any) -> tuple:
            return (self.func(t),)
        return Mapper(to_tuple)
    
    def dict(self, d: Dict) -> Mapper:
        def as_index_f(t: Any) -> Any:
            y = Mapper.eval(d, t)
            return y[self.func(t)]
        return Mapper(as_index_f)

def at(index: int | None = None) -> Mapper:
    if index is None:
        return Mapper(lambda t: t)
    else:
        return Mapper(lambda t: t[index])

def const(value: Any) -> Mapper:
    return Mapper(lambda t: value)

_0 = at(0)
_1 = at(1)
_2 = at(2)
_3 = at(3)
_4 = at(4)
_5 = at(5)
_6 = at(6)
_7 = at(7)
_8 = at(8)
_9 = at(9)

def call(c: Collector, *args: Any, **kwargs: Any) -> Mapper:
    def bound(t: list|tuple) -> Any:
        unnamed_args = []
        named_args = {}
        for v in args:
            if isinstance(v, Mapper):
                unnamed_args.append(v(t))
            else:
                unnamed_args.append(v)
        for k, v in kwargs.items():
            if isinstance(v, Mapper):
                named_args[k] = v(t)
            else:
                named_args[k] = v
        return c(*unnamed_args, **named_args)
    return Mapper(bound)
    

class GrammarMeta(type):
    """Metaclass for grammars."""

    def __new__(mcs, name, bases, namespace, **config) -> Any:
        MAX_NAME_LENGTH = config.pop("max_name_length", 0)
        S = Syntax.set(**config)
        new_namespace: Dict[str, Any] = dict()
        lazy_rules: Dict[str, LazyHolder] = {}
        normal_rules: Dict[str, Syntax] = {}
        
        root_rule: Set[Syntax] = set()
        for name, value in namespace.items():
            if isinstance(value, LazyHolder):
                lazy_rules[name] = value
            elif isinstance(value, Syntax):
                if value.is_root:
                    if root_rule:
                        raise ValueError(f"Multiple root rules defined: {root_rule} and {name}")
                    root_rule.add(value)
                if value.has_name:
                    if value.spec.name == AUTUO_NAME:
                        value.set_name(None)
                        n = str(value)
                        if len(n) > MAX_NAME_LENGTH:
                            value = value.named(name=name, _location=False)
                normal_rules[name] = value
            new_namespace[name] = value

        for n in lazy_rules.keys():
            new_namespace.pop(n, None)
        cls = type.__new__(mcs, name, (S,), dict(new_namespace))
        all_rules: Dict[str, Syntax] = {}
        for name, value in lazy_rules.items():
            r = value.rule(cls, MAX_NAME_LENGTH, name)
            all_rules[name] = r
            if r.is_root:
                if root_rule:
                    raise ValueError(f"Multiple root rules defined: {root_rule} and {name}")
                root_rule.add(r)
            setattr(cls, name, r)
        all_rules.update(normal_rules)
        setattr(cls, '_rules', all_rules)
        setattr(cls, '_root_rule', next(iter(root_rule)) if root_rule else None)
        return cls
    

class Grammar(Syntax, metaclass=GrammarMeta):
    _rules: Dict[str, Syntax]
    _root_rule: Syntax | None
    _parser: Dict[Syntax, Algebra] = {}
    _generator: Dict[Syntax, Algebra] = {}

    @classmethod
    def parser(cls, syntax: Syntax | None = None) -> Algebra:
        """Create a parser for the grammar."""
        if syntax is None:
            if cls._root_rule is None:
                raise ValueError("No root rule defined for the grammar")
            syntax = cls._root_rule
        if syntax in cls._parser:
            return cls._parser[syntax]
        ret = parser(syntax=syntax)
        cls._parser[syntax] = ret
        return ret
    
    @classmethod
    def generator(cls, syntax: Syntax | None = None) -> Algebra:
        """Create a generator for the grammar."""
        if syntax is None:
            if cls._root_rule is None:
                raise ValueError("No root rule defined for the grammar")
            syntax = cls._root_rule
        if syntax in cls._generator:
            return cls._generator[syntax]
        ret = generator(syntax=syntax)
        cls._generator[syntax] = ret
        return ret
    
    @classmethod
    def validator(cls, syntax: Syntax | None = None) -> Algebra:
        """Create a validator for the grammar."""
        return cls.generator(syntax=syntax)

    @classmethod
    def parse(cls, data: str, syntax: Syntax | None = None, raw: bool = False) -> Any:
        """Parse text using the grammar."""
        from syncraft.parser import Runner
        parser = cls.parser(syntax=syntax)
        runner: Runner[Any] = Runner()
        cursor = StreamCursor.from_data(data)
        cache: Cache[Any] = Cache()
        for result, s in runner.run(parser, state=None, cursor=cursor, once=True, cache=cache):
            if s:
                if isinstance(result, AST):
                    return result if raw else result.mapped 
                else:
                    return result
            else:
                return result
        raise SyncraftError("Regex did not yield any results", offender=None, expect="at least one result")

    @classmethod
    def stream_parse(cls, data: StreamCursor[Any], syntax: Syntax | None = None, raw: bool = False) -> Any:
        """Parse text using the grammar."""
        from syncraft.parser import Runner
        parser = cls.parser(syntax=syntax)
        runner: Runner[Any] = Runner()
        cache: Cache[Any] = Cache()
        
        for result, s in runner.run(parser, state=None, cursor=data, once=False, cache=cache):
            if s:
                if isinstance(result, AST):
                    yield result if raw else result.mapped
                else:
                    yield result
            else:
                yield result
                
    @classmethod
    def generate(cls, data: Any, syntax: Syntax | None = None, seed: int | None = None) -> Any:
        """Generate text using the grammar."""
        from syncraft.generator import Runner
        import random
        generator = cls.generator(syntax=syntax)        
        runner = Runner(ast=data,
                        seed=seed if seed is not None else random.randint(0, 2**32 - 1), 
                        restore_pruned=False)
        for result, s in runner.run(generator, state=None, cursor=None, once=True, cache=None):
            return result
        
    @classmethod
    def validate(cls, data: Any, syntax: Syntax | None = None, seed: int | None = None) -> Any:
        """Validate text using the grammar."""
        from syncraft.generator import Runner
        import random
        generator = cls.generator(syntax=syntax)        
        runner = Runner(ast=data, 
                        seed=seed if seed is not None else random.randint(0, 2**32 - 1),
                        restore_pruned=True)
        for result, _ in runner.run(generator, state=None, cursor=None, once=True, cache=None):
            return result
        

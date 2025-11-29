from __future__ import annotations
from typing import Callable, Any, overload, Dict, Set, Literal, Optional
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
            namespace.pop(n, None)
            
        cls = type.__new__(mcs, name, (S,), dict(new_namespace))
        all_rules: Dict[str, Syntax] = {}
        for name, value in lazy_rules.items():
            rule = value.rule(cls, MAX_NAME_LENGTH, name)
            all_rules[name] = rule
            if rule.is_root:
                if root_rule:
                    raise ValueError(f"Multiple root rules defined: {root_rule} and {name}")
                root_rule.add(rule)
            setattr(cls, name, rule)
        all_rules.update(normal_rules)
        setattr(cls, '_rules', all_rules)
        setattr(cls, '_root_rule', next(iter(root_rule)) if root_rule else None)
        return cls
    

class Grammar(Syntax, metaclass=GrammarMeta):
    _rules: Dict[str, Syntax]
    _root_rule: Syntax | None
    _parser: Dict[Syntax, Algebra[Any, Any]] = {}
    _generator: Dict[Syntax, Algebra[Any, Any]] = {}
    @classmethod
    def seq2(cls, to: Collector|None=None, _name: str | None = AUTUO_NAME, **kwargs: Syntax | tuple[Syntax, Any]) -> Syntax:
        """Helper function to create a sequence syntax rule."""
        level = 1
        file, line, func = get_file(level), get_line(level), get_func(level)
        parsers: list[Syntax | tuple[Syntax, Any]] = []
        for k, v in kwargs.items():
            if k.startswith("_"):
                parsers.append(v)
            elif isinstance(v, Syntax):
                parsers.append(v.mark(k))
            elif isinstance(v, tuple) and len(v) == 2 and isinstance(v[0], Syntax):
                parsers.append((v[0].mark(k), v[1]))
            else:
                pass
        if len(parsers) == 0:
            raise ValueError("No parsers provided for seq2")
        if len(parsers) > 1:
            rule: Syntax = cls.seq(*parsers)
        else:
            rule = parsers[0] if isinstance(parsers[0], Syntax) else parsers[0][0]
        if to is not None:
            rule = rule.to(to)
        return rule._named(name=_name, file=file, line=line, func=func)
    
    @classmethod
    def alt2(cls, to: Collector|None=None, _name: str | None = AUTUO_NAME, **kwargs: Syntax) -> Syntax:
        """Helper function to create an alternative syntax rule."""
        level = 1
        file, line, func = get_file(level), get_line(level), get_func(level)
        parsers: list[Syntax] = []
        for k, v in kwargs.items():
            if k.startswith("_"):
                parsers.append(v)
            elif isinstance(v, Syntax):
                parsers.append(v.mark(k))
            else:
                pass
        rule: Syntax = cls.alt(*parsers)
        if to is not None:
            rule = rule.to(to)
        return rule._named(name=_name, file=file, line=line, func=func)

    @classmethod
    def parser(cls, syntax: Syntax | None = None) -> Algebra[Any, Any]:
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
    def generator(cls, syntax: Syntax | None = None) -> Algebra[Any, Any]:
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
    def validator(cls, syntax: Syntax | None = None) -> Algebra[Any, Any]:
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
        

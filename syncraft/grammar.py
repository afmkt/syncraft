from __future__ import annotations
from typing import Callable, Any, overload, Dict, Set, Literal
from syncraft.ast import AST, SyncraftError
from syncraft.syntax import Syntax
from syncraft.algebra import Algebra
from syncraft.parser import parser
from syncraft.generator import generator
from syncraft.cache import Cache
from syncraft.input import StreamCursor
from syncraft.utils import file as get_file, line as get_line, func as get_func


NO_NAME = "<no_name>"

def rule(syntax: Syntax, *, name: str | None = None, is_root: bool = False) -> Syntax:
    level:int = 1
    file, line, func = get_file(level), get_line(level), get_func(level)
    if not isinstance(syntax, Syntax):
        raise TypeError("Argument to rule must be a Syntax instance")
    if is_root:
        syntax = syntax.as_root()
    ret = syntax._named(name=name, file=file, line=line, func=func)
    assert ret.is_root == is_root, "Rule root status does not match is_root argument"
    return ret



class LazyDescriptor:
    def __init__(self, 
                 f: Callable[..., Syntax] | classmethod, 
                 syntax_cls: type[Syntax] | None = None,
                 name: str | None = None,
                 file: str | None = None,
                 line: int | None = None,
                 func: str | None = None,
                 is_root: bool = False
                 ):
        self.f = f
        self.name = f.__name__ if name is None else name
        self.cls = syntax_cls
        self.file = file
        self.line = line
        self.func = func
        self.is_root = is_root
        self.resolved: Syntax | None = None

    def _set_cls(self, cls: type[Syntax]) -> None:
        self.cls = cls
        if self.resolved is not None:
            self.resolved = self.resolved.rebase(cls)            
    
    def __get__(self, instance: Any, owner: type) -> Syntax:
        if self.resolved is not None:
            return self.resolved
        if isinstance(self.f, classmethod):
            fn = self.f.__func__
        else:
            fn = self.f
        assert self.cls is not None, "LazyDescriptor syntax class not set"
        ret = self.cls.lazy(lambda: fn(owner))._named(name=self.name, file=self.file, line=self.line, func=self.func)
        if self.is_root:
            ret = ret.as_root()
        self.resolved = ret
        return ret

    def __str__(self) -> str:
        return f"<LazyDescriptor {self.name} at {self.file}:{self.line} in {self.func}>"



def lazy(name: str | None | Callable[..., Syntax] = None, *, is_root: bool = False) -> Any:
    level = 1
    file, line, func = get_file(level), get_line(level), get_func(level)
    if callable(name) or isinstance(name, classmethod):
        return LazyDescriptor(name, None, None, file, line, func, is_root=is_root)
    elif isinstance(name, str):
        def wrapper(f: Callable[..., Syntax]) -> LazyDescriptor:
            return LazyDescriptor(f, None, name, file, line, func, is_root=is_root)
        return wrapper
    else: 
        raise TypeError("Argument to lazy must be a callable or a string or a boolean")
    


    
    

def grammar(**config: Any) -> Callable[[Any], Any]:
    S = Syntax.set(**config)
    def wrapper(cls: type) -> type:
        rules = {}
        root = None
        for name, value in list(cls.__dict__.items()):
            # if isinstance(value, LazyDescriptor):
            #     print(value)
            #     value._set_cls(S)
            #     value = value.__get__(None, cls)
            if isinstance(value, Syntax):
                value = value.rebase(S)
                if value.spec.name is None:
                    value = value.named(name=name, _location=False)
                elif value.spec.name == NO_NAME:
                    value = value.named(name=None, _location=False)
                rules[name] = value
                if value.is_root:
                    if root is not None:
                        raise ValueError("Multiple root rules defined for grammar")
                    root = value
                setattr(cls, name, value)
        setattr(cls, '_rules', rules)
        setattr(cls, '_root_rule', root)
        return cls
    return wrapper

        

    

class Grammar:
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
        

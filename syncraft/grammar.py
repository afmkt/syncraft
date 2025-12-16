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



def lazy(S: type[Syntax], name: str | None | Callable[..., Syntax] = None, *, is_root: bool = False) -> Any:
    level = 1
    file, line, func = get_file(level), get_line(level), get_func(level)
    if callable(name):
        if is_root:
            return S.lazy(name).as_root()._named(name=None, file=file, line=line, func=func)
        else:
            return S.lazy(name)._named(name=None, file=file, line=line, func=func)
    elif isinstance(name, str) or name is None:
        def wrapper(f: Callable[..., Syntax]) -> Syntax:
            if is_root:
                return S.lazy(f).as_root()._named(name=name if name is not None else f.__name__, file=file, line=line, func=func)
            else:
                return S.lazy(f)._named(name=name if name is not None else f.__name__, file=file, line=line, func=func)
        return wrapper
    else: 
        raise TypeError(f"Argument to lazy must be a callable or a string or a boolean, got {type(name)}")
    


def class_field_location(cls):
    import inspect
    import ast
    source = inspect.getsource(cls)
    filename = inspect.getsourcefile(cls)
    start_line = inspect.getsourcelines(cls)[1]
    tree = ast.parse(source)
    field_locations = {}
    class_node = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    for stmt in class_node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            field_locations[stmt.target.id] = (filename, stmt.lineno + start_line - 1)
        elif isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    field_locations[target.id] = (filename, stmt.lineno + start_line - 1)

    return field_locations

def grammar(cls: type) -> type:    
    locations = class_field_location(cls)
    rules = {}
    root = None
    for name, value in list(cls.__dict__.items()):
        if isinstance(value, Syntax):
            if value.spec.name is None:
                s_name = name
            elif value.spec.name == NO_NAME:
                s_name = None
            else:
                s_name = value.spec.name
            if value.location is None:                
                if name in locations:
                    file, line = locations[name]
                    value.update_meta_in_place(name = s_name, file=file, line=line, func=None, _location=True)
                    
                else:
                    raise ValueError(f"Grammar rules must have location information, but rule '{name}' does not.")
            else:
                value.update_meta_in_place(name = s_name, file = None, line= None, func=None, _location=False)
                
            rules[name] = value
            if value.is_root:
                if root is not None:
                    raise ValueError("Multiple root rules defined for grammar")
                root = value
            setattr(cls, name, value)
    setattr(cls, '_rules', rules)
    setattr(cls, '_root_rule', root)
    return cls

        

    

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
    def parse(cls, 
              data: str, 
              syntax: Syntax | None = None, 
              raw: bool = False, 
              cache: Cache[Any] | None = None) -> Any:
        """Parse text using the grammar."""
        from syncraft.parser import Runner
        parser = cls.parser(syntax=syntax)
        runner: Runner[Any] = Runner()
        cursor = StreamCursor.from_data(data)
        cache = cache or Cache()
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
    def stream_parse(cls, 
                     data: StreamCursor[Any], 
                     syntax: Syntax | None = None, 
                     raw: bool = False,
                     cache: Cache[Any] | None = None) -> Any:
        """Parse text using the grammar."""
        from syncraft.parser import Runner
        parser = cls.parser(syntax=syntax)
        runner: Runner[Any] = Runner()
        cache = cache or Cache()
        
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
        

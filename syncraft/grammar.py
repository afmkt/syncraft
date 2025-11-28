from __future__ import annotations
from typing import Callable, Any, overload, Literal
from syncraft.syntax import Syntax
from syncraft.utils import file as get_file, line as get_line, func as get_func
NO_NAME = ""
AUTUO_NAME = "<auto_name>"
class LazyHolder:
    def __init__(self, thunk: Callable[[Any], Syntax], name: str | None, need_name: bool, file: str | None, line: int | None, func: str | None):
        self.thunk = thunk
        self.name = name
        self.need_name = need_name
        self.file = file
        self.line = line
        self.func = func

@overload
def lazy(thunk: str) -> Callable[[Callable[[Any], Syntax]], Any]: ...
@overload
def lazy(thunk: bool) -> Callable[[Callable[[Any], Syntax]], Any]: ...
@overload
def lazy(thunk: Callable[[Any], Syntax]) -> Any: ...
def lazy(thunk: str | Callable[[Any], Syntax] | bool) -> Any | Callable[[Any], Any]:
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
        return LazyHolder(thunk, None, need_name=True, file=file, line=line, func=func)
    elif isinstance(thunk, str):
        def wrapper(f: Callable[[Any], Syntax]) -> LazyHolder:
            return LazyHolder(f, name=thunk, need_name=thunk != NO_NAME, file=file, line=line, func=func)
        return wrapper
    elif isinstance(thunk, bool):
        def wrapper(f: Callable[[Any], Syntax]) -> LazyHolder:
            return LazyHolder(f, name=None if thunk else NO_NAME, need_name=thunk, file=file, line=line, func=func)
        return wrapper
    else:
        raise TypeError("Invalid argument to lazy decorator")



def rule(syntax: Syntax, name: str | None = AUTUO_NAME) -> Syntax:
    """Helper function to name a syntax rule."""
    level = 1
    file, line, func = get_file(level), get_line(level), get_func(level)
    return syntax._named(name=name, file=file, line=line, func=func)

class GrammarMeta(type):
    """Metaclass for grammars."""

    def __new__(mcs, name, bases, namespace, **config):
        S = Syntax.config(**config)
        lazy_rules = {}
        for name, value in namespace.items():
            if isinstance(value, LazyHolder):
                lazy_rules[name] = value

        for n in lazy_rules.keys():
            namespace.pop(n, None)

        new_namespace = {}
        for k, v in namespace.items():
            if isinstance(v, Syntax):
                if v.has_name:
                    if v.spec.name == AUTUO_NAME:
                        v = v.named(name=k, _location=False)
            new_namespace[k] = v


        cls = type.__new__(mcs, name, (S,), dict(new_namespace))

        for name, value in lazy_rules.items():
            rule = S.lazy(lambda: value.thunk(cls))
            if value.need_name:            
                if value.name is None:
                    value.name = name
                rule = rule._named(name=value.name, file=value.file, line=value.line, func=value.func)
            else:
                rule = rule._named(name=None, file=value.file, line=value.line, func=value.func)
            setattr(cls, name, rule)
        return cls
    

class Grammar(Syntax, metaclass=GrammarMeta):
    """Base class for grammars."""
    pass

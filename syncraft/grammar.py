from __future__ import annotations
from typing import Callable, Any, overload
from syncraft.syntax import Syntax, Collector
from syncraft.utils import file as get_file, line as get_line, func as get_func

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
        return LazyHolder(thunk, name=AUTUO_NAME, need_name=True, file=file, line=line, func=func)
    elif isinstance(thunk, str):
        def wrapper(f: Callable[[Any], Syntax]) -> LazyHolder:
            return LazyHolder(f, name=thunk, need_name=True, file=file, line=line, func=func)
        return wrapper
    elif isinstance(thunk, bool):
        def wrapper(f: Callable[[Any], Syntax]) -> LazyHolder:
            return LazyHolder(f, name=None if not thunk else AUTUO_NAME, need_name=thunk, file=file, line=line, func=func)
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
        MAX_NAME_LENGTH = config.pop("max_name_length", 0)
        S = Syntax.set(**config)
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
                        v.set_name(None)
                        n = str(v)
                        if len(n) > MAX_NAME_LENGTH:
                            v = v.named(k)
            new_namespace[k] = v


        cls = type.__new__(mcs, name, (S,), dict(new_namespace))

        for name, value in lazy_rules.items():
            rule = S.lazy(lambda: value.thunk(cls))
            if value.need_name:            
                rule_name = str(rule)
                if value.name == AUTUO_NAME:
                    value.name = None
                    if (len(rule_name) > MAX_NAME_LENGTH or 'UNSOLVED' in rule_name):
                        value.name = name                        
                rule = rule._named(name=value.name, file=value.file, line=value.line, func=value.func)
            else:
                rule = rule._named(name=None, file=value.file, line=value.line, func=value.func)
            setattr(cls, name, rule)
        return cls
    

class Grammar(Syntax, metaclass=GrammarMeta):
    """Base class for grammars."""
    @classmethod
    def seq2(cls, to: Collector|None=None, name: str | None = AUTUO_NAME, **kwargs: Syntax | tuple[Syntax, Any]) -> Syntax:
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
        rule: Syntax = cls.seq(*parsers)
        if to is not None:
            rule = rule.to(to)
        return rule._named(name=name, file=file, line=line, func=func)
    
    @classmethod
    def alt2(cls, to: Collector|None=None, name: str | None = AUTUO_NAME, **kwargs: Syntax) -> Syntax:
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
        return rule._named(name=name, file=file, line=line, func=func)

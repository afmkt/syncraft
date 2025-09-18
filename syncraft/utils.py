from __future__ import annotations
from typing import Any, Callable, Optional, Generator,Generic, TypeVar, cast
from dataclasses import dataclass, field, replace
import inspect
import functools
import types
from rich.console import Console

import os
from enum import Enum


class ENV_VARS(Enum):
    SYNCRAFT_DEBUG = "SYNCRAFT_DEBUG"

def set_debug(value:bool = True)->None:
    os.environ[ENV_VARS.SYNCRAFT_DEBUG.value] = "yes" if value else "no"

def debug_print(*args: Any) -> None:
    if str(os.getenv(ENV_VARS.SYNCRAFT_DEBUG.value)).lower() in ("1", "true", "yes"):
        Console().print(*args, markup=False)
    


class CallWith:
    @staticmethod
    def get_callable_signature(obj, follow_wrapped: bool = True) -> inspect.Signature:
        """
        Given a callable object, retrieves its signature.
        Handles normal functions, bound methods, unbound methods, 
        classes (for __init__), static methods, class methods, and callable instances.
        """
        if not callable(obj):
            raise TypeError(f"Object {obj} is not callable.")

        # Case 1: If obj is a class, get the signature of its __init__ method
        if inspect.isclass(obj):
            return inspect.signature(obj.__init__, follow_wrapped=follow_wrapped)

        # Case 2: Static method descriptor
        if isinstance(obj, staticmethod):
            return inspect.signature(obj.__func__, follow_wrapped=follow_wrapped)

        # Case 3: Class method descriptor
        if isinstance(obj, classmethod):
            return inspect.signature(obj.__func__, follow_wrapped=follow_wrapped)

        # Case 4: Coroutine or async function
        if inspect.iscoroutinefunction(obj):
            return inspect.signature(obj, follow_wrapped=follow_wrapped)

        # Case 5: functools.partial
        if isinstance(obj, functools.partial):
            return inspect.signature(obj.func, follow_wrapped=follow_wrapped)

        # Case 6: Bound or unbound method
        if inspect.ismethod(obj):
            return inspect.signature(obj, follow_wrapped=follow_wrapped)
            # return inspect.signature(obj.__func__, follow_wrapped=follow_wrapped)

        # Case 7: Regular function or lambda
        if isinstance(obj, (types.FunctionType, types.LambdaType)):
            return inspect.signature(obj, follow_wrapped=follow_wrapped)

        try:
            return inspect.signature(obj, follow_wrapped=follow_wrapped)
        except (TypeError, ValueError):
            # Fallback to inspecting __call__
            return inspect.signature(obj.__call__, follow_wrapped=follow_wrapped)
    
    def __init__(self, specific_func:Callable[...,Any], *general_args:Any, **general_kwargs:Any) -> None:
        self.func = specific_func
        sig = CallWith.get_callable_signature(specific_func) 
        params = sig.parameters.values()

        args = []
        kwargs = {}
        remaining_args = []
        remaining_kwargs = general_kwargs.copy()

        arg_index = 0
        num_args = len(general_args)

        var_positional = False
        var_keyword = False

        consumed_kwargs = set()

        for param in params:
            if param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
                if arg_index < num_args:
                    args.append(general_args[arg_index])
                    arg_index += 1
                elif param.name in general_kwargs:
                    args.append(general_kwargs[param.name])
                    consumed_kwargs.add(param.name)
                elif param.default is not inspect.Parameter.empty:
                    args.append(param.default)
                else:
                    if param.name != 'self':  # Skip 'self' for instance methods
                        raise TypeError(f"Missing required positional argument: {param.name}")

            elif param.kind == inspect.Parameter.VAR_POSITIONAL:
                var_positional = True
                # collect remaining general_args into *args
                args.extend(general_args[arg_index:])
                arg_index = num_args  # mark all as used

            elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                if param.name in general_kwargs:
                    kwargs[param.name] = general_kwargs[param.name]
                    consumed_kwargs.add(param.name)
                elif param.default is not inspect.Parameter.empty:
                    kwargs[param.name] = param.default
                else:
                    raise TypeError(f"Missing required keyword-only argument: {param.name}")

            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                var_keyword = True
                # allow all remaining kwargs
                for k, v in general_kwargs.items():
                    if k not in consumed_kwargs and k not in kwargs:
                        kwargs[k] = v
                        consumed_kwargs.add(k)

        # Collect unused arguments
        if arg_index < num_args:
            remaining_args = list(general_args[arg_index:]) if not var_positional else []

        remaining_kwargs = {
            k: v for k, v in general_kwargs.items()
            if k not in consumed_kwargs and k not in kwargs
        } if not var_keyword else {}

        self.func = specific_func
        self.args = args
        self.kwargs = kwargs
        self.unused_args = remaining_args
        self.unused_kwargs = remaining_kwargs

    def __call__(self) -> Any:
        return self.func(*self.args, **self.kwargs)




Y = TypeVar('Y')
Y1 = TypeVar('Y1')
Y2 = TypeVar('Y2')
S = TypeVar('S')
S1 = TypeVar('S1')
S2 = TypeVar('S2')
R = TypeVar('R')
R1 = TypeVar('R1')
R2 = TypeVar('R2')

@dataclass(frozen=True)
class Yield(Generic[Y, S, R, Y1, S1, R1]):
    yield_f: Callable[[Y], Y1] = cast(Callable[[Y], Y1], lambda y: y)
    send_f: Callable[[S1], S] = cast(Callable[[S1], S], lambda s: s)
    return_f: Callable[[R], R1] = cast(Callable[[R], R1], lambda r: r)

    def __call__(self, generator: Generator[Y, S, R]) -> Generator[Y1, S1, R1]:
        try:
            value = next(generator)
            while True:
                send_value = yield self.yield_f(value)
                value = generator.send(self.send_f(send_value))
        except StopIteration as e:
            return self.return_f(e.value)
        

    def ymap(self, f: Callable[[Y1], Y2]) -> Yield[Y, S, R, Y2, S1, R1]:
        def y(y: Y) -> Y2:
            return f(self.yield_f(y))
        return Yield(y, self.send_f, self.return_f)
        
    def smap(self, f: Callable[[S2], S1]) -> Yield[Y, S, R, Y1, S2, R1]:
        def s(s1: S2) -> S:
            return self.send_f(f(s1))
        return Yield(self.yield_f, s, self.return_f)
    
    def rmap(self, f: Callable[[R1], R2]) -> Yield[Y, S, R, Y1, S1, R2]:
        def r(r: R) -> R2:
            return f(self.return_f(r))
        return Yield(self.yield_f, self.send_f, r)
    
    def compose(self, other: Yield[Y1, S1, R1, Y2, S2, R2]) -> Yield[Y, S, R, Y2, S2, R2]:
        return self.ymap(other.yield_f).smap(other.send_f).rmap(other.return_f)





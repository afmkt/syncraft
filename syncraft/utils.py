from __future__ import annotations
from typing import Any, Callable, Generator,Generic, TypeVar, cast, Dict, Hashable, Optional
from dataclasses import dataclass
import inspect
import functools
import types
import collections.abc
import threading
from weakref import WeakKeyDictionary, WeakValueDictionary
import os

def callable_str(obj:Any)->str:
    if not callable(obj):
        return repr(obj)
    original = str(obj)
    idstr = hex(id(obj))
    name = obj.syntax if hasattr(obj, 'syntax') else (
        obj.__name__ if hasattr(obj, '__name__') else obj.__class__.__name__)
    if 'lazy' in original:
        return f"{idstr} @ LAZY({name})"
    elif 'flat_map' in original:
        return f"{idstr} @ THEN({name})"
    elif 'or_else' in original:
        return f"{idstr} @ OR_ELSE({name})"
    elif 'map' in original:
        return f"{idstr} @ MAP({name})"
    elif 'lex' in original:
        return f"{idstr} @ LEX({name})"
    else:
        return f"{idstr} @ {name}"
    

def line(level: int = 0) -> None | int:
    frame = inspect.currentframe()
    if frame is None:
        return None
    while level >= 0 and frame is not None:
        level -= 1
        frame = frame.f_back
    return frame.f_lineno if frame is not None else None

def file(level: int = 0)->None | str:
    frame = inspect.currentframe()
    if frame is None:
        return None
    while level >= 0 and frame is not None:
        level -= 1
        frame = frame.f_back
    return frame.f_code.co_filename if frame is not None else None

def func(level: int = 0) -> None | str:
    frame = inspect.currentframe()
    if frame is None:
        return None
    while level >= 0 and frame is not None:
        level -= 1
        frame = frame.f_back
    ret = frame.f_code.co_name if frame is not None else None
    return ret if ret != '<module>' else None
    

class CallWith:
    cache: Dict[Callable[...,Any], inspect.Signature] = dict()
    @staticmethod
    def get_callable_signature(obj: Any, follow_wrapped: bool = True) -> inspect.Signature:
        """
        Given a callable object, retrieves its signature.
        Handles normal functions, bound methods, unbound methods, 
        classes (for __init__), static methods, class methods, and callable instances.
        """
        if obj in CallWith.cache:
            return CallWith.cache[obj]
        if not callable(obj):
            raise TypeError(f"Object {obj} is not callable.")

        # Case 1: If obj is a class, get the signature of its __init__ method
        if inspect.isclass(obj):
            ret = inspect.signature(obj.__init__, follow_wrapped=follow_wrapped)

        # Case 2: Static method descriptor
        if isinstance(obj, staticmethod):
            ret = inspect.signature(obj.__func__, follow_wrapped=follow_wrapped)

        # Case 3: Class method descriptor
        if isinstance(obj, classmethod):
            ret = inspect.signature(obj.__func__, follow_wrapped=follow_wrapped)

        # Case 4: Coroutine or async function
        if inspect.iscoroutinefunction(obj):
            ret = inspect.signature(obj, follow_wrapped=follow_wrapped)

        # Case 5: functools.partial
        if isinstance(obj, functools.partial):
            ret = inspect.signature(obj.func, follow_wrapped=follow_wrapped)

        # Case 6: Bound or unbound method
        if inspect.ismethod(obj):
            ret = inspect.signature(obj, follow_wrapped=follow_wrapped)

        # Case 7: Regular function or lambda
        if isinstance(obj, (types.FunctionType, types.LambdaType)):
            ret = inspect.signature(obj, follow_wrapped=follow_wrapped)

        try:
            ret = inspect.signature(obj, follow_wrapped=follow_wrapped) # type: ignore
        except (TypeError, ValueError):
            ret = inspect.signature(obj.__call__, follow_wrapped=follow_wrapped) # type: ignore
        CallWith.cache[obj] = ret # type: ignore
        return ret
    
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

        self.missing_args = set()
        self.missing_kwargs = set()
        for param in params:
            if param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
                if param.name != 'self':
                    if arg_index < num_args:
                        args.append(general_args[arg_index])
                        arg_index += 1
                    elif param.name in general_kwargs:
                        args.append(general_kwargs[param.name])
                        consumed_kwargs.add(param.name)
                    elif param.default is not inspect.Parameter.empty:
                        args.append(param.default)
                    else:
                        self.missing_args.add(param.name)
                        # raise TypeError(f"Missing required positional argument: {param.name}")

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
                    self.missing_kwargs.add(param.name)
                    # raise TypeError(f"Missing required keyword-only argument: {param.name}")

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


K = TypeVar('K', bound=Hashable)
V = TypeVar('V', bound=Any)
class ThreadLocalWeakKeyDict(threading.local, Generic[K, V]):
    def __init__(self) -> None:
        super().__init__()
        self.store: WeakKeyDictionary[K, V] = WeakKeyDictionary()

    def __getitem__(self, key: K) -> V:
        return self.store[key]

    def __contains__(self, key: K) -> bool:
        return key in self.store

    def __setitem__(self, key: K, value: V) -> None:
        self.store[key] = value

    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        return self.store.get(key, default)
    
    def items(self):
        return self.store.items()
    
    def keys(self):
        return self.store.keys()
    
    def values(self):
        return self.store.values()
    
    def update(self, other: collections.abc.Mapping[K, V]) -> None:
        self.store.update(other)
    
    def __ior__(self, other: collections.abc.Mapping[K, V]) -> ThreadLocalWeakKeyDict:
        self.store |= other
        return self

    def __delitem__(self, key: K) -> None:
        del self.store[key]

    def __bool__(self) -> bool:
        return bool(self.store)
        
    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)

    def __eq__(self, other):
        if isinstance(other, collections.abc.Mapping):
            return self.store == other
        return NotImplemented

    def __repr__(self):
        return f"{self.__class__.__name__}({self.store})"


class ThreadLocalWeakValueDict(threading.local, Generic[K, V]):
    def __init__(self) -> None:
        super().__init__()
        self.store: WeakValueDictionary[K, V] = WeakValueDictionary()

    def __getitem__(self, key: K) -> V:
        return self.store[key]

    def __contains__(self, key: K) -> bool:
        return key in self.store

    def __setitem__(self, key: K, value: V) -> None:
        self.store[key] = value

    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        return self.store.get(key, default)
    
    def items(self):
        return self.store.items()
    
    def keys(self):
        return self.store.keys()
    
    def values(self):
        return self.store.values()

    def update(self, other: collections.abc.Mapping[K, V]) -> None:
        self.store.update(other)

    def __ior__(self, other: collections.abc.Mapping[K, V]) -> ThreadLocalWeakValueDict:
        self.store |= other
        return self

    def __delitem__(self, key: K) -> None:
        del self.store[key]

    def __bool__(self) -> bool:
        return bool(self.store)
        
    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)

    def __eq__(self, other):
        if isinstance(other, collections.abc.Mapping):
            return self.store == other
        return NotImplemented

    def __repr__(self):
        return f"{self.__class__.__name__}({self.store})"

class ThreadLocalDict(threading.local, Generic[K, V]):
    def __init__(self) -> None:
        super().__init__()
        self.store: Dict[K, V] = {}

    def __getitem__(self, key: K) -> V:
        return self.store[key]

    def __contains__(self, key: K) -> bool:
        return key in self.store

    def __setitem__(self, key: K, value: V) -> None:
        self.store[key] = value

    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        return self.store.get(key, default)
    
    def items(self):
        return self.store.items()
    
    def keys(self):
        return self.store.keys()
    
    def values(self):
        return self.store.values()

    def update(self, other: collections.abc.Mapping[K, V]) -> None:
        self.store.update(other)

    def __ior__(self, other: collections.abc.Mapping[K, V]) -> ThreadLocalDict:
        self.store |= other
        return self

    def __delitem__(self, key: K) -> None:
        del self.store[key]

    def __bool__(self) -> bool:
        return bool(self.store)
        
    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)

    def __eq__(self, other):
        if isinstance(other, collections.abc.Mapping):
            return self.store == other
        return NotImplemented

    def __repr__(self):
        return f"{self.__class__.__name__}({self.store})"


class FrozenDict(collections.abc.Mapping, Generic[K, V]):
    """An immutable, hashable mapping.

    Behaves like a read-only dict and caches its hash, making it suitable as a
    key in other dictionaries or for set membership. Equality compares the
    underlying mapping to any other Mapping.
    """
    def __init__(self, *args, **kwargs):
        self._data = dict(*args, **kwargs)
        self._hash = None

    def __bool__(self)->bool:
        return bool(self._data)

    def __or__(self, other: collections.abc.Mapping) -> "FrozenDict[K, V]":
        """Return a new FrozenDict with merged keys (other overrides self)."""
        merged = dict(self._data)
        merged.update(other)
        return FrozenDict(merged)

    def __ror__(self, other: collections.abc.Mapping) -> "FrozenDict[K, V]":
        """Support other | self."""
        merged = dict(other)
        merged.update(self._data)
        return FrozenDict(merged)
            
    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)
        
    def __hash__(self):
        if self._hash is None:
            self._hash = hash(frozenset(self._data.items()))
        return self._hash

    def __eq__(self, other):
        if isinstance(other, collections.abc.Mapping):
            return self._data == other
        return NotImplemented

    def __repr__(self):
        return f"{self.__class__.__name__}({self._data})"
    




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





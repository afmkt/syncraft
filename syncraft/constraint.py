from __future__ import annotations
from typing import Callable, Generic, Tuple, TypeVar, Optional, Any, Self
from enum import Enum
from dataclasses import dataclass, field, replace
import collections.abc
from collections import defaultdict
from itertools import product

K = TypeVar('K')
V = TypeVar('V')
class FrozenDict(collections.abc.Mapping, Generic[K, V]):
    def __init__(self, *args, **kwargs):
        self._data = dict(*args, **kwargs)
        self._hash = None
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




@dataclass(frozen=True)
class Expr:
    left: Any
    op: str
    right: Any


@dataclass(frozen=True)
class Variable:
    name: Optional[str] = None
    _root: Optional[Variable] = field(default=None, compare=False, repr=False)
    _mapf: Optional[Callable[[Any], Any]] = field(default=None, compare=False, repr=False)

    def __post_init__(self):
        if self._root is None:
            object.__setattr__(self, '_root', self)

    def raw(self, b:'BoundVar') -> Tuple[Any, ...]:
        assert self._root is not None, "_rawf can not be None"
        return b.get(self._root, ())
    

    def map(self, f: Callable[[Any], Any]) -> "Variable":
        if self._mapf is None:
            return replace(self, _mapf=f)
        else:
            oldf = self._mapf
            return replace(self, _mapf=lambda a: f(oldf(a)))
    
    def get(self, b: 'BoundVar') -> Tuple[Any, ...]:
        vals = self.raw(b)
        if self._mapf is not None:
            return tuple(self._mapf(v) for v in vals)
        else:
            return vals
        
    def __call__(self, b:'BoundVar', raw:bool=False) -> Any:
        if raw:
            return self.raw(b)
        else:
            return self.get(b)
        
    def __eq__(self, other): 
        return Expr(self, '==', other)
    def __ne__(self, other): 
        return Expr(self, '!=', other)
    def __lt__(self, other): 
        return Expr(self, '<', other)
    def __le__(self, other): 
        return Expr(self, '<=', other)
    def __gt__(self, other): 
        return Expr(self, '>', other)
    def __ge__(self, other): 
        return Expr(self, '>=', other)    

BoundVar = FrozenDict[Variable, Tuple[Any, ...]]


@dataclass(frozen=True)
class Binding:
    bindings : frozenset[Tuple[Variable, Any]] = frozenset()
    def bind(self, var: Variable, node: Any) -> Binding:
        new_binding = set(self.bindings)
        new_binding.add((var, node))
        return Binding(bindings=frozenset(new_binding))
    
    def to_dict(self)->BoundVar:
        ret = defaultdict(list)
        for var, node in self.bindings:
            ret[var].append(node)
        return FrozenDict({k: tuple(vs) for k, vs in ret.items()})


A = TypeVar('A')
@dataclass(frozen=True)
class Bindable:
    binding: Binding = field(default_factory=Binding)

    def map(self, f: Callable[[Any], Any])->Self: 
        return self
    
    def bind(self, var: Variable, node:Any)->Self:
        return replace(self, binding=self.binding.bind(var, node))


class Quantifier(Enum):
    FORALL = "forall"
    EXISTS = "exists"

@dataclass(frozen=True)
class Constraint:
    run_f: Callable[[BoundVar], bool]
    name: str = ""
    def __call__(self, bound: BoundVar)->bool:
        return self.run_f(bound)
    def __and__(self, other: Constraint) -> Constraint:
        return Constraint(
            run_f=lambda bound: self(bound) and other(bound),
            name=f"({self.name} && {other.name})"
        )
    def __or__(self, other: Constraint) -> Constraint:
        return Constraint(
            run_f=lambda bound: self(bound) or other(bound),
            name=f"({self.name} || {other.name})"
        )
    def __xor__(self, other: Constraint) -> Constraint:
        return Constraint(
            run_f=lambda bound: self(bound) ^ other(bound),
            name=f"({self.name} ^ {other.name})"
        )
    def __invert__(self) -> Constraint:
        return Constraint(
            run_f=lambda bound: not self(bound),
            name=f"!({self.name})"
        )        

    @classmethod
    def predicate(cls, f: Callable[..., bool],*, name: Optional[str] = None, quant: Quantifier = Quantifier.FORALL)->Callable[..., Constraint]:
        def wrapper(*args: Any, **kwargs:Any) -> Constraint:
            arg_list = list(args)
            kw_list = [(k, v) for k, v in kwargs.items()]
            def run_f(bound: BoundVar) -> bool:
                # positional argument values
                pos_values = [
                    arg.get(bound) if isinstance(arg, Variable) else (arg,)
                    for arg in arg_list
                ]
                # keyword argument values
                kw_keys, kw_values = zip(*[
                    (k, v.get(bound) if isinstance(v, Variable) else (v,))
                    for k, v in kw_list
                ]) if kw_list else ([], [])

                # Cartesian product over all argument values
                all_combos = product(*pos_values, *kw_values)

                # evaluate predicate on each combination
                def eval_combo(combo):
                    pos_args = combo[:len(pos_values)]
                    kw_args = dict(zip(kw_keys, combo[len(pos_values):]))
                    return f(*pos_args, **kw_args)

                if quant is Quantifier.EXISTS:
                    return any(eval_combo(c) for c in all_combos)
                else:
                    return all(eval_combo(c) for c in all_combos)
            return cls(run_f=run_f, name = name or f.__name__)
        return wrapper

    @classmethod
    def forall(cls, f: Callable[..., bool], name: Optional[str] = None) -> Callable[..., Constraint]:
        return cls.predicate(f, name=name, quant=Quantifier.FORALL)
    
    @classmethod
    def exists(cls, f: Callable[..., bool], name: Optional[str] = None):
        return cls.predicate(f, name=name, quant=Quantifier.EXISTS)



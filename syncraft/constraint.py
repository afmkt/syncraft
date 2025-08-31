from __future__ import annotations
from typing import Callable, Generic, Tuple, TypeVar, Optional, Any, Self
from enum import Enum
from dataclasses import dataclass, field, replace
import collections.abc
from collections import defaultdict
from itertools import product
import inspect

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
class Binding:
    bindings : frozenset[Tuple[str, Any]] = frozenset()
    def bind(self, name: str, node: Any) -> Binding:
        new_binding = set(self.bindings)
        new_binding.add((name, node))
        return Binding(bindings=frozenset(new_binding))
    
    def bound(self)->FrozenDict[str, Tuple[Any, ...]]:
        ret = defaultdict(list)
        for name, node in self.bindings:
            ret[name].append(node)
        return FrozenDict({k: tuple(vs) for k, vs in ret.items()})



@dataclass(frozen=True)
class Bindable:
    binding: Binding = field(default_factory=Binding)

    def map(self, f: Callable[[Any], Any])->Self: 
        return self
    
    def bind(self, name: str, node:Any)->Self:
        return replace(self, binding=self.binding.bind(name, node))


class Quantifier(Enum):
    FORALL = "forall"
    EXISTS = "exists"

@dataclass(frozen=True)
class ConstraintResult:
    result: bool
    unbound: frozenset[str] = frozenset()
@dataclass(frozen=True)
class Constraint:
    run_f: Callable[[FrozenDict[str, Tuple[Any, ...]]], ConstraintResult]
    name: str = ""
    def __call__(self, bound: FrozenDict[str, Tuple[Any, ...]])->ConstraintResult:
        return self.run_f(bound)
    def __and__(self, other: Constraint) -> Constraint:
        def and_run(bound: FrozenDict[str, Tuple[Any, ...]]) -> ConstraintResult:
            res1 = self(bound)
            res2 = other(bound)
            combined_result = res1.result and res2.result
            combined_unbound = res1.unbound.union(res2.unbound)
            return ConstraintResult(result=combined_result, unbound=combined_unbound)
        return Constraint(
            run_f=and_run,
            name=f"({self.name} && {other.name})"
        )
    def __or__(self, other: Constraint) -> Constraint:
        def or_run(bound: FrozenDict[str, Tuple[Any, ...]]) -> ConstraintResult:
            res1 = self(bound)
            res2 = other(bound)
            combined_result = res1.result or res2.result
            combined_unbound = res1.unbound.union(res2.unbound)
            return ConstraintResult(result=combined_result, unbound=combined_unbound)
        return Constraint(
            run_f=or_run,
            name=f"({self.name} || {other.name})"
        )
    def __xor__(self, other: Constraint) -> Constraint:
        def xor_run(bound: FrozenDict[str, Tuple[Any, ...]]) -> ConstraintResult:
            res1 = self(bound)
            res2 = other(bound) 
            combined_result = res1.result ^ res2.result
            combined_unbound = res1.unbound.union(res2.unbound)
            return ConstraintResult(result=combined_result, unbound=combined_unbound)
        return Constraint(
            run_f=xor_run,
            name=f"({self.name} ^ {other.name})"
        )
    def __invert__(self) -> Constraint:
        def invert_run(bound: FrozenDict[str, Tuple[Any, ...]]) -> ConstraintResult:
            res = self(bound)
            return ConstraintResult(result=not res.result, unbound=res.unbound)
        return Constraint(
            run_f=invert_run,
            name=f"!({self.name})"
        )        

    @classmethod
    def predicate(cls, 
                  f: Callable[..., bool],
                  *, 
                  name: Optional[str] = None, 
                  quant: Quantifier = Quantifier.FORALL)->Constraint:
        sig = inspect.signature(f)
        pos_params = []
        kw_params = []
        for pname, param in sig.parameters.items():
            if param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
                pos_params.append(pname)
            elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                kw_params.append(pname)
            else:
                raise TypeError(f"Unsupported parameter kind: {param.kind}")
        def run_f(bound: FrozenDict[str, Tuple[Any, ...]]) -> ConstraintResult:
            # positional argument values
            pos_values = [bound.get(pname, ()) for pname in pos_params]
            # keyword argument values
            kw_values = [bound.get(pname, ()) for pname in kw_params]

            # If any param is unbound, fail
            all_params = pos_params + kw_params
            all_values = pos_values + kw_values
            unbound_args = [p for p, vs in zip(all_params, all_values) if not vs]
            if unbound_args:
                return ConstraintResult(result=quant is Quantifier.FORALL, unbound=frozenset(unbound_args))

            # Cartesian product
            all_combos = product(*pos_values, *kw_values)

            def eval_combo(combo):
                pos_args = combo[: len(pos_values)]
                kw_args = dict(zip(kw_params, combo[len(pos_values) :]))
                return f(*pos_args, **kw_args)

            if quant is Quantifier.EXISTS:
                return ConstraintResult(result = any(eval_combo(c) for c in all_combos), unbound=frozenset())
            else:
                return ConstraintResult(result = all(eval_combo(c) for c in all_combos), unbound=frozenset())

        return cls(run_f=run_f, name=name or f.__name__)

def forall(f: Callable[..., bool], name: Optional[str] = None) -> Constraint:
    return Constraint.predicate(f, name=name, quant=Quantifier.FORALL)
    
def exists(f: Callable[..., bool], name: Optional[str] = None) -> Constraint:
    return Constraint.predicate(f, name=name, quant=Quantifier.EXISTS)



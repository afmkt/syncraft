from __future__ import annotations
from typing import (
    Callable, Tuple, Any, Self, 
    Protocol, runtime_checkable
)
from enum import Enum
from dataclasses import dataclass

from itertools import product
from inspect import Signature
import inspect
from syncraft.ast import SyncraftError
from syncraft.utils import FrozenDict

    
@dataclass(frozen=True, slots=True)
class Binding:
    bindings : FrozenDict[str, Tuple[Any, ...]] = FrozenDict()
    def bind(self, name: str, node: Any) -> Binding:
        old: Any = self.bindings.get(name, ())
        return Binding(bindings=self.bindings.set(name, old + (node,)))
    
    def replace(self, name: str, node: Any) -> Binding:
        return Binding(bindings=self.bindings.set(name, (node,)))



@runtime_checkable
class Bindable(Protocol):
    @property
    def cache_key(self) -> int: ...

    @property
    def all_bindings(self) -> FrozenDict[str, Tuple[Any, ...]]: ...

    def unused_cache_key(self) -> int: ...

    def map(self, f: Callable[[Any], Any])->Self: ...
    
    def bind(self, name: str, node:Any)->Self: ...

    def replace(self, name: str, node:Any)->Self: ...

    def get(self, name: str, unwrapper: bool=True) -> Tuple[Any, ...] | Any: ...

    def enter(self) -> Self: ...
    
    def leave(self) -> Self: ...
    
    @property
    def ended(self) -> bool: ...
        

class Quantifier(Enum):
    FORALL = "forall"
    EXISTS = "exists"

@dataclass(frozen=True, slots=True)
class ConstraintResult:
    result: bool
    unbound: frozenset[str] = frozenset()
@dataclass(frozen=True, slots=True)
class Constraint:
    """A composable boolean check over a set of bound values.

    The check is a function from a mapping of names to tuples of values to a
    ``ConstraintResult`` with a boolean outcome and any unbound requirements.
    unbound names are those required for evaluation but not present in the
    provided bindings.
    Constraints compose with logical operators (``&``, ``|``, ``^``, ``~``).
    """
    run_f: Callable[[Any, FrozenDict[str, Tuple[Any, ...]]], ConstraintResult]
    def __call__(self, value: Any,  bound: FrozenDict[str, Tuple[Any, ...]])->ConstraintResult:
        """Evaluate this constraint against the provided bindings."""
        return self.run_f(value, bound)
    
    def __and__(self, other: Constraint) -> Constraint:
        """Logical AND composition of two constraints."""
        def and_run(value: Any, bound: FrozenDict[str, Tuple[Any, ...]]) -> ConstraintResult:
            res1 = self(value, bound)
            res2 = other(value, bound)
            combined_result = res1.result and res2.result
            combined_unbound = res1.unbound.union(res2.unbound)
            return ConstraintResult(result=combined_result, unbound=combined_unbound)
        return Constraint(run_f=and_run)
    
    def __or__(self, other: Constraint) -> Constraint:
        """Logical OR composition of two constraints."""
        def or_run(value: Any, bound: FrozenDict[str, Tuple[Any, ...]]) -> ConstraintResult:
            res1 = self(value, bound)
            res2 = other(value, bound)
            combined_result = res1.result or res2.result
            combined_unbound = res1.unbound.union(res2.unbound)
            return ConstraintResult(result=combined_result, unbound=combined_unbound)
        return Constraint(run_f=or_run)
    
    def __xor__(self, other: Constraint) -> Constraint:
        """Logical XOR composition of two constraints."""
        def xor_run(value: Any, bound: FrozenDict[str, Tuple[Any, ...]]) -> ConstraintResult:
            res1 = self(value, bound)
            res2 = other(value, bound) 
            combined_result = res1.result ^ res2.result
            combined_unbound = res1.unbound.union(res2.unbound)
            return ConstraintResult(result=combined_result, unbound=combined_unbound)
        return Constraint(run_f=xor_run)
    
    def __invert__(self) -> Constraint:
        """Logical NOT of this constraint."""
        def invert_run(value: Any, bound: FrozenDict[str, Tuple[Any, ...]]) -> ConstraintResult:
            res = self(value, bound)
            return ConstraintResult(result=not res.result, unbound=res.unbound)
        return Constraint(run_f=invert_run)        

    @classmethod
    def predicate(cls, 
                  f: Callable[..., bool],
                  *, 
                  sig: Signature,
                  quant: Quantifier)->Constraint:
        pos_params = []
        kw_params = []
        for pname, param in sig.parameters.items():
            if param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
                pos_params.append(pname)
            elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                kw_params.append(pname)
            else:
                raise SyncraftError(f"Unsupported parameter kind: {param.kind}", 
                                    offender=param.kind, 
                                    expect=(inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY))
                
        def run_f(value: Any, bound: FrozenDict[str, Tuple[Any, ...]]) -> ConstraintResult:
            # positional argument values
            pos_values = [bound.get(pname, ()) for pname in pos_params[1:]]
            # keyword argument values
            kw_values = [bound.get(pname, ()) for pname in kw_params]

            # If any param is unbound, fail
            all_params = pos_params[1:] + kw_params
            all_values = pos_values + kw_values
            unbound_args = [p for p, vs in zip(all_params, all_values) if not vs]
            if unbound_args:
                return ConstraintResult(result=quant is Quantifier.FORALL, unbound=frozenset(unbound_args))

            # Cartesian product
            all_combos = product(*pos_values, *kw_values)

            def eval_combo(combo):
                pos_args = combo[: len(pos_values)]
                kw_args = dict(zip(kw_params, combo[len(pos_values) :]))
                return f(value, *pos_args, **kw_args)

            if quant is Quantifier.EXISTS:
                return ConstraintResult(result = any(eval_combo(c) for c in all_combos), unbound=frozenset())
            else:
                return ConstraintResult(result = all(eval_combo(c) for c in all_combos), unbound=frozenset())

        return cls(run_f=run_f)




def forall(f: Callable[..., bool]) -> Constraint:
    """``forall`` wrapper around ``predicate`` (all combinations must satisfy)."""
    sig = inspect.signature(f)    
    return Constraint.predicate(f, sig=sig, quant=Quantifier.FORALL)
    
    
def exists(f: Callable[..., bool]) -> Constraint:
    """``exists`` wrapper around ``predicate`` (at least one combination)."""
    sig = inspect.signature(f)    
    return Constraint.predicate(f, sig=sig, quant=Quantifier.EXISTS)






from __future__ import annotations
from typing import Callable, Generic, Tuple, TypeVar, Optional, Any, Self
from enum import Enum
from dataclasses import dataclass, field, replace
import collections.abc
from collections import defaultdict
from itertools import product
from inspect import Signature
import inspect

K = TypeVar('K')
V = TypeVar('V')
class FrozenDict(collections.abc.Mapping, Generic[K, V]):
    """An immutable, hashable mapping.

    Behaves like a read-only dict and caches its hash, making it suitable as a
    key in other dictionaries or for set membership. Equality compares the
    underlying mapping to any other Mapping.
    """
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
    """Mixin that carries named bindings produced during evaluation.

    Instances accumulate bindings of name->node pairs. Subclasses should return
    a new instance from ``bind`` to preserve immutability.
    """
    binding: Binding = field(default_factory=Binding)

    def map(self, f: Callable[[Any], Any])->Self: 
        """Optionally transform the underlying value (no-op by default)."""
        return self
    
    def bind(self, name: str, node:Any)->Self:
        """Return a copy with ``node`` recorded under ``name`` in bindings."""
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
    """A composable boolean check over a set of bound values.

    The check is a function from a mapping of names to tuples of values to a
    ``ConstraintResult`` with a boolean outcome and any unbound requirements.
    Constraints compose with logical operators (``&``, ``|``, ``^``, ``~``).
    """
    run_f: Callable[[FrozenDict[str, Tuple[Any, ...]]], ConstraintResult]
    name: str = ""
    def __call__(self, bound: FrozenDict[str, Tuple[Any, ...]])->ConstraintResult:
        """Evaluate this constraint against the provided bindings."""
        return self.run_f(bound)
    def __and__(self, other: Constraint) -> Constraint:
        """Logical AND composition of two constraints."""
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
        """Logical OR composition of two constraints."""
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
        """Logical XOR composition of two constraints."""
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
        """Logical NOT of this constraint."""
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
                  sig: Signature,
                  name: str, 
                  quant: Quantifier)->Constraint:
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

        return cls(run_f=run_f, name=name)


def predicate(f: Callable[..., bool], 
              *, 
              name: Optional[str] = None, 
              quant: Quantifier = Quantifier.FORALL, 
              bimap: bool = True) -> Constraint:
    """Create a constraint from a Python predicate function.

    The predicate's parameters define the required bindings. When ``bimap`` is
    true, arguments with a ``bimap()`` method are mapped to their forward value
    before evaluation, making it convenient to write predicates over AST values.

    Args:
        f: The boolean function to wrap as a constraint.
        name: Optional human-friendly name; defaults to ``f.__name__``.
        quant: Quantification over bound values (forall or exists).
        bimap: Whether to call ``bimap()`` on arguments before evaluation.

    Returns:
        Constraint: A composable constraint.
    """
    name = name or f.__name__
    sig = inspect.signature(f)
    if bimap:
        def wrapper(*args: Any, **kwargs:Any) -> bool:
            mapped_args = [a.bimap()[0] if hasattr(a, "bimap") else a for a in args]
            mapped_kwargs = {k: (v.bimap()[0] if hasattr(v, "bimap") else v) for k,v in kwargs.items()}
            return f(*mapped_args, **mapped_kwargs)
        
        return Constraint.predicate(wrapper, sig=sig, name=name, quant=quant)
    else:
        return Constraint.predicate(f, sig=sig, name=name, quant=quant)

def forall(f: Callable[..., bool], name: Optional[str] = None, bimap: bool=True) -> Constraint:
    """``forall`` wrapper around ``predicate`` (all combinations must satisfy)."""
    return predicate(f, name=name, quant=Quantifier.FORALL, bimap=bimap)
    
def exists(f: Callable[..., bool], name: Optional[str] = None, bimap:bool = True) -> Constraint:
    """``exists`` wrapper around ``predicate`` (at least one combination)."""
    return predicate(f, name=name, quant=Quantifier.EXISTS, bimap=bimap)




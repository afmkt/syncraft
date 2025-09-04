from __future__ import annotations
from typing import (
    Callable, Generic, Tuple, TypeVar, Optional, Any, Self, 
    Generator, List, Set, Union, Dict, Iterable,
)
from enum import Enum
from dataclasses import dataclass, field, replace, is_dataclass, fields
import collections.abc
from collections import defaultdict
from itertools import product
from inspect import Signature
import inspect
from syncraft.ast import SyncraftError
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
                raise SyncraftError(f"Unsupported parameter kind: {param.kind}", 
                                    offending=param.kind, 
                                    expect=(inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY))
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



def all_binding(a: FrozenDict[str, Tuple[Any, ...]], *names: str) -> Generator[FrozenDict[str, Any], None, None]:
    """Yield all combinations of the provided bindings."""
    if a:
        names = tuple(a.keys()) if not names else names 
        values = [a[name] for name in names]
        for combo in product(*values):
            yield FrozenDict({name: value for name, value in zip(names, combo)})


    

####################################################################################################################################
@dataclass(frozen=True)
class Var:
    name: str


Subst = Dict[str, Any]
Fact = Tuple[str, Tuple[Any, ...]]
Rule = Tuple[str, Tuple[Any, ...], List[Fact]]

def is_var(x): return isinstance(x, Var)

# ---------- Unification ----------
def unify(x, y, subst: Subst) -> Subst | None:
    if x == y:
        return subst
    if is_var(x):
        return unify_var(x, y, subst)
    if is_var(y):
        return unify_var(y, x, subst)
    if isinstance(x, tuple) and isinstance(y, tuple) and len(x) == len(y):
        for a, b in zip(x, y):
            tmp = unify(a, b, subst)
            if tmp is None:
                return None
            else: 
                subst = tmp
        return subst
    return None

def unify_var(var: Var, val: Any, subst: Subst) -> Subst | None:
    if var.name in subst:
        return unify(subst[var.name], val, subst)
    if occurs_check(var, val, subst):
        return None
    subst = subst.copy()
    subst[var.name] = val
    return subst

def occurs_check(var: Var, val: Any, subst: Subst) -> bool:
    if var == val: 
        return True
    if is_var(val) and val.name in subst:
        return occurs_check(var, subst[val.name], subst)
    if isinstance(val, tuple):
        return any(occurs_check(var, v, subst) for v in val)
    return False

# ---------- Substitution ----------
def apply_subst_fact(fact: Fact, subst: Subst) -> Fact:
    pred, args = fact
    return (pred, tuple(apply_subst_term(a, subst) for a in args))

def apply_subst_term(term, subst: Subst):
    if is_var(term) and term.name in subst:
        return apply_subst_term(subst[term.name], subst)
    return term

# ---------- Engine ----------
class DatalogEngine:
    def __init__(self):
        self.facts: List[Fact] = []
        self.rules: List[Rule] = []

    def add_fact(self, fact: Fact):
        self.facts.append(fact)

    def add_rule(self, head: Fact, body: List[Fact]):
        self.rules.append((head[0], head[1], body))

    # ----- Forward chaining -----
    def infer(self) -> List[Fact]:
        changed = True
        inferred = set(self.facts)
        while changed:
            changed = False
            for (hpred, hargs, body) in self.rules:
                for subst in self._prove_body(body, {}):
                    head = apply_subst_fact((hpred, hargs), subst)
                    if head not in inferred:
                        inferred.add(head)
                        changed = True
        return list(inferred)

    # ----- Backward chaining -----
    def query(self, goal: Fact, subst: Subst | None = None) -> Generator[Subst, None, None]:
        if subst is None:
            subst = {}
        pred, args = goal

        # Match against facts
        for (fpred, fargs) in self.facts:
            if fpred != pred: 
                continue
            s = unify(args, fargs, subst)
            if s is not None:
                yield s

        # Match against rules
        for (hpred, hargs, body) in self.rules:
            if hpred != pred: 
                continue
            s = unify(args, hargs, subst)
            if s is None: 
                continue
            yield from self._prove_body(body, s)

    def _prove_body(self, goals: List[Fact], subst: Subst) -> Generator[Subst, None, None]:
        if not goals:
            yield subst
            return
        first, *rest = goals
        for s in self.query(apply_subst_fact(first, subst), subst):
            yield from self._prove_body(rest, s)

#####################################################################################################################################
def dataclass_to_facts(obj: Any, *, extended: bool = False, parent: Any = None) -> List[Fact]:
    facts: List[Fact] = []

    if not is_dataclass(obj):
        raise TypeError(f"Expected dataclass instance, got {type(obj)}")

    cls = type(obj)
    pred = cls.__name__  # use class name as predicate
    args = tuple(getattr(obj, f.name) for f in fields(obj))
    facts.append((pred, args))

    for f in fields(obj):
        val = getattr(obj, f.name)

        if is_dataclass(val):
            # recurse into child dataclass
            facts.extend(dataclass_to_facts(val, extended=extended, parent=obj))

            if extended:
                facts.append(("Contains", (obj, val)))
                facts.append(("Field", (obj, f.name, val)))

        elif isinstance(val, list):
            for item in val:
                if is_dataclass(item):
                    facts.extend(dataclass_to_facts(item, extended=extended, parent=obj))
                    if extended:
                        facts.append(("Contains", (obj, item)))
                        facts.append(("Field", (obj, f.name, item)))
                else:
                    if extended:
                        facts.append(("Field", (obj, f.name, item)))
        else:
            if extended:
                facts.append(("Field", (obj, f.name, val)))

    return facts



def test()->None:
    X, Y, Z = Var("X"), Var("Y"), Var("Z")

    db = DatalogEngine()
    db.add_fact(("parent", ("alice", "bob")))
    db.add_fact(("parent", ("bob", "carol")))

    # Rules
    db.add_rule(("ancestor", (X, Y)), [("parent", (X, Y))])
    db.add_rule(("ancestor", (X, Y)), [("parent", (X, Z)), ("ancestor", (Z, Y))])

    print("Forward infer:")
    print(db.infer())
    # [('parent', ('alice', 'bob')), ('parent', ('bob', 'carol')), 
    #  ('ancestor', ('alice', 'bob')), ('ancestor', ('bob', 'carol')), 
    #  ('ancestor', ('alice', 'carol'))]

    print("Backward query:")
    print(list(db.query(("ancestor", (X, "carol")))))
    # [{'X': 'bob'}, {'X': 'alice'}]

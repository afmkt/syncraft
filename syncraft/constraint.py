from __future__ import annotations
from typing import Callable, Generic, Tuple, TypeVar, Optional, Any, Protocol
from enum import Enum
from dataclasses import dataclass
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
class Variable:
    name: str



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

class Bindable(Protocol):
    binding: Binding
    def bind(self, var: Variable, node: Any) -> Any: ...


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
                    bound.get(arg, ()) if isinstance(arg, Variable) else (arg,)
                    for arg in arg_list
                ]
                # keyword argument values
                kw_keys, kw_values = zip(*[
                    (k, bound.get(v, ()) if isinstance(v, Variable) else (v,))
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


"""

# -----------------------------
# Variable with projection
# -----------------------------
@dataclass(frozen=True)
class Variable:
    name: str
    projector: Callable[[Any], Any] = lambda x: x

    def map(self, f: Callable[[Any], Any]) -> "Variable":
        return Variable(self.name, lambda x: f(self.projector(x)))



# Helper proxy to capture variable access
class _BindingProxy:
    def __init__(self, binding, captured_vars):
        self._binding = binding
        self._captured_vars = captured_vars

    def __getitem__(self, var: Variable):
        self._captured_vars.add(var)
        return self._binding[var]


# -----------------------------
# DSL operator overloads for Variable
# -----------------------------
def _binary_op(a: Variable, b, op: Callable[[Any, Any], bool], quant=forall):
    b_expr = b if isinstance(b, Variable) else b
    return quant((a,) if not isinstance(b, Variable) else (a,b),
                 lambda *vals: op(*vals),
                 name=f"({a.name} {op.__name__} {getattr(b,'name',b)})")

Variable.__lt__ = lambda self, other: _binary_op(self, other, lambda x, y: x < y)
Variable.__le__ = lambda self, other: _binary_op(self, other, lambda x, y: x <= y)
Variable.__gt__ = lambda self, other: _binary_op(self, other, lambda x, y: x > y)
Variable.__ge__ = lambda self, other: _binary_op(self, other, lambda x, y: x >= y)
Variable.__eq__ = lambda self, other: _binary_op(self, other, lambda x, y: x == y)

# -----------------------------
# Demo
# -----------------------------
if __name__ == "__main__":
    # define variables with projection
    x = Variable("x").map(lambda t: int(t.text))
    y = Variable("y").map(lambda t: int(t.text))

    # fake parser state
    state = ParserState()
    state.bind(x, Token("5"))
    state.bind(x, Token("10"))
    state.bind(y, Token("7"))

    # constraints from DSL
    c1 = x > 0          # forall x>0
    c2 = exists((x, y), lambda a, b: a < b, "x<y")  # exists x,y: a<b

    c = c1 & c2

    print("Check:", c(state.binding))   # True
    print("Variables:", [v.name for v in c.variables])


"""    
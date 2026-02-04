from __future__ import annotations


from typing import (
    Any, TypeVar, Tuple, Set, Dict, List,
    Generic, Callable, overload, Literal
)

from dataclasses import dataclass, field, is_dataclass, fields
from syncraft.utils import FrozenDict



A = TypeVar('A')
B = TypeVar('B')  
C = TypeVar('C')  
    
def identity(x: Any) -> Any:
    return x

@dataclass(frozen=True, slots=True)
class Iso(Generic[A, B]):
    forward: Callable[[A], B] = field(default=identity)
    inverse: Callable[[B], A] = field(default=identity)


    def __iter__(self):
        yield from (self.forward, self.inverse)

    def __len__(self) -> int:
        return 2
    

    @overload
    def __getitem__(self, index: Literal[0]) -> Callable[[A], B]: ...
    @overload
    def __getitem__(self, index: Literal[1]) -> Callable[[B], A]: ...
    def __getitem__(self, index: int | slice) -> Any:
        if index == 0:
            return self.forward
        elif index == 1:
            return self.inverse
        else:
            raise IndexError("Index out of range for Iso, valid indices are 0 and 1")

    def fmap(self, a : A) -> B:
        return self.forward(a)
    
    def imap(self, b : B) -> A:
        return self.inverse(b)

    def __rshift__(self, other: Iso[B, C]) -> Iso[A, C]:
        return Iso(lambda a: other.forward(self.forward(a)),
                   lambda c: self.inverse(other.inverse(c)))

    def __rrshift__(self, other: Iso[C, A]) -> Iso[C, B]:
        return Iso(lambda c: self.forward(other.forward(c)),
                   lambda b: other.inverse(self.inverse(b)))
    
    def __neg__(self) -> Iso[B, A]:
        return Iso(self.inverse, self.forward)

    @classmethod
    def const(cls, a: A, b: B) -> Iso[A, B]:
        return cls(lambda _: b, lambda _: a)
    



def _default_eval(msg: str) -> Callable[[Env, Set[Any]], Tuple[bool, Any]]:
    def default_eval(env: Env, visited: Set[Any]) -> Tuple[bool, Any]:
        raise TypeError(f"Expression not fully defined: {msg}")
    return default_eval
    
@dataclass(frozen=True, slots=True, eq=False)
class Expr:
    expr: Callable[[Env, Set[Any]], Tuple[bool, Any]] = field(compare=False, hash=False, repr=False)
    def evaluate(self, env: Env, visited: Set[Any]) -> Tuple[bool, Any]:
        if self in visited:
            return False, self
        visited.add(self)
        return self.expr(env, visited)
    
    def bind(self, env: Env, value: Any) -> bool:
        env.constraints.add(Constraint(self, value))
        return True
        
    
    def unify(self, other: Any, env: Env) -> bool:
        return self.bind(env, other)

    
    def _bin_op(self, other: Any, op: Callable[[Any, Any], Any], flip: bool = False) -> Expr:
        def expr_f(env: Env, visited: Set[Any]) -> Tuple[bool, Any]:
            full1, v1 = self.evaluate(env, visited)
            if not full1:
                return False, self
            full2, v2 = evaluate(other, env, visited)
            if not full2:
                return False, other
            return (True, op(v2, v1) if flip else op(v1, v2))
        return Expr(expr_f)
    
    def _unary_op(self, op: Callable[[Any], Any]) -> Expr:
        def expr_f(env: Env, visited: Set[Any]) -> Tuple[bool, Any]:
            full, v = self.evaluate(env, visited)
            if not full:
                return False, self
            return (True, op(v))
        return Expr(expr_f)

    # function call operator
    def __call__(self, *args: Any, **kwargs: Any) -> Expr:
        def expr_f(env: Env, visited: Set[Any]) -> Tuple[bool, Any]:
            full, func = self.evaluate(env, visited)
            if not full:
                return False, self
            evaluated_args = []
            for arg in args:
                full_arg, v_arg = evaluate(arg, env, visited)
                if not full_arg:
                    return False, arg
                evaluated_args.append(v_arg)
            evaluated_kwargs = {}
            for k, v in kwargs.items():
                full_kwarg, v_kwarg = evaluate(v, env, visited)
                if not full_kwarg:
                    return False, v
                evaluated_kwargs[k] = v_kwarg
            return (True, func(*evaluated_args, **evaluated_kwargs))
        return Expr(expr_f)

    @classmethod
    def apply(cls, func: Callable[..., Any], *args, **kwargs) -> Expr:
        def expr_f(env: Env, visited: Set[Any]) -> Tuple[bool, Any]:
            evaluated_args = []
            for arg in args:
                full_arg, v_arg = evaluate(arg, env, visited)
                if not full_arg:
                    return False, arg
                evaluated_args.append(v_arg)
            evaluated_kwargs = {}
            for k, v in kwargs.items(): 
                full_kwarg, v_kwarg = evaluate(v, env, visited)
                if not full_kwarg:
                    return False, v
                evaluated_kwargs[k] = v_kwarg
            return (True, func(*evaluated_args, **evaluated_kwargs))
        return Expr(expr_f)
    
    # Container & Utility Operators
    def __getitem__(self, key: Any) -> Expr:
        return self._unary_op(lambda v: v[key])
    
    def __contains__(self, item: Any) -> Expr:
        return self._unary_op(lambda v: item in v)
    
    def __len__(self) -> Any:
        return self._unary_op(lambda v: len(v))
    
    # Arithmetic Operators
    def __add__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v1 + v2)
    
    def __radd__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v2 + v1, flip=True)
    
    def __sub__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v1 - v2)
    
    def __rsub__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v2 - v1, flip=True)
    
    def __mul__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v1 * v2)
    
    def __rmul__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v2 * v1, flip=True)
    
    def __truediv__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v1 / v2)
    
    def __rtruediv__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v2 / v1, flip=True)
    
    def __floordiv__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v1 // v2)
    
    def __rfloordiv__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v2 // v1, flip=True)
    
    def __mod__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v1 % v2)
    
    def __rmod__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v2 % v1, flip=True)
    
    def __pow__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v1 ** v2)
    
    def __rpow__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v2 ** v1, flip=True)
    
    # Comparison Operators
    def eq(self, other: Any) -> Expr: # type: ignore[override]
        return self._bin_op(other, lambda v1, v2: v1 == v2)
    
    def ne(self, other: Any) -> Expr: # type: ignore[override]
        return self._bin_op(other, lambda v1, v2: v1 != v2)


    def __lt__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v1 < v2)
    
    def __le__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v1 <= v2)
    
    def __gt__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v1 > v2)
        
    def __ge__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v1 >= v2)


    # logical operators
    def __and__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v1 & v2)
    
    def __rand__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v2 & v1, flip=True)
    
    def __or__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v1 | v2)
    
    def __ror__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v2 | v1, flip=True)
    
    def __invert__(self) -> Expr:
        return self._unary_op(lambda v: ~v)
    
    def __neg__(self) -> Expr:
        return self._unary_op(lambda v: -v)
    
    def __pos__(self) -> Expr:
        return self._unary_op(lambda v: +v)
    
    def __abs__(self) -> Expr:
        return self._unary_op(lambda v: abs(v))
    
    def __xor__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v1 ^ v2)
    
    def __rxor__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v2 ^ v1, flip=True)
    
    def __lshift__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v1 << v2)
    
    def __rlshift__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v2 << v1, flip=True)
    
    def __rshift__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v1 >> v2)
    
    def __rrshift__(self, other: Any) -> Expr:
        return self._bin_op(other, lambda v1, v2: v2 >> v1, flip=True)
    


@dataclass(frozen=True, slots=True, eq=False)
class Var(Expr):
    name: str | None = None
    def __post_init__(self):
        def expr_f(env: Env, visited: Set[Any]) -> Tuple[bool, Any]:
            if self.is_bound(env):
                resolved = env.resolve(self)
                if resolved is ...:
                    return False, self
                else:
                    return evaluate(resolved, env, visited)
            else:
                return False, self
        object.__setattr__(self, 'expr', expr_f)

    def is_bound(self, env: Env) -> bool:
        return self in env.bindings and env.bindings[self].value is not ...
    
    def bind(self, env: Env, value: Any) -> bool:
        return env.bind(self, value) is not None

    def unify(self, other: Any, env: Env) -> bool:
        return env.bind(self, other) is not None
            


@dataclass(frozen=True, slots=True, eq=False)
class Let(Expr):
    var: Var = field(default_factory=lambda: Var(_default_eval('Var')), compare=False, hash=False)
    body: Expr = field(default_factory=lambda: Expr(_default_eval('Expr')), compare=False, hash=False)

    def __post_init__(self):
        def expr_f(env: Env, visited: Set[Any]) -> Tuple[bool, Any]:
            return evaluate(self.body, env, visited)
        object.__setattr__(self, 'expr', expr_f)

    def unify(self, target: Any, env: Env) -> bool:
        if not unify(self.var, target, env):
            return False
        env.constraints.add(Constraint(self, target))
        return True

def let(var: Var, rhs: Any) -> Let:
    return Let(lambda env, visited: (False, ...), var, rhs)


@dataclass(slots=True)
class Binding:
    value: Any = ...


@dataclass(frozen=True, slots=True)
class Constraint:
    """
    Docstring for Constraint
    False, _ if not fully evaluated
    True, False if constraint failed
    True, True if constraint succeeded
    """
    expr: Expr
    expected: Any = field(compare=False, hash=False)
    _val_hash: int = field(init=False, repr=False)

    def __post_init__(self):
        def structural_hash(v: Any) -> int:
            """Recursively computes a hash for unhashable structures."""
            if isinstance(v, (list, tuple)):
                return hash(tuple(structural_hash(i) for i in v))
            if isinstance(v, dict):
                # Sort items to ensure stable hashing for dictionaries
                return hash(tuple(sorted((k, structural_hash(val)) for k, val in v.items())))
            if is_dataclass(v):
                return hash(tuple((f.name, structural_hash(getattr(v, f.name))) for f in fields(v)))
            if isinstance(v, (set, frozenset)):
                return hash(tuple(sorted(structural_hash(i) for i in v)))
            return hash(v)        
        object.__setattr__(self, '_val_hash', structural_hash(self.expected))

    def __call__(self, env: Env, visited: Set[Any]) -> Tuple[bool, bool | Any]:
        full, v = self.expr.evaluate(env, visited)
        if not full:
            return False, self.expr
        full_v, result_v = evaluate(self.expected, env, visited)
        if not full_v:
            return False, self.expected
        return True, unify(v, result_v, env)

@dataclass(slots=True)
class Env:
    constants: FrozenDict[str, Any] = field(default_factory=FrozenDict) 
    bindings: dict[Var, Binding] = field(default_factory=dict)
    
    constraints: Set[Constraint] = field(default_factory=set)
    changed: bool = False
    
        
    def __contains__(self, var: Var) -> bool:
        return var in self.bindings
    
    def resolve(self, var: Var) -> Any:
        ret = self.bindings.get(var, ...)
        if ret is ...:
            return self.constants.get(var.name, ...)
        else:
            return ret.value
        
    def bind(self, var: Var, value: Any) -> Binding | None:
        if var in self.bindings:
            binding = self.bindings[var]
            if binding.value is not ...:

                if not unify(binding.value, value, self):
                    return None
            else:
                binding.value = value

        else:
            binding = Binding(value=value)
            self.bindings[var] = binding
        self.changed = True
        return binding
    

    def solve(self)-> Tuple[bool, List[Any]]:
        self.changed = True
        satisfied = set()
        while self.changed:
            self.changed = False
            for c in list(self.constraints):
                full, result = c(self, set())
                if not full:
                    continue
                if result is False:
                    return False, [(c, "Constraint evaluated to False")]
                else:
                    satisfied.add(c)
        for c in self.constraints:
            if c not in satisfied:
                return False, [(c, "Constraint could not be fully evaluated")]
        return True, []

@dataclass(slots=True)
class Scope:
    pool: Dict[str, Var] = field(default_factory=dict)
    def __getattr__(self, name: str) -> Var:
        if name not in self.pool:
            self.pool[name] = Var(_default_eval('Var'), name=name)
        return self.pool[name]


def is_primitive(value: Any) -> bool:
    return isinstance(value, (int, float, str, bool, bytes, type(None)))



def is_variable(value: Any) -> bool:
    return isinstance(value, Var)

def is_struct(value: Any) -> bool:
    return isinstance(value, (dict, list, tuple)) or is_dataclass(value) 


def evaluate(expr: Any, env: Env, visited: Set[Any]) -> Tuple[bool, Any]:
    if isinstance(expr, Expr):
        return expr.evaluate(env, visited)
    elif is_struct(expr):
        result = {}
        if isinstance(expr, dict):
            for k, v in expr.items():
                full, val = evaluate(v, env, visited)
                if not full:
                    return False, expr
                result[k] = val
            return True, result
        elif isinstance(expr, list):
            lst = []
            for item in expr:
                full, v = evaluate(item, env, visited)
                if not full:
                    return False, expr
                lst.append(v)
            return True, lst
        elif isinstance(expr, tuple):
            tpl = []
            for item in expr:
                full, v = evaluate(item, env, visited)
                if not full:
                    return False, expr
                tpl.append(v)
            return True, tuple(tpl)
        elif is_dataclass(expr):
            all_fields = {}
            for field in fields(expr):
                full, v = evaluate(getattr(expr, field.name), env, visited)
                if not full:
                    return False, expr
                all_fields[field.name] = v
            return True, type(expr)(**all_fields) # type: ignore
    return True, expr
    
def unify(pattern: Any, value: Any, env: Env) -> bool:
    if pattern is ... or value is ...:
        raise ValueError("Cannot unify with Unbound(...) pattern.")
    elif isinstance(pattern, Expr):
        return pattern.unify(value, env)
    elif isinstance(value, Expr):
        return value.unify(pattern, env)
    
    elif is_primitive(pattern):
        if is_primitive(value):
            if isinstance(pattern, float) and isinstance(value, float):
                import math
                return math.isclose(pattern, value, rel_tol=1e-9)
            else:
                return pattern == value
        else:
            return False

    elif is_struct(pattern):
        if isinstance(pattern, dict) and isinstance(value, dict):
            for k, v in pattern.items():
                if k not in value:
                    return False
                if not unify(v, value[k], env):
                    return False
            return True
        elif isinstance(pattern, (list, tuple)) and isinstance(value, (list, tuple)):
            for p_item, v_item in zip(pattern, value):
                if not unify(p_item, v_item, env):
                    return False
            return True
        elif is_dataclass(pattern) and is_dataclass(value):
            for field in fields(pattern):
                p_item = getattr(pattern, field.name)
                v_item = getattr(value, field.name)
                if not unify(p_item, v_item, env):
                    return False
            return True

    raise ValueError("Unsupported pattern or value type for unification.")



def unify_all(pattern: Any, value: Any, env: Env | None = None) -> Env:
    if env is None:
        env = Env()
    success = unify(pattern, value, env)
    if not success:
        raise ValueError("Unification failed.")
    success, reason = env.solve()
    if not success:
        raise ValueError(f"Constraints not satisfied after unification: {reason}")
    return env





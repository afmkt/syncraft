from __future__ import annotations


from typing import (
    Any, TypeVar, Tuple, List, Set,
    Generic, Callable, overload, Literal
)
from abc import ABC, abstractmethod
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
    
    




class Term(ABC):
    @abstractmethod
    def bind(self, env: Env, value: Any) -> bool:
        ...

    @abstractmethod
    def eval(self, env: Env) -> Tuple[bool, Any]:
        ...

    @abstractmethod
    def unify(self, other: Any, env: Env) -> bool:
        ...




@dataclass(frozen=True, slots=True)
class Var(Term):
    name: str | None = None
    def is_bound(self, env: Env) -> bool:
        return self in env.bindings and env.bindings[self].value is not ...
    
    def bind(self, env: Env, value: Any) -> bool:
        binding = env.bind(self, value)
        return binding is not None
    
    def eval(self, env: Env) -> Tuple[bool, Any]:
        if self.is_bound(env):
            resolved = env.resolve(self)
            if resolved is ...:
                return False, self
            else:
                full, v = eval(resolved, env)
                return full, v
        else:
            return False, self
        
    def unify(self, other: Any, env: Env) -> bool:
        return env.bind(self, other) is not None
    
    

@dataclass(frozen=True, slots=True)
class Fun(Term):
    target: Var
    func: Callable[..., Any]
    args: tuple[Any, ...]

    def bind(self, env: Env, value: Any) -> bool:
        binding = env.bind(self.target, value)
        if binding is None:
            return False
        binding.constraints.append(self)
        return binding is not None
    
    def eval(self, env: Env) -> Tuple[bool, Any]:
        collected_args = []
        for arg in self.args:
            full, v = eval(arg, env)
            if not full:
                return False, self
            collected_args.append(v)
        return True, self.func(*collected_args)
    
    def unify(self, other: Any, env: Env) -> bool:
        return self.bind(env, other)



@dataclass(slots=True)
class Binding:
    value: Any = ...
    constraints: List[Fun] = field(default_factory=list)
    satisfied: Set[int] = field(default_factory=set)

@dataclass(slots=True)
class Env:
    constants: FrozenDict[str, Any] = field(default_factory=FrozenDict) 
    bindings: dict[Var, Binding] = field(default_factory=dict)
    scope: dict[str, Var] = field(default_factory=dict)
    
    
    def __getattr__(self, name: str) -> Var:
        if name not in self.scope:
            self.scope[name] = Var(name)
        return self.scope[name]
        
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
                assert not is_fun(binding.value), "Binding.value cannot be a Fun"
                if not unify(binding.value, value, self):
                    return None
            else:
                binding.value = value
            return binding
        else:
            binding = Binding(value=value)
            self.bindings[var] = binding
            return binding
    

    def solve(self)-> bool:
        changed = True
        while changed:
            changed = False
            for var, binding in self.bindings.items():
                for fun in binding.constraints:
                    full, value = eval(fun, self)
                    if not full:
                        continue
                    if binding.value is not ...:
                        if not unify(fun.target, value, self):
                            return False
                    else:
                        binding.value = value
                        changed = True
                    binding.satisfied.add(id(fun))
        for var, binding in self.bindings.items():
            for fun in binding.constraints:
                if id(fun) not in binding.satisfied:
                    return False
        return True

def is_primitive(value: Any) -> bool:
    return isinstance(value, (int, float, str, bool, bytes, type(None)))

def is_fun(value: Any) -> bool:
    return isinstance(value, Fun)

def is_variable(value: Any) -> bool:
    return isinstance(value, Var)

def is_struct(value: Any) -> bool:
    return isinstance(value, (dict, list, tuple)) or is_dataclass(value) 


def eval(expr: Any, env: Env) -> Tuple[bool, Any]:
    if isinstance(expr, Term):
        return expr.eval(env)
    elif is_struct(expr):
        result = {}
        if isinstance(expr, dict):
            for k, v in expr.items():
                full, val = eval(v, env)
                if not full:
                    return False, expr
                result[k] = val
            return True, result
        elif isinstance(expr, list):
            lst = []
            for item in expr:
                full, v = eval(item, env)
                if not full:
                    return False, expr
                lst.append(v)
            return True, lst
        elif isinstance(expr, tuple):
            tpl = []
            for item in expr:
                full, v = eval(item, env)
                if not full:
                    return False, expr
                tpl.append(v)
            return True, tuple(tpl)
        elif is_dataclass(expr):
            all_fields = {}
            for field in fields(expr):
                full, v = eval(getattr(expr, field.name), env)
                if not full:
                    return False, expr
                all_fields[field.name] = v
            return True, type(expr)(**all_fields) # type: ignore
    return True, expr
    
def unify(pattern: Any, value: Any, env: Env) -> bool:
    if pattern is ... or value is ...:
        raise ValueError("Cannot unify with Unbound(...) pattern.")
    elif isinstance(pattern, Term):
        return pattern.unify(value, env)

    elif is_primitive(pattern):
        if is_primitive(value):
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



def unify_all(pattern: Any, value: Any) -> Env:
    # from rich import print
    env = Env()
    success = unify(pattern, value, env)
    # print(env)
    if not success:
        raise ValueError("Unification failed.")
    if not env.solve():
        raise ValueError("Constraints not satisfied after unification.")
    return env



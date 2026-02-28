"""
Docstring for syncraft.bimap
No occur-check, the visited set will prevent infinite recursion
list/tuple is prefix matching
Expr.eq/Expr.ne for lifting equality
... means Unbound
"""
from __future__ import annotations


from typing import (
    Any, TypeVar, Tuple, Set, Dict, List, Generator,
    Generic, Callable, overload, Literal, Self
)

from dataclasses import dataclass, field, is_dataclass, fields, replace
from syncraft.utils import FrozenDict, CallWith
from abc import ABC, abstractmethod


class DataError(Exception):
    def __init__(self, message: str, reason: list[Any] | None = None, *, soft_failure: bool = False):
        super().__init__(message)
        self.reason = reason
        self.soft_failure = soft_failure
        self.rule: str | None = None
        self.file: str | None = None
        self.line: int | None = None

    def __str__(self) -> str:
        base = super().__str__()
        if self.reason:
            reason_str = "\nReason:\n" + "\n".join(f"- {r}" for r in self.reason)
            location_str = f"({self.file}:{self.line})" if self.file and self.line else "(?)"
            return f"{base}\n{reason_str}\n{location_str} at {self.rule}"
        location_str = f"({self.file}:{self.line})" if self.file and self.line else "(?)"
        return f"{base} at {self.rule} {location_str}"
        

@dataclass(frozen=True, slots=True) 
class Bindable(ABC):
    ctx: FrozenDict = field(default_factory=FrozenDict)

    def get(self, name: str, default: Any = ...) -> Any:
        return self.ctx.get(name, default)
    
    def bind(self, value: Any, **trans: Callable[[Any, Any], Any] | Any) -> Self:
        new_ctx = self.ctx
        for name, f in trans.items():
            if callable(f):
                old = new_ctx.get(name, ...)
                new_ctx = new_ctx.set(name, f(value, old))
            elif name not in new_ctx:
                new_ctx = new_ctx.set(name, f)
            else:
                raise ValueError(f"Cannot bind {name} to {f} because it is already bound to {new_ctx[name]}")

        return replace(self, ctx=new_ctx)

    @property
    @abstractmethod
    def cache_key(self) -> int: ...

    @abstractmethod
    def unused_cache_key(self) -> int: ...

    def apply(self, f: Callable[..., Any])->Self: 
        return self
        
    @abstractmethod
    def enter(self) -> Self: ...
    
    @abstractmethod
    def leave(self) -> Self: ...
    
    @property
    @abstractmethod
    def ended(self) -> bool: ...

    @abstractmethod
    def str_input(self, ul: bool) -> str: ...



A = TypeVar('A')
B = TypeVar('B')  
C = TypeVar('C')  
    
def identity(x: Any, _: Any) -> Any:
    return x

@dataclass(frozen=True, slots=True)
class Iso(Generic[A, B]):
    forward: Callable[[A, Any], B] = field(default=identity)
    inverse: Callable[[B, Any], A] = field(default=identity)


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

    def fmap(self, a : A, ctx: Any) -> B:
        return self.forward(a, ctx)
    
    def imap(self, b : B, ctx: Any) -> A:
        return self.inverse(b, ctx)
    
    def __rshift__(self, other: Iso[B, C]) -> Iso[A, C]:
        return Iso(lambda a, ctx: other.forward(self.forward(a, ctx), ctx),
                   lambda c, ctx: self.inverse(other.inverse(c, ctx), ctx))

    def __rrshift__(self, other: Iso[C, A]) -> Iso[C, B]:
        return Iso(lambda c, ctx: self.forward(other.forward(c, ctx), ctx),
                   lambda b, ctx: other.inverse(self.inverse(b, ctx), ctx))
    
    def __neg__(self) -> Iso[B, A]:
        return Iso(self.inverse, self.forward)

    @classmethod
    def const(cls, a: A, b: B) -> Iso[A, B]:
        return cls(lambda _, __: b, lambda _, __: a)
    
    @classmethod
    def derive(cls, a: Callable[..., A], b: Callable[..., B]) -> Iso[A, B]:
        forward = transform(a, b, soft_failure=False)
        inverse = transform(b, a, soft_failure=True)
        return cls(forward, inverse)




def default_eval(env: Env, visited: Set[Any]) -> Tuple[bool, Any]:
    """
    Docstring for default_eval
    Setinal function for Expr, should never be called directly. If it is called, it means the expression was not fully defined. 
    The subclass of Expr should override this method with the actual evaluation logic. The default implementation raises an error to indicate that the expression is not fully defined and should not be evaluated.
    """
    raise NotImplementedError("Expression not fully defined, default_eval should NEVER be called")

def default_infer(value: Any, child: List[Tuple[bool, int|str, Expr, Any]], env: Env, visited: Set[Any]) -> Generator[Tuple[Tuple[Var, Any], ...], None, None]:
    yield ()
@dataclass(frozen=True, slots=True, eq=False)
class Expr:
    expr: Callable[[Env, Set[Any]], Tuple[bool, Any]] = field(default=default_eval, compare=False, hash=False, repr=False)
    children: List[Tuple[int|str, Expr]] = field(default_factory=list, compare=False, hash=False, repr=False)
    infer: Callable[[Any, List[Tuple[bool, int|str, Expr, Any]], Env, Set[Any]], Generator[Tuple[Tuple[Var, Any], ...], None, None]] = field(default=default_infer, compare=False, hash=False, repr=False)
    
    def evaluate(self, env: Env, visited: Set[Any]) -> Tuple[bool, Any]:
        cache = env.evaluation_cache.setdefault(env.version, {})
        if id(self) in cache:
            return True, cache[id(self)]
        if self in visited:
            return False, self
        visited.add(self)
        fully_resolved, value = self.expr(env, visited)
        if fully_resolved:
            cache[id(self)] = value
        return fully_resolved, value
    
    def inference(self, value: Any, env: Env, visited: Set[Any]) -> Generator[Tuple[Tuple[Var, Any], ...], None, None]:
        if self in visited:
            return
        visited = visited | {self}
        if self.infer is default_infer:
            yield ()
            return
        else:
            children:List[Tuple[bool, int|str, Expr, Any]] = []
            for i, child in self.children:
                fully_resolved, v = evaluate(child, env, visited)
                children.append((fully_resolved, i, child, v))
            yield from self.infer(value, children, env, visited)
            return

    def bind(self, env: Env, value: Any) -> Tuple[bool, List[Any]]:
        env.constraints.add(Constraint(self, value))
        return True, []
        
    
    def unify(self, other: Any, env: Env) -> Tuple[bool, List[Any]]:
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

        return Expr(expr_f, [(0, self), (1, other)])
    

    def _unary_op(self, op: Callable[[Any], Any]) -> Expr:
        def expr_f(env: Env, visited: Set[Any]) -> Tuple[bool, Any]:
            fully_resolved, v = self.evaluate(env, visited)
            if not fully_resolved:
                return False, self
            return (True, op(v))
        
        return Expr(expr_f, [(0, self)])

    # function call operator
    def __call__(self, *args: Any, **kwargs: Any) -> Expr:
        def expr_f(env: Env, visited: Set[Any]) -> Tuple[bool, Any]:
            fully_resolved, func = self.evaluate(env, visited)
            if not fully_resolved:
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
        return Expr(expr_f, [(0, self)] 
                            + [(i+1, arg) for i, arg in enumerate(args)] 
                            + [(k, v) for k, v in kwargs.items()]) # type: ignore

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
        return Expr(expr_f, [(i, arg) for i, arg in enumerate(args)] 
                            + [(k, v) for k, v in kwargs.items()]) # type: ignore
    
    # Container & Utility Operators
    def __getitem__(self, key: Any) -> Expr:
        return self._unary_op(lambda v: v[key])
    
    def __contains__(self, item: Any) -> Expr:
        return self._unary_op(lambda v: item in v)
    
    
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
    debug_f: Callable[..., Any] = field(default=lambda *arg, **kwargs: None, compare=False, hash=False, repr=False)
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

    def inference(self, value: Any, env: Env, visited: Set[Any]) -> Generator[Tuple[Tuple[Var, Any], ...], None, None]:
        yield ((self, value),)

    def is_bound(self, env: Env) -> bool:
        return self in env
    
    def bind(self, env: Env, value: Any) -> Tuple[bool, List[Any]]:
        success, reason = env.bind(self, value)
        if success:
            self.debug_f(self.name, value)
            return True, []
        return False, reason + [(self, "Variable binding conflict")]

    def unify(self, other: Any, env: Env) -> Tuple[bool, List[Any]]:
        return self.bind(env, other)

    def debug(self, f: Callable[..., Any]) -> Var:
        object.__setattr__(self, 'debug_f', f)
        return self

@dataclass(slots=True)
class Scope:
    pool: Dict[str, Var] = field(default_factory=dict)
    def __getattr__(self, name: str) -> Var:
        return self.create(name)

    def create(self, name: str) -> Var:
        if name not in self.pool:
            self.pool[name] = Var(name=name)
        return self.pool[name]

@dataclass(frozen=True, slots=True, eq=False)
class Let(Expr):
    var: Var = field(default_factory=lambda: Var(), compare=False, hash=False)
    body: Any = field(default_factory=lambda: Expr(), compare=False, hash=False)

    def __post_init__(self):
        def expr_f(env: Env, visited: Set[Any]) -> Tuple[bool, Any]:
            return evaluate(self.body, env, visited)
        object.__setattr__(self, 'expr', expr_f)

    def unify(self, target: Any, env: Env) -> Tuple[bool, List[Any]]:
        success, reason = unify(self.var, target, env)
        if success:
            env.constraints.add(Constraint(self, target))
        return success, reason

def let(var: Var, rhs: Any) -> Let:
    return Let(var=var, body=rhs)


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
    _val_hash is used by dataclass's default hash implementation.
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

    def __call__(self, env: Env, visited: Set[Any]) -> Tuple[bool, Any, List[Any]]:
        fully_resolved, value = self.expr.evaluate(env, visited)
        full_expected, value_expected = evaluate(self.expected, env, visited)
        if fully_resolved and full_expected:
            success, reason = unify(value, value_expected, env)
            return True, success, reason
        elif not fully_resolved and full_expected:
            for solution in self.expr.inference(value_expected, env, set()):

                for var, val in solution:
                    success, reason = env.bind(var, val)
                    if not success:

                        return True, False, reason + [(var, val, "Constraint inference binding conflict")]
                    else:

                        return True, True, []
            return False, self.expr, []
        elif fully_resolved and not full_expected:
            return False, self.expected, []
        else:
            return False, self.expr, []


                
        

@dataclass(slots=True)
class EnvFrame:
    bindings: dict[Var, Binding] = field(default_factory=dict)
    parent: EnvFrame | None = None
    def resolve(self, var: Var) -> Any:
        ret = self.bindings.get(var, ...)
        if ret is ...:
            if self.parent is not None:
                return self.parent.resolve(var)
            else:
                return ...
        else:
            return ret.value


    
@dataclass(slots=True)
class Env:
    constants: FrozenDict[str, Any] = field(default_factory=FrozenDict) 
    frames: EnvFrame = field(default_factory=EnvFrame)
    constraints: Set[Constraint] = field(default_factory=set)
    scope: Scope = field(default_factory=Scope)
    version: int = 0
    evaluation_cache: Dict[int, Dict[int, Any]] = field(default_factory=dict, compare=False, hash=False, repr=False)

    def push(self) -> Env:
        self.frames = EnvFrame(parent=self.frames)
        return self
    
    def pop(self) -> Env:
        if self.frames.parent is not None:
            self.frames = self.frames.parent
        return self
    
    def commit(self, all: bool = False) -> Env:
        while self.frames.parent is not None:
            if self.frames.bindings:
                self.version += 1
            for var, binding in self.frames.bindings.items():
                self.frames.parent.bindings[var] = binding
            self.frames = self.frames.parent
            if not all:
                break
        return self

    def __getattr__(self, name: str) -> Var:
        return self.scope.create(name)

    def create_var(self, name: str) -> Var:
        return self.scope.create(name)

    def __contains__(self, var: Var) -> bool:
        return self.resolve(var) is not ...
        

    @classmethod
    def create(cls,
               scope: Scope,
               constants: FrozenDict[str, Any], 
               *constraints: Constraint,
               **where: Any) -> Env:
        ret = Env(constants=constants)
        for c in constraints:
            ret.constraints.add(c)
        for k, v in where.items():
            var = scope.create(k)
            success, reason = ret.bind(var, v)
            if not success:
                raise DataError(f"Failed to bind variable {k} to value {v}", reason)
        return ret
    
    def resolve(self, var: Var) -> Any:
        ret = self.frames.resolve(var)
        if ret is ... and self.constants is not None:
            return self.constants.get(var.name, ...)
        else:
            return ret
        
    def bind(self, var: Var, value: Any) -> Tuple[bool, List[Any]]:
        v = self.resolve(var)
        if v is not ...:
            success, reason = unify(v, value, self)
            if not success:
                return False, reason + [(var, value, "Variable binding conflict")]
        else:
            self.frames.bindings[var] = Binding(value=value)
            self.version += 1
        return True, []
            

    def solve(self)-> Tuple[bool, List[Any]]:
        version = -1
        satisfied = set()
        while self.version > version:
            version = self.version
            for c in list(self.constraints):
                self.push()
                fully_resolved, result, reason = c(self, set())
                if not fully_resolved:
                    self.pop()
                    continue
                if result is False:
                    self.pop()
                    return False, reason + [(c, "Constraint evaluated to False")]
                self.commit()
                satisfied.add(c)


        for c in self.constraints:
            if c not in satisfied:
                return False, [(c, "Constraint could not be fully evaluated")]
        return True, []





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
                fully_resolved, val = evaluate(v, env, visited)
                if not fully_resolved:
                    return False, expr
                result[k] = val
            return True, result
        elif isinstance(expr, list):
            lst = []
            for item in expr:
                fully_resolved, v = evaluate(item, env, visited)
                if not fully_resolved:
                    return False, expr
                lst.append(v)
            return True, lst
        elif isinstance(expr, tuple):
            tpl = []
            for item in expr:
                fully_resolved, v = evaluate(item, env, visited)
                if not fully_resolved:
                    return False, expr
                tpl.append(v)
            return True, tuple(tpl)
        elif is_dataclass(expr):
            all_fields = {}
            for field in fields(expr):
                fully_resolved, v = evaluate(getattr(expr, field.name), env, visited)
                if not fully_resolved:
                    return False, expr
                all_fields[field.name] = v
            try:
                return True, type(expr)(**all_fields) # type: ignore
            except Exception as e:
                print(f"Failed to construct dataclass {type(expr)} with fields {all_fields}: {e}")
                raise DataError(f"Failed to construct dataclass {type(expr)} with fields {all_fields}: {e}")
    return True, expr
    
def unify(pattern: Any, value: Any, env: Env) -> Tuple[bool, List[Any]]:
    if pattern is value:
        return True, []
    elif isinstance(pattern, Expr):
        return pattern.unify(value, env)
    elif isinstance(value, Expr):
        return value.unify(pattern, env)
    
    elif is_primitive(pattern):
        if is_primitive(value):
            if isinstance(pattern, float) and isinstance(value, float):
                import math
                ret = math.isclose(pattern, value, rel_tol=1e-9)
            else:
                ret = pattern == value
            if not ret:
                return False, [(pattern, value, "Primitive values do not match")]
            else:
                return True, []
        else:
            return False, [(pattern, value, "Type mismatch between primitive and non-primitive")]

    elif is_struct(pattern):
        if isinstance(pattern, dict) and isinstance(value, dict):
            for k, v in pattern.items():
                if k not in value:
                    return False, [(pattern, value, f"Key {k} not found in value")]
                success, reason = unify(v, value[k], env)
                if not success:
                    return False, reason + [(pattern, value, f"Failed to unify key {k}")]
            return True, []
        elif isinstance(pattern, (list, tuple)) and isinstance(value, (list, tuple)):
            if len(pattern) > len(value):
                return False, [(pattern, value, "Pattern list/tuple is longer than value")]
            for p_item, v_item in zip(pattern, value):
                success, reason = unify(p_item, v_item, env)
                if not success:
                    return False, reason + [(pattern, value, "Failed to unify list/tuple items")]
            return True, []
        elif is_dataclass(pattern) and is_dataclass(value):
            if not isinstance(value, type(pattern)): # type: ignore
                return False, [(pattern, value, "Dataclass type mismatch")]
            for field in fields(pattern):
                p_item = getattr(pattern, field.name)
                v_item = getattr(value, field.name)
                success, reason = unify(p_item, v_item, env)
                if not success:
                    return False, reason + [(pattern, value, f"Failed to unify dataclass field {field.name}")]
            return True, []

    raise DataError(f"Unsupported pattern or value type for unification {pattern}, {value}.")


def solve(pattern: Any, value: Any, env: Env) -> Env | List[Any]:
    success, reason = unify(pattern, value, env)
    if not success:
        return reason
    success, reason = env.solve()
    if not success:
        return reason
    return env


    
def transform(
    source: Callable[..., Any],
    target: Callable[..., Any],
    *,
    soft_failure: bool,
) -> Callable[[Any, Any], Any]:
    src_sig = CallWith(source)
    src_vars = src_sig.missing_args[1:]
    def call_src(env: Env) -> Any:
        vars = [env.create_var(name) for name in src_vars]
        return source(env, *vars)

    tgt_sig = CallWith(target)
    tgt_vars = tgt_sig.missing_args[1:]
    def call_tgt(env: Env) -> Any:
        vars = [env.create_var(name) for name in tgt_vars]
        return target(env, *vars)
        

    def transform_f(value: Any, ctx: Any) -> Any:
        # from rich import print
        assert ctx is None or isinstance(ctx, FrozenDict), f"Context must be a FrozenDict, got {type(ctx)}"
        env = Env(constants=ctx or FrozenDict())
        src = call_src(env)

        new_env = solve(src, value, env)
        if isinstance(new_env, list):
            raise DataError(
                f"Failed to unify source with value: {new_env}",
                soft_failure=soft_failure,
            )
        tgt = call_tgt(new_env)
        fully_resolved, result = evaluate(tgt, new_env, set())
        if not fully_resolved:
            raise DataError(f"Failed to fully evaluate target after unification: {result}")
        return result
    return transform_f

class Match:
    def __init__(self, source: Callable[..., Any], target: Callable[..., Any]):
        self.cases = [(source, target)]

    def case(self, source: Callable[..., Any], target: Callable[..., Any]) -> Match:
        self.cases.append((source, target))   
        return self

    @staticmethod
    def overlap(*ptns: Callable[..., Any]) -> Tuple[bool, List[Any]]:
        def build(env: Env, ptn: Callable[..., Any]) -> Any:
            sig = CallWith(ptn)
            vars = [env.create_var(name) for name in sig.missing_args[1:]]
            return ptn(env, *vars)

        n = len(ptns)
        for i in range(n):
            for j in range(i + 1, n):
                env = Env()  # fresh env per pair
                a = build(env, ptns[i])
                b = build(env, ptns[j])
                success, _ = unify(a, b, env)
                if not success:
                    continue
                else:
                    return True, [a, b]
        return False, []
    
    def forward(self, overlap: bool) -> Callable[[Any, Any], Any]:
        if not overlap:
            o, offender = Match.overlap(*(src for src, tgt in self.cases))
            if o:
                raise DataError(f"Overlapping patterns detected in Match.forward: {offender[0]} VS. {offender[1]}")
        transforms = [transform(src, tgt, soft_failure=False) for src, tgt in self.cases]
        def transform_f(value: Any, ctx: Any) -> Any:
            for t in transforms:
                try:
                    return t(value, ctx)
                except DataError:
                    continue
            raise DataError(f"No matching case found for value: {value}")
        return transform_f
    
    def inverse(self, overlap: bool) -> Callable[[Any, Any], Any]:
        if not overlap:
            o, offender = Match.overlap(*(tgt for src, tgt in self.cases))
            if o:
                raise DataError(f"Overlapping patterns detected in Match.inverse: {offender[0]} VS. {offender[1]}")
        transforms = [transform(tgt, src, soft_failure=True) for src, tgt in self.cases]
        def transform_f(value: Any, ctx: Any) -> Any:
            for t in transforms:
                try:
                    return t(value, ctx)
                except DataError:
                    continue
            raise DataError(f"No matching case found for value: {value}")
        return transform_f
    
    def iso(self, overlap: bool = True) -> Iso:
        return Iso(self.forward(overlap=overlap), self.inverse(overlap=overlap))
        

def Not(expr: Any) -> Any:
    def infer_not(value: Any, child: List[Tuple[bool, int|str, Expr, Any]], env: Env, visited: Set[Any]) -> Generator[Tuple[Tuple[Var, Any], ...], None, None]:
        if value is True:
            for fully_resolved, i, child_expr, child_value in child:
                if not fully_resolved:
                    yield from child_expr.inference(False, env=env, visited=visited)
        elif value is False:
            for fully_resolved, i, child_expr, child_value in child:
                if not fully_resolved:
                    yield from child_expr.inference(True, env=env, visited=visited)
        else:
            raise DataError(f"Expected boolean value for Not inference, got {value}")
    return replace(Expr.apply(lambda x: not x, expr), infer = infer_not)



"""
Docstring for syncraft.bimap

  This document outlines the architecture for a bidirectional data transformation DSL based on Structural Unification 
and Functional Injection. It focuses on a "Pure Structural" engine where functional relationships are treated as declarative constraints.

1. Core Architecture
    The system operates on a Variable Environment (a context dictionary) and a Template. The transformation is 
    bidirectional by nature: the engine either extracts values into variables or reconstructs structures from variables.
    The Two Modes of Operation:
    Deconstruction (Raw → Domain): Matches the input against a structural pattern and binds values to variables.
    Reconstruction (Domain → Raw): Uses bound variables to fill "holes" in a structural pattern.


2. Key DSL Components
    A. Logic Variables (V_VAR)
    Singletons or objects that act as placeholders.
    State: Can be Unbound (empty) or Bound (contains a value).
    Constraint: Once bound, a variable cannot change its value (ensuring consistency).

    B. Structural Patterns
    Standard Python collections used as templates:
    Tuples/Lists: (V_A, V_B) or (V_HEAD, *V_TAIL).
    Dictionaries: {"key": V_VAL}.

    C. The Computed Injector
    The bridge between pure structure and logic.
    Syntax: Computed(Target_Var, Function, *Source_Vars)
    Behavior: * If Target_Var is unknown: Calculates Function(*Source_Vars) and assigns the result.
    If Target_Var is known: Validates that Target_Var == Function(*Source_Vars).

3. Transformation Example: Length-Prefixed List
    This example demonstrates how the len function serves both directions without needing a formal "inverse."
    ```
    V_SIZE = Var("size")
    V_ITEMS = Var("items")

    template = Mapping(
        # The 'raw' side expects a tuple: (length, item1, item2...)
        raw = (Computed(V_SIZE, len, V_ITEMS), *V_ITEMS),
        
        # The 'domain' side expects a structured dict
        domain = {"size": V_SIZE, "content": V_ITEMS}
    )
    ```
    Direction,  Input,                      Action,                                                     Output
    Parsing     "(2, ""A"", ""B"")",        "Bind V_SIZE=2, V_ITEMS=[""A"", ""B""]. len validates.",    "{""size"": 2, ""content"": [""A"", ""B""]}"
    Generating  "{""content"": [""A""]}",   "Bind V_ITEMS=[""A""]. Computed calculates V_SIZE=1.",      "(1, ""A"")"

4. Technical Details: The Resolution Engine
    Local Backtracking (Choice Points)
    To support branching (e.g., or_else), the engine uses Environment Snapshots.
    Checkpoint: Copy the current variable bindings.
    Attempt: Try Branch A.
    Rollback: If structural matching or Computed constraints fail, restore the checkpoint.
    Succeed: If Branch A finishes, discard the checkpoint and commit.
    The Resolution Loop
    Since Computed fields might depend on other Computed fields, the engine uses a reactive loop:
    Step 1: Perform all direct structural bindings.
    Step 2: Identify all Computed constraints.
    Step 3: Repeatedly execute constraints where all Source_Vars are bound until the environment stabilizes.
    Step 4: Verify no "Deadlocks" (circular dependencies) or "Unbound" requirements remain. 

5. Summary Comparison: Why this is better than Manual Isos
    Feature,                Manual Pair (to/from),                      Unification DSL
    Maintenance,            High (must keep 2 functions in sync),       Low (Single template definition)
    Validation,             Manual if checks,                           Automatic (Mismatch = Failure)
    Logic,                  Procedural,                                 Declarative (WYSIWYG)
    Functional Case,        Requires explicit Inverse (Iso),            Can use ordinary functions (Computed)    


6. Formal Structure of Terms
    Primitive ::= int | float | str | bool | bytes | None

    Value ::= Primitive | Var | Structure

    Structure ::= dict[hashable, Term]
                | list[Term]
                | tuple[Term, ...]
                | dataclass(Term fields)

    Term ::= Value | Computed

    Computed ::= constraint(Target: Var, func, args: Tuple[Value, ...])

"""



from __future__ import annotations

from typing import (
    Any, TypeVar, Tuple, List, Set,
    Generic, Callable, overload, Literal
)
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, is_dataclass, fields




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



class MetaUnbound(type):
    def __instancecheck__(cls, instance: Any) -> bool:
        return instance is cls or super().__instancecheck__(instance)
    def __str__(cls)->str:
        return "Unbound"
    def __repr__(cls)->str:
        return "Unbound"
    def __bool__(cls)->bool:
        return False
@dataclass(frozen=True, slots=True)
class Unbound(metaclass=MetaUnbound):
    """Singleton sentinel representing the absence of a value in the AST."""
    def __call__(self)-> Unbound:
        return self
    def __new__(cls):
        return cls
    def __bool__(self)->bool:
        return False
    def __str__(self)->str:
        return "Unbound"
    def __repr__(self)->str:
        return "Unbound"

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
        return self in env.bindings and env.bindings[self].value is not Unbound
    
    def bind(self, env: Env, value: Any) -> bool:
        binding = env.bind(self, value)
        return binding is not None
    
    def eval(self, env: Env) -> Tuple[bool, Any]:
        if self.is_bound(env):
            resolved = env.resolve(self)
            if isinstance(resolved, Unbound):
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
    value: Any = Unbound
    constraints: List[Fun] = field(default_factory=list)
    satisfied: Set[int] = field(default_factory=set)

@dataclass(slots=True)
class Env:
    bindings: dict[Var, Binding] = field(default_factory=dict)
    def __contains__(self, var: Var) -> bool:
        return var in self.bindings
    
    def resolve(self, var: Var) -> Any | Unbound:
        ret = self.bindings.get(var, Unbound())
        if isinstance(ret, Unbound):
            return Unbound
        else:
            return ret.value
        
    def bind(self, var: Var, value: Any) -> Binding | None:
        if var in self.bindings:
            binding = self.bindings[var]
            if binding.value is not Unbound:
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
                    if binding.value is not Unbound:
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

def is_structure(value: Any) -> bool:
    return isinstance(value, (dict, list, tuple)) or is_dataclass(value) 


def eval(expr: Any, env: Env) -> Tuple[bool, Any]:
    if isinstance(expr, Term):
        return expr.eval(env)
    elif is_structure(expr):
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
    if pattern is Unbound or value is Unbound:
        raise ValueError("Cannot unify with Unbound pattern.")
    elif isinstance(pattern, Term):
        return pattern.unify(value, env)

    elif is_primitive(pattern):
        if is_primitive(value):
            return pattern == value
        else:
            return False

    elif is_structure(pattern):
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
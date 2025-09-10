from __future__ import annotations

from typing import (
    TypeVar, Optional, Hashable, Generic, Tuple, ClassVar
)
from dataclasses import dataclass, field
from syncraft.algebra import (
    SyncraftError
)
from syncraft.constraint import  FrozenDict

from rich import print


C = TypeVar('C', bound=Hashable)

@dataclass(frozen=True)
class NFAState(Generic[C]):
    _counter: ClassVar[int] = 0  # shared across all states
    id: int = field(default_factory=lambda: NFAState._next_id())
    @classmethod
    def _next_id(cls) -> int:
        val = cls._counter
        cls._counter += 1
        return val

    def __repr__(self) -> str:
        return f"q{self.id}"        


@dataclass(frozen=True)
class NFA(Generic[C]):
    name: str
    start: NFAState[C]
    accept: frozenset[NFAState[C]] = field(default_factory=frozenset)
    transitions: FrozenDict[NFAState[C], FrozenDict[C, frozenset[NFAState[C]]]] = field(default_factory=FrozenDict)
    epsilon: FrozenDict[NFAState[C], frozenset[NFAState[C]]] = field(default_factory=FrozenDict)


    def clone(self) -> NFA[C]:
        state_map: dict[NFAState[C], NFAState[C]] = {}
        def get_clone(s: NFAState[C]) -> NFAState[C]:
            if s not in state_map:
                state_map[s] = NFAState()
            return state_map[s]
        new_start = get_clone(self.start)
        new_accept = frozenset(get_clone(a) for a in self.accept)
        new_transitions: dict[NFAState[C], FrozenDict[C, frozenset[NFAState[C]]]] = {}
        for k, v in self.transitions.items():
            new_transitions[get_clone(k)] = FrozenDict({
                c: frozenset(get_clone(s) for s in targets)
                for c, targets in v.items()
            })
        new_epsilon: FrozenDict[NFAState[C], frozenset[NFAState[C]]] = FrozenDict({
            get_clone(k): frozenset(get_clone(s) for s in v)
            for k, v in self.epsilon.items()
        })
        return self.__class__(name=self.name,
                              start=new_start,
                              accept=new_accept,
                              transitions=FrozenDict(new_transitions),
                              epsilon=new_epsilon)

    def closure(self, states: frozenset[NFAState[C]]) -> frozenset[NFAState[C]]:
        stack = list(states)
        closure = set(states)
        while stack:
            s = stack.pop()
            for next_state in self.epsilon.get(s, frozenset()):
                if next_state not in closure:
                    closure.add(next_state)
                    stack.append(next_state)
        return frozenset(closure)
    

    def run(self, input_seq: list[C]) -> bool:
        # step 1: epsilon closure from start
        current: frozenset[NFAState[C]] = self.closure(frozenset({self.start}))

        # step 2: consume input
        for symbol in input_seq:
            next_states = set()
            for s in current:
                for tgt in self.transitions.get(s, {}).get(symbol, frozenset()):
                    next_states.add(tgt)
            current = self.closure(frozenset(next_states))
        # step 3: check accept
        ret = any(st in self.accept for st in current)    
        return ret

    @classmethod
    def from_char(cls, char: C) -> NFA[C]:
        start: NFAState[C] = NFAState()
        accept: NFAState[C] = NFAState()
        return cls(name=f'{char}',
                   start=start, 
                   accept=frozenset({accept}),
                   transitions=FrozenDict({
                       start: FrozenDict({char: frozenset({accept})})
                   }),
                   epsilon=FrozenDict())


    def then(self, other: NFA[C]) -> NFA[C]:
        this = self.clone()
            
        eps = {**this.epsilon}
        for a in this.accept:
            eps[a] = eps.get(a, frozenset()) | frozenset({other.start})
        
        for k, v in other.epsilon.items():
            eps[k] = eps.get(k, frozenset()) | v
    
        new_transitions = {**this.transitions}
        for k, v in other.transitions.items():
            new_transitions[k] = new_transitions.get(k, FrozenDict()) | v
            
        return this.__class__(name=f'{this.name} {other.name}',
                              start=this.start, 
                              accept=other.accept, 
                              transitions=FrozenDict(new_transitions), 
                              epsilon=FrozenDict(eps))
    
    def union(self, other: NFA[C]) -> NFA[C]:
        if self is other:
            return self
        new_start: NFAState[C] = NFAState()
        eps = {new_start: frozenset({self.start, other.start})}
        for k, v in self.epsilon.items():
            eps[k] = eps.get(k, frozenset()) | v
        for k, v in other.epsilon.items():
            eps[k] = eps.get(k, frozenset()) | v
        
        new_transitions = {**self.transitions}
        for k, v in other.transitions.items():
            new_transitions[k] = new_transitions.get(k, FrozenDict()) | v
        return self.__class__(name=f'{self.name} | {other.name}',
                              start=new_start, 
                              accept=self.accept | other.accept, 
                              transitions=FrozenDict(new_transitions), 
                              epsilon=FrozenDict(eps))

    def star(self) -> NFA[C]:
        new_start: NFAState[C] = NFAState()
        eps = {**self.epsilon, new_start: frozenset({self.start})}
        for a in self.accept:
            eps[a] = eps.get(a, frozenset()) | frozenset({self.start})
        return self.__class__(name=f'({self.name})*',
                              start=new_start, 
                              accept=self.accept | frozenset({new_start}), 
                              transitions=self.transitions, 
                              epsilon=FrozenDict(eps))
    
    def optional(self)->NFA[C]:
        new_start: NFAState[C] = NFAState()
        eps = {**self.epsilon, new_start: frozenset({self.start})}
        return self.__class__(name=f'({self.name})?',
                              start=new_start, 
                              accept=self.accept | frozenset({new_start}), 
                              transitions=self.transitions, 
                              epsilon=FrozenDict(eps))
    
    def plus(self) -> NFA[C]:
        eps = {**self.epsilon}
        for a in self.accept:
            eps[a] = eps.get(a, frozenset()) | frozenset({self.start})
        return self.__class__(name=f'({self.name})+',
                              start=self.start, 
                              accept=self.accept, 
                              transitions=self.transitions, 
                              epsilon=FrozenDict(eps))
    
    def many(self, at_least: int = 1, at_most: Optional[int] = None) -> NFA[C]:
        if at_least <=0 or (at_most is not None and at_most < at_least):
            raise SyncraftError(f"Invalid arguments for many: at_least={at_least}, at_most={at_most}", offending=(at_least, at_most), expect="at_least>0 and (at_most is None or at_most>=at_least)")
        if at_least == 1 and at_most is None:
            return self.plus()
        nfa = self
        for _ in range(at_least - 1):
            nfa = nfa.then(self)
        if at_most is None:
            nfa = nfa.then(self.star())
        else:
            optional_count = at_most - at_least
            for _ in range(optional_count):
                nfa = nfa.then(self.optional())
        return nfa

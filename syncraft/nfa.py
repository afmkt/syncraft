from __future__ import annotations

from typing import (
    TypeVar, Optional, Hashable, Generic, Tuple, ClassVar, List, Set, Dict
)
from dataclasses import dataclass, field, replace
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
    def from_int(cls, id: int) -> NFAState:
        return cls(id=id)

    @classmethod
    def _next_id(cls) -> int:
        val = cls._counter
        cls._counter += 1
        return val

    def __repr__(self) -> str:
        return f"s{self.id}"        


@dataclass(frozen=True)
class NFA(Generic[C]):
    name: str
    start: NFAState[C]
    accept: FrozenDict[NFAState[C], Optional[str]] = field(default_factory=FrozenDict)
    transitions: FrozenDict[NFAState[C], FrozenDict[C, frozenset[NFAState[C]]]] = field(default_factory=FrozenDict)
    epsilon: FrozenDict[NFAState[C], frozenset[NFAState[C]]] = field(default_factory=FrozenDict)


    def clone(self) -> NFA[C]:
        state_map: dict[NFAState[C], NFAState[C]] = {}
        def get_clone(s: NFAState[C]) -> NFAState[C]:
            if s not in state_map:
                state_map[s] = NFAState()
            return state_map[s]
        new_start = get_clone(self.start)
        new_accept: FrozenDict[NFAState[C], Optional[str]] = FrozenDict({get_clone(a):b for a,b in self.accept.items()})
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
    
    def tagged(self, tag: str) -> NFA[C]:
        return self.__class__(name=self.name,
                              start=self.start,
                              accept=FrozenDict({a: tag for a in self.accept}),
                              transitions=self.transitions,
                              epsilon=self.epsilon)

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
    
    def run(self, input_seq: list[C]) -> NFARunner[C]:
        return NFARunner.from_nfa(self).steps(self, input_seq)

    def match(self, input_seq: list[C]) -> bool:
        return self.run(input_seq).is_accepted(self)

    @classmethod
    def from_char(cls, char: C, tag: Optional[str] = None) -> NFA[C]:
        start: NFAState[C] = NFAState()
        accept: NFAState[C] = NFAState()
        return cls(name=f'{char}',
                   start=start, 
                   accept=FrozenDict({accept: tag}),
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
                              accept=self.accept | FrozenDict({new_start: None}), 
                              transitions=self.transitions, 
                              epsilon=FrozenDict(eps))
    
    def optional(self)->NFA[C]:
        new_start: NFAState[C] = NFAState()
        eps = {**self.epsilon, new_start: frozenset({self.start})}
        return self.__class__(name=f'({self.name})?',
                              start=new_start, 
                              accept=self.accept | FrozenDict({new_start: None}), 
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


@dataclass(frozen=True)
class NFARunner(Generic[C]):
    current: frozenset[NFAState[C]] = field(default_factory=frozenset)
    accepted: Tuple[Tuple[int, NFAState[C], Optional[str]], ...] = field(default_factory=tuple)
    @classmethod
    def from_nfa(cls, nfa: NFA[C]) -> NFARunner[C]:
        current = nfa.closure(frozenset({nfa.start}))
        return cls(current=current, accepted=tuple())
    
    def step(self, nfa: NFA[C], symbol: C, pos: int) -> NFARunner[C]:
        next_states = set()
        for s in self.current:
            for tgt in nfa.transitions.get(s, {}).get(symbol, frozenset()):
                next_states.add(tgt)
        new_current = nfa.closure(frozenset(next_states))
        new_accepted = self.accepted + tuple(((pos, a, tag) for a, tag in nfa.accept.items() if a in new_current))
        return NFARunner(current=new_current, accepted=new_accepted)


    def steps(self, nfa: NFA[C], input: list[C]) -> NFARunner[C]:
        runner = self
        for i, symbol in enumerate(input):
            runner = runner.step(nfa, symbol, i)
        return replace(runner, accepted=tuple(sorted(runner.accepted, key=lambda x: x[0], reverse=True)))


    def is_accepted(self, nfa: NFA[C]) -> bool:
        return any(st in nfa.accept for st in self.current)
    
    
    def resumable(self, nfa: NFA[C]) -> FrozenDict[NFAState[C], tuple[int, frozenset[C]]]:
        """
        Return a dict mapping each current state (not yet accepting) that can eventually
        reach acceptance to a tuple:
            (minimum distance to accept, set of first symbols along minimal paths)
        Empty dict means 'dead' (no resumable paths).
        """
        result: dict[NFAState[C], tuple[int, set[C]]] = {}

        for start in self.current:
            if start in nfa.accept:
                continue  # skip already accepting states

            # BFS queue: (state, distance, first symbol leading here)
            queue: list[tuple[NFAState[C], int, Optional[C]]] = [(start, 0, None)]
            # Map visited node -> (distance, first symbols set)
            visited: dict[NFAState[C], tuple[int, set[C]]] = {start: (0, set())}
            found_distance: Optional[int] = None

            while queue:
                s: NFAState[C]
                d: int 
                first_sym: Optional[C] 
                s, d, first_sym = queue.pop(0)

                if found_distance is not None and d > found_distance:
                    continue

                if s in nfa.accept:
                    found_distance = d if found_distance is None else min(found_distance, d)
                    continue

                # Explore transitions
                for sym, nxts in nfa.transitions.get(s, {}).items():
                    for nxt in nxts:
                        fs: C
                        if first_sym is None:
                            fs = sym
                        else:
                            fs = first_sym                        
                        if nxt not in visited:
                            visited[nxt] = (d + 1, {fs})
                            queue.append((nxt, d + 1, fs))
                        else:
                            old_d, old_syms = visited[nxt]
                            if d + 1 < old_d:
                                visited[nxt] = (d + 1, {fs})
                                queue.append((nxt, d + 1, fs))
                            elif d + 1 == old_d:
                                old_syms.add(fs)

                # Explore epsilon transitions
                for nxt in nfa.epsilon.get(s, frozenset()):
                    if nxt not in visited:
                        visited[nxt] = (d, set() if first_sym is None else {first_sym})
                        queue.append((nxt, d, first_sym))
                    else:
                        old_d, old_syms = visited[nxt]
                        if d < old_d:
                            visited[nxt] = (d, set() if first_sym is None else {first_sym})
                            queue.append((nxt, d, first_sym))
                        elif d == old_d and first_sym is not None:
                            old_syms.add(first_sym)

            # After BFS, collect first symbols for minimal distance paths
            if found_distance is not None:
                first_symbols: set[C] = set()
                for state, (dist, syms) in visited.items():
                    if state in nfa.accept and dist == found_distance:
                        first_symbols.update(syms)
                result[start] = (found_distance, first_symbols)

        # Convert mutable sets to frozenset for API safety
        return FrozenDict({st: (dist, frozenset(syms)) for st, (dist, syms) in result.items()})

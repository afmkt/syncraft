from __future__ import annotations

from typing import (
    TypeVar, Optional, Hashable, Generic, Tuple, ClassVar, List, Set, Dict
)
from collections import deque
from dataclasses import dataclass, field, replace
from syncraft.algebra import (
    SyncraftError
)
from syncraft.constraint import  FrozenDict

from rich import print


C = TypeVar('C', bound=Hashable)

@dataclass(frozen=True)
class DFA(Generic[C]):
    start: frozenset[NFAState[C]]
    accept: FrozenDict[frozenset[NFAState[C]], frozenset[str]] = field(default_factory=FrozenDict)
    transitions: FrozenDict[frozenset[NFAState[C]], FrozenDict[C, frozenset[NFAState[C]]]] = field(default_factory=FrozenDict)

    @classmethod
    def from_nfa(cls, nfa: NFA[C]) -> DFA[C]:
        start:frozenset[NFAState[C]] = nfa.closure({nfa.start})
        reachable:FrozenDict[frozenset[NFAState[C]], FrozenDict[C, frozenset[NFAState[C]]]] = nfa.reachable(start)
        accept: FrozenDict[frozenset[NFAState[C]], frozenset[str]] = FrozenDict({
            state_set: frozenset(
                tag for s in state_set if s in nfa.accept and nfa.accept[s] is not None
                for tag in [nfa.accept[s]]  # unwrap Optional[str]
            )
            for state_set in reachable
        })
        return cls(start=frozenset(start), accept=FrozenDict(accept), transitions=reachable)
    

    def resumable(self, states: frozenset[frozenset[NFAState[C]]]) -> FrozenDict[frozenset[NFAState[C]], frozenset[C]]:
        """
        Compute resumable symbols for each DFA state in `states`.
        Returns a mapping: DFA state -> set of possible next symbols.
        """
        result: dict[frozenset[NFAState[C]], frozenset[C]] = {}
        for dfa_state in states:
            # Skip already accepting DFA states
            if self.accept.get(dfa_state):
                continue
            # Outgoing symbols
            next_syms = frozenset(self.transitions.get(dfa_state, {}).keys())
            if next_syms:
                result[dfa_state] = next_syms
        return FrozenDict(result)
    
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

    def reachable(self, start_states: frozenset[NFAState[C]] | set[NFAState[C]]) -> FrozenDict[frozenset[NFAState[C]], FrozenDict[C, frozenset[NFAState[C]]]]:
        """
        BFS-like traversal from start_states over NFA.
        Returns a mapping:
        frozenset of NFA states -> dict of symbol -> frozenset of NFA states
        This captures all reachable sets along each symbol (with epsilon closure).
        """
        result: dict[frozenset[NFAState[C]], FrozenDict[C, frozenset[NFAState[C]]]] = {}
        worklist: list[frozenset[NFAState[C]]] = [frozenset(start_states)]

        while worklist:
            states = worklist.pop()
            if states in result:
                continue

            trans_map: dict[C, frozenset[NFAState[C]]] = {}
            symbols = set()
            for s in states:
                symbols.update(self.transitions.get(s, {}).keys())

            for sym in symbols:
                next_states = set()
                for s in states:
                    next_states.update(self.transitions.get(s, {}).get(sym, frozenset()))
                next_states = set(self.closure(next_states))
                trans_map[sym] = frozenset(next_states)
                if next_states and frozenset(next_states) not in result:
                    worklist.append(frozenset(next_states))
            result[states] = FrozenDict(trans_map)
        return FrozenDict(result)



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

    def closure(self, states: set[NFAState[C]] | frozenset[NFAState[C]]) -> frozenset[NFAState[C]]:
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
        current = nfa.closure({nfa.start})
        return cls(current=frozenset(current), accepted=tuple())
    
    def step(self, nfa: NFA[C], symbol: C, pos: int) -> NFARunner[C]:
        next_states = set()
        for s in self.current:
            for tgt in nfa.transitions.get(s, {}).get(symbol, frozenset()):
                next_states.add(tgt)
        new_current = nfa.closure(next_states)
        new_accepted = self.accepted + tuple(((pos, a, tag) for a, tag in nfa.accept.items() if a in new_current))
        return NFARunner(current=frozenset(new_current), accepted=new_accepted)


    def steps(self, nfa: NFA[C], input: list[C]) -> NFARunner[C]:
        runner = self
        for i, symbol in enumerate(input):
            runner = runner.step(nfa, symbol, i)
        return replace(runner, accepted=tuple(sorted(runner.accepted, key=lambda x: x[0], reverse=True)))


    def is_accepted(self, nfa: NFA[C]) -> bool:
        return any(st in nfa.accept for st in self.current)
    
    

    def resumable(self, nfa: NFA[C]) -> FrozenDict[NFAState[C], tuple[int, frozenset[C]]]:
        """
        Compute resumable info for the current NFA runner:
        - minimal distance to acceptance
        - set of first symbols along minimal paths
        """
        result: dict[NFAState[C], tuple[int, frozenset[C]]] = {}

        for start in self.current:
            if start in nfa.accept:
                continue  # already accepting

            # reachable sets for single start state
            reachable = nfa.reachable({start})

            # BFS structures
            distances: dict[frozenset[NFAState[C]], int] = {frozenset({start}): 0}
            first_symbols: dict[frozenset[NFAState[C]], set[C]] = {frozenset({start}): set()}
            queue = deque([frozenset({start})])

            while queue:
                sset = queue.popleft()
                d = distances[sset]
                fsyms = first_symbols[sset]

                for sym, nxt_set in reachable.get(sset, {}).items():
                    nxt_frozen = frozenset(nxt_set)
                    fs = fsyms or {sym}
                    if nxt_frozen not in distances or d + 1 < distances[nxt_frozen]:
                        distances[nxt_frozen] = d + 1
                        first_symbols[nxt_frozen] = fs
                        queue.append(nxt_frozen)
                    elif d + 1 == distances[nxt_frozen]:
                        first_symbols[nxt_frozen].update(fs)

            # extract minimal distance + first symbols for accepting states
            min_dist = None
            symbols: set[C] = set()
            for sset, d in distances.items():
                if any(s in nfa.accept for s in sset):
                    if min_dist is None or d < min_dist:
                        min_dist = d
                        symbols = set(first_symbols[sset])
                    elif d == min_dist:
                        symbols.update(first_symbols[sset])

            if min_dist is not None:
                result[start] = (min_dist, frozenset(symbols))

        return FrozenDict(result)

from __future__ import annotations

from typing import (
    TypeVar, Optional, Hashable, Generic, Tuple, ClassVar, Set, Protocol, Any, Self, List, Callable
)
from dataclasses import dataclass, field, replace
from syncraft.algebra import (
    SyncraftError
)
from syncraft.constraint import  FrozenDict
from syncraft.charset import CharClass

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
    
    def runner(self) -> NFARunner[C]:
        return NFARunner.create(self)

    def run(self, input_seq: list[C]) -> NFARunner[C]:
        return self.runner().steps(self, input_seq)

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




DFAState = frozenset[NFAState[C]]
@dataclass(frozen=True)
class DFA(Generic[C]):
    current: DFAState
    accept: FrozenDict[DFAState, frozenset[str]] = field(default_factory=FrozenDict)
    transitions: FrozenDict[DFAState, FrozenDict[C, DFAState]] = field(default_factory=FrozenDict)

    @staticmethod
    def reachable(nfa: NFA[C], start_states: frozenset[NFAState[C]] | set[NFAState[C]]) -> FrozenDict[frozenset[NFAState[C]], FrozenDict[C, frozenset[NFAState[C]]]]:
        result: dict[frozenset[NFAState[C]], FrozenDict[C, frozenset[NFAState[C]]]] = {}
        worklist: list[frozenset[NFAState[C]]] = [frozenset(start_states)]

        while worklist:
            states = worklist.pop()
            if states in result:
                continue

            trans_map: dict[C, frozenset[NFAState[C]]] = {}
            symbols = set()
            for s in states:
                symbols.update(nfa.transitions.get(s, {}).keys())

            for sym in symbols:
                next_states = set()
                for s in states:
                    next_states.update(nfa.transitions.get(s, {}).get(sym, frozenset()))
                next_states = set(nfa.closure(next_states))
                trans_map[sym] = frozenset(next_states)
                if next_states and frozenset(next_states) not in result:
                    worklist.append(frozenset(next_states))
            result[states] = FrozenDict(trans_map)
        return FrozenDict(result)



    @classmethod
    def from_nfa(cls, nfa: NFA[C]) -> DFA[C]:
        current:DFAState = nfa.closure({nfa.start})
        reachable:FrozenDict[DFAState, FrozenDict[C, DFAState]] = DFA.reachable(nfa, current)
        accept: FrozenDict[DFAState, frozenset[str]] = FrozenDict({
            state_set: frozenset(
                nfa.accept[s]
                for s in state_set
                if s in nfa.accept and nfa.accept[s] is not None
            )
            for state_set in reachable
            if any(s in nfa.accept for s in state_set)  # <-- only keep real accept states
        })        
        return cls(current=frozenset(current), accept=FrozenDict(accept), transitions=reachable)
    
    def runner(self) -> DFARunner[C]:
        return DFARunner.create(self)

    def run(self, input_seq: list[C]) -> DFARunner[C]:
        return self.runner().steps(self, input_seq)

    def match(self, input_seq: list[C]) -> bool:
        return self.run(input_seq).is_accepted(self)




Automata = TypeVar('Automata', bound=Any, contravariant=True)
@dataclass(frozen=True)
class Runner(Protocol[C, Automata]):
    accepted: Tuple[Tuple[int, Any, Any], ...] = field(default_factory=tuple)
    @classmethod
    def create(cls, a: Automata) -> Self: ...
    def step(self, a: Automata, symbol: C, pos: int) -> Self: ...
    def steps(self, fa: Automata, input: list[C]) -> Self:
        runner = self
        for i, symbol in enumerate(input):
            runner = runner.step(fa, symbol, i)
            if not runner.is_valid():
                break  # no valid transitions, stop early
        return replace(runner, accepted=tuple(sorted(runner.accepted, key=lambda x: x[0], reverse=True)))

    def is_accepted(self, a: Automata) -> bool: ...
    def is_valid(self) -> bool: ...
    def resumable(self, a: Automata) -> frozenset[C]: ...
    def tags(self, a: Automata) -> frozenset[str]: ...
    def gen(self, a: Automata, times: int = 1) -> List[Tuple[List[C], frozenset[str]]]: 
        def gen_one(r: Self, a: Automata) -> Optional[Tuple[C, Self]]:
            possible_steps = r.resumable(a)
            if possible_steps:
                import random
                c = random.choice(list(possible_steps))
                return c, r.step(a, c, 0)
            else:
                return None
        ret = []
        runner = self
        for _ in range(times):
            txt: List[C] = []
            while runner.resumable(a):
                match gen_one(runner, a):
                    case None:
                        break
                    case (c, r):
                        txt.append(c)
                        runner = r
                if runner.is_accepted(a):
                    ret.append((txt, runner.tags(a)))
                    import random
                    if random.random() < 0.5:
                        break
        return ret


@dataclass(frozen=True)
class NFARunner(Runner[C, NFA[C]]):
    current: frozenset[NFAState[C]] = field(default_factory=frozenset)
    @classmethod
    def create(cls, nfa: NFA[C]) -> NFARunner[C]:
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
    
    def is_accepted(self, nfa: NFA[C]) -> bool:
        return any(st in nfa.accept for st in self.current)
    
    def is_valid(self) -> bool:
        return bool(self.current)

    def resumable(self, nfa: NFA[C]) -> frozenset[C]:
        result: Set[C] = set()
        for s in self.current:
            result.update(nfa.transitions.get(s, {}).keys())
        return frozenset(result)

    def tags(self, nfa: NFA[C]) -> frozenset[str]:
        tags: Set[str] = set()
        for s in self.current:
            if s in nfa.accept and nfa.accept[s] is not None:
                tags.add(nfa.accept[s])  # unwrap Optional[str]
        return frozenset(tags)
    

@dataclass(frozen=True)
class DFARunner(Runner[C, DFA[C]]):
    current: DFAState = field(default_factory=frozenset)

    @classmethod
    def create(cls, dfa: DFA[C]) -> DFARunner[C]:
        current = dfa.current
        return cls(current=current, accepted=tuple())
    
    def step(self, dfa: DFA[C], symbol: C, pos: int) -> DFARunner[C]:
        new_current = dfa.transitions.get(self.current, {}).get(symbol, frozenset())
        if not new_current:
            return replace(self, current=new_current)
        tags = dfa.accept.get(new_current, frozenset())
        new_accepted = self.accepted + ((pos, new_current, tags),)
        return self.__class__(current=new_current, accepted=new_accepted)

    def is_accepted(self, dfa: DFA[C]) -> bool:
        return self.current in dfa.accept

    def is_valid(self) -> bool:
        return bool(self.current)
    
    def resumable(self, dfa: DFA[C]) -> frozenset[C]:
        return frozenset(dfa.transitions.get(self.current, {}).keys())

    def tags(self, dfa: DFA[C]) -> frozenset[str]:
        return dfa.accept.get(self.current, frozenset())

        

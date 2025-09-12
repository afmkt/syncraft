from __future__ import annotations

from typing import (
    TypeVar, Optional, Generic, Tuple, ClassVar, Set, Protocol, Any, Self, List
)
from dataclasses import dataclass, field, replace
from syncraft.algebra import (
    SyncraftError
)
from collections import deque
from syncraft.constraint import  FrozenDict
from syncraft.charset import CharSet, CodeUniverse, MixedUniverseError, CodepointError

from rich import print



C = TypeVar('C', bound=str | bytes)

@dataclass(frozen=True)
class FAState:
    _counter: ClassVar[int] = 0  # shared across all states
    id: int = field(default_factory=lambda: FAState._next_id())

    @classmethod
    def from_int(cls, id: int) -> FAState:
        return cls(id=id)

    @classmethod
    def _next_id(cls) -> int:
        val = cls._counter
        cls._counter += 1
        return val

    def __repr__(self) -> str:
        return f"s{self.id}"        


@dataclass(frozen=True)
class DFA(Generic[C]):
    universe: CodeUniverse
    current: FAState
    accept: FrozenDict[FAState, frozenset[str]] = field(default_factory=FrozenDict)
    transitions: FrozenDict[FAState, FrozenDict[CharSet[C], FAState]] = field(default_factory=FrozenDict)
    nfa2dfa: FrozenDict[frozenset[FAState], FAState]= field(default_factory=FrozenDict) 
    @staticmethod
    def merge_adjacent_transitions(universe: CodeUniverse, transitions: dict[CharSet[C], FAState]) -> dict[CharSet[C], FAState]:
        """Merge consecutive CharSets with the same target into a single CharSet."""
        merged: List[Tuple[List[Tuple[int,int]], FAState]] = []
        sorted_trans = sorted(transitions.items(), key=lambda x: x[0].interval)
        
        for charset, target in sorted_trans:
            if merged and merged[-1][1] == target:
                merged[-1][0].extend(charset.interval)  # merge intervals
            else:
                merged.append((list(charset.interval), target))
        
        return {CharSet.from_interval(intv, universe): target for intv, target in merged}

    @classmethod
    def from_nfa(cls, nfa: NFA[C]) -> DFA[C]:
        start:frozenset[FAState] = nfa.closure({nfa.current})
        work_list = deque([start])
        dfa_states : dict[frozenset[FAState], FAState] = {start: FAState()}
        trans: dict[FAState, dict[CharSet[C], FAState]] = {}
        while work_list:
            current = work_list.popleft()
            current_dfa_state = dfa_states[current]
            edges: List[Tuple[CharSet[C], frozenset[FAState]]] = []
            for s in current:
                for e, targets in nfa.transitions.get(s, {}).items():
                    edges.append((e, targets))

            intvs: List[Tuple[int, int]] = [interval for e, _ in edges for interval in (e.interval if isinstance(e.interval, tuple) and isinstance(e.interval[0], int) else e.interval)]
            pieces: List[Tuple[int, int]] = CharSet.partition_charsets(intvs)
            for p in pieces:
                tgt_states: Set[FAState] = set()
                for e, targets in edges:
                    if e.overlaps(p):
                        tgt_states.update(targets)                         
                closure = nfa.closure(tgt_states)
                if closure not in dfa_states:
                    dfa_states[closure] = FAState()
                    work_list.append(closure)
                trans.setdefault(current_dfa_state, {})[CharSet.from_interval([p], nfa.universe)] = dfa_states[closure]

        for s, e in trans.items():
            trans[s] = DFA.merge_adjacent_transitions(nfa.universe, e)
        accept: dict[FAState, frozenset[str]] = {}
        for nfa_states, fa_state in dfa_states.items():
            tags: Set[str] = set()
            is_accept: bool = False
            for ns in nfa_states:
                is_accept = is_accept or (ns in nfa.accept)
                tags.update(nfa.accept.get(ns, frozenset()))
            if is_accept:
                accept[fa_state] = frozenset(tags)

        transitions: FrozenDict[FAState, FrozenDict[CharSet[C], FAState]] =FrozenDict({k: FrozenDict(v) for k, v in trans.items()})
        dead_states = [s for s in transitions if not transitions[s]]
        assert len(dead_states) <= 1, f"DFA can have at most one dead state, found {len(dead_states)}: {dead_states}"
        
        return cls(
                   universe=nfa.universe,
                   current=dfa_states[start],
                   accept=FrozenDict(accept),
                   transitions=transitions,
                   nfa2dfa=FrozenDict(dfa_states)
               )

    def runner(self) -> DFARunner[C]:
        return DFARunner.create(self)

    def run(self, input_seq: list[C]) -> DFARunner[C]:
        return self.runner().steps(self, input_seq)

    def match(self, input_seq: list[C]) -> bool:
        return self.run(input_seq).is_accepted(self)

@dataclass(frozen=True)
class NFA(Generic[C]):
    universe: CodeUniverse
    current: FAState
    accept: FrozenDict[FAState, frozenset[str]] = field(default_factory=FrozenDict)
    transitions: FrozenDict[FAState, FrozenDict[CharSet[C], frozenset[FAState]]] = field(default_factory=FrozenDict)
    epsilon: FrozenDict[FAState, frozenset[FAState]] = field(default_factory=FrozenDict)

    def clone(self) -> NFA[C]:
        state_map: dict[FAState, FAState] = {}
        def get_clone(s: FAState) -> FAState:
            if s not in state_map:
                state_map[s] = FAState()
            return state_map[s]
        new_start = get_clone(self.current)
        new_accept: FrozenDict[FAState, frozenset[str]] = FrozenDict({get_clone(a):b for a,b in self.accept.items()})
        new_transitions: dict[FAState, FrozenDict[CharSet[C], frozenset[FAState]]] = {}
        for k, v in self.transitions.items():
            new_transitions[get_clone(k)] = FrozenDict({
                c: frozenset(get_clone(s) for s in targets)
                for c, targets in v.items()
            })
        new_epsilon: FrozenDict[FAState, frozenset[FAState]] = FrozenDict({
            get_clone(k): frozenset(get_clone(s) for s in v)
            for k, v in self.epsilon.items()
        })
        return replace(self,
                        current=new_start,
                        accept=new_accept,
                        transitions=FrozenDict(new_transitions),
                        epsilon=new_epsilon)
    
    def tagged(self, tag: str, append:bool=False) -> NFA[C]:
        if append:
            return replace(self, accept=FrozenDict({a: (tags | frozenset({tag}) if tags else frozenset({tag})) for a, tags in self.accept.items()}))
        else:
            return replace(self, accept=FrozenDict({a: frozenset({tag}) for a in self.accept}))

    def closure(self, states: set[FAState] | frozenset[FAState]) -> frozenset[FAState]:
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
    def from_char(cls, char: C, *, universe: CodeUniverse, negation:bool = False,  tag: Optional[str] = None) -> NFA[C]:
        assert len(char) >= 1, "char cannot be empty"
        current: FAState = FAState()
        accept: FAState = FAState()
        charset: CharSet[C] = CharSet.create(char, universe=universe)
        if negation:
            charset = ~charset
        if charset.interval == tuple():
            raise CodepointError(f"Character {char!r} is not valid in the specified universe {universe}", offending=char, universe=universe)
        return cls(
                   universe=universe,
                   current=current, 
                   accept=FrozenDict({accept: frozenset({tag or f'{char!r}'})}),
                   transitions=FrozenDict({
                       current: FrozenDict({charset: frozenset({accept})})
                   }),
                   epsilon=FrozenDict())


    def then(self, other: NFA[C]) -> NFA[C]:
        if self.universe is not other.universe:
            raise MixedUniverseError("Cannot combine NFAs with different universes", offending=(self.universe, other.universe))
        this = self.clone()
            
        eps = {**this.epsilon}
        for a in this.accept:
            eps[a] = eps.get(a, frozenset()) | frozenset({other.current})
        
        for k, v in other.epsilon.items():
            eps[k] = eps.get(k, frozenset()) | v
    
        new_transitions = {**this.transitions}
        for k, v in other.transitions.items():
            new_transitions[k] = new_transitions.get(k, FrozenDict()) | v
            
        return this.__class__(
                              universe=this.universe,
                              current=this.current, 
                              accept=other.accept, 
                              transitions=FrozenDict(new_transitions), 
                              epsilon=FrozenDict(eps))
    
    def union(self, other: NFA[C]) -> NFA[C]:
        if self.universe is not other.universe:
            raise MixedUniverseError("Cannot combine NFAs with different universes", offending=(self.universe, other.universe))
        if self is other:
            return self
        new_current: FAState = FAState()
        eps = {new_current: frozenset({self.current, other.current})}
        for k, v in self.epsilon.items():
            eps[k] = eps.get(k, frozenset()) | v
        for k, v in other.epsilon.items():
            eps[k] = eps.get(k, frozenset()) | v
        
        new_transitions = {**self.transitions}
        for k, v in other.transitions.items():
            new_transitions[k] = new_transitions.get(k, FrozenDict()) | v
        return replace(self,
                       universe=self.universe,
                       current=new_current, 
                       accept=self.accept | other.accept, 
                       transitions=FrozenDict(new_transitions), 
                       epsilon=FrozenDict(eps))

    def star(self) -> NFA[C]:
        new_current: FAState = FAState()
        eps = {**self.epsilon, new_current: frozenset({self.current})}
        for a in self.accept:
            eps[a] = eps.get(a, frozenset()) | frozenset({self.current})
        return replace(self,
                        current=new_current, 
                        accept=self.accept | FrozenDict({new_current: frozenset()}), 
                        transitions=self.transitions, 
                        epsilon=FrozenDict(eps))
    
    def optional(self)->NFA[C]:
        new_current: FAState = FAState()
        eps = {**self.epsilon, new_current: frozenset({self.current})}
        return replace(self,
                        current=new_current, 
                        accept=self.accept | FrozenDict({new_current: frozenset()}), 
                        transitions=self.transitions, 
                        epsilon=FrozenDict(eps))
    
    def plus(self) -> NFA[C]:
        eps = {**self.epsilon}
        for a in self.accept:
            eps[a] = eps.get(a, frozenset()) | frozenset({self.current})
        return replace(self,
                        current=self.current, 
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
    
Automata = TypeVar('Automata', bound=Any, contravariant=True)
@dataclass(frozen=True)
class Runner(Protocol[C, Automata]):
    accepted: Tuple[Tuple[int, Any, frozenset[str]], ...] = field(default_factory=tuple)
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
    def resumable(self, a: Automata) -> frozenset[CharSet[C]]: ...
    def tags(self, a: Automata) -> frozenset[str]: ...
    def gen(self, a: Automata, times: int = 1) -> List[Tuple[List[C], frozenset[str]]]: 
        def gen_one(r: Self, a: Automata) -> Optional[Tuple[C, Self]]:
            possible_steps = r.resumable(a)
            if possible_steps:
                import random
                rnd = random.Random()
                ccls = rnd.choice(list(possible_steps))
                c = ccls.sample(rnd)
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
    current: frozenset[FAState] = field(default_factory=frozenset)
    @classmethod
    def create(cls, nfa: NFA[C]) -> NFARunner[C]:
        current = nfa.closure({nfa.current})
        return cls(current=frozenset(current), accepted=tuple())
    
    def step(self, nfa: NFA[C], symbol: C, pos: int) -> NFARunner[C]:
        next_states = set()
        for s in self.current:
            entry: FrozenDict[CharSet[C], frozenset[FAState]] = nfa.transitions.get(s, {})
            k: CharSet[C] = CharSet.create(symbol, universe=nfa.universe)
            if k in entry:
                next_states.update(entry[k])
            else:
                for char_class, targets in entry.items():
                    if isinstance(char_class, CharSet) and char_class(symbol):
                        next_states.update(targets)
        new_current = nfa.closure(next_states)
        new_accepted = self.accepted + tuple(((pos, a, tag) for a, tag in nfa.accept.items() if a in new_current))
        return NFARunner(current=frozenset(new_current), accepted=new_accepted)
    
    def is_accepted(self, nfa: NFA[C]) -> bool:
        return any(st in nfa.accept for st in self.current)
    
    def is_valid(self) -> bool:
        return bool(self.current)

    def resumable(self, nfa: NFA[C]) -> frozenset[CharSet[C]]:
        result: Set[CharSet[C]] = set()
        for s in self.current:
            result.update(nfa.transitions.get(s, {}).keys())
        return frozenset(result)

    def tags(self, nfa: NFA[C]) -> frozenset[str]:
        tags: Set[str] = set()
        for s in self.current:
            tags.update(nfa.accept.get(s, frozenset()))  
        return frozenset(tags)
    

@dataclass(frozen=True)
class DFARunner(Runner[C, DFA[C]]):
    current: Optional[FAState] = None

    @classmethod
    def create(cls, dfa: DFA[C]) -> DFARunner[C]:
        current = dfa.current
        return cls(current=current, accepted=tuple())
    
    def step(self, dfa: DFA[C], symbol: C, pos: int) -> DFARunner[C]:
        next_state: Optional[FAState] = None
        entry: FrozenDict[CharSet[C], FAState] = dfa.transitions.get(self.current, {})
        k: CharSet[C] = CharSet.create(symbol, universe=dfa.universe)
        if k in entry:
            next_state = entry[k]
        else:
            for char_class, targets in entry.items():
                if isinstance(char_class, CharSet) and char_class(symbol):
                    next_state = targets
                    break
        if next_state in dfa.accept:
            new_accepted = self.accepted + ((pos, next_state, dfa.accept[next_state]),)
            return DFARunner(current=next_state, accepted=new_accepted)
        else:
            return replace(self, current=next_state)



    def is_accepted(self, dfa: DFA[C]) -> bool:
        return self.current in dfa.accept

    def is_valid(self) -> bool:
        return bool(self.current)
    
    def resumable(self, dfa: DFA[C]) -> frozenset[CharSet[C]]:
        return frozenset(dfa.transitions.get(self.current, {}).keys())

    def tags(self, dfa: DFA[C]) -> frozenset[str]:
        return dfa.accept.get(self.current, frozenset())

        

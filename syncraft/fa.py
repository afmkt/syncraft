from __future__ import annotations

from typing import (
    TypeVar, Optional, Generic, Tuple, ClassVar, Set, Protocol, Any, Self, List, Callable
)
from typing import Dict
from dataclasses import dataclass, field, replace
from syncraft.algebra import (
    SyncraftError
)
from collections import deque
from syncraft.constraint import  FrozenDict
from syncraft.charset import CharSet, CodeUniverse, MixedUniverseError, CodepointError
from enum import Enum
from collections import defaultdict




C = TypeVar('C', bound=str | int | Enum)

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
    accept: FrozenDict[FAState, frozenset[str | Enum]] = field(default_factory=FrozenDict)
    transitions: FrozenDict[FAState, FrozenDict[CharSet[C], FAState]] = field(default_factory=FrozenDict)
    nfa2dfa: FrozenDict[frozenset[FAState], FAState]= field(default_factory=FrozenDict) 

    @property
    def minimize(self) -> DFA[C]:
        # 1. Gather all states (not just those with transitions)
        all_states: Set[FAState] = set(self.transitions.keys()) | set(self.accept.keys()) | {self.current}

        # 2. Initial partition: accepting vs non-accepting
        accept_states = frozenset(s for s in all_states if s in self.accept)
        non_accept_states = frozenset(all_states - accept_states)
        P: List[frozenset[FAState]] = []
        if accept_states:
            P.append(accept_states)
        if non_accept_states:
            P.append(non_accept_states)

        # Worklist of partitions to refine
        W: List[frozenset[FAState]] = P.copy()

        # Hopcroft refinement
        while W:
            A = W.pop()
            # Find all predecessors that transition into A
            symbol_to_predecessors: Dict[CharSet[C], Set[FAState]] = defaultdict(set)
            for q, trans in self.transitions.items():
                for charset, target in trans.items():
                    if target in A:
                        symbol_to_predecessors[charset].add(q)

            newP: List[frozenset[FAState]] = []
            for Y in P:
                preds = set().union(*symbol_to_predecessors.values())
                intersection = Y & preds
                difference = Y - preds
                if intersection and difference:
                    newP.extend([frozenset(intersection), frozenset(difference)])
                    if Y in W:
                        W.remove(Y)
                        W.extend([frozenset(intersection), frozenset(difference)])
                    else:
                        # Add the smaller subset to the worklist
                        if len(intersection) <= len(difference):
                            W.append(frozenset(intersection))
                        else:
                            W.append(frozenset(difference))
                else:
                    newP.append(Y)
            P = newP

        # 3. Build representative states
        state_map: Dict[FAState, FAState] = {}
        new_states: Dict[frozenset[FAState], FAState] = {}
        for block in P:
            rep = FAState()
            new_states[block] = rep
            for s in block:
                state_map[s] = rep

        # 4. Build transitions
        new_transitions: Dict[FAState, Dict[CharSet[C], FAState]] = {}
        for block, rep in new_states.items():
            new_transitions[rep] = {}
            orig = next(iter(block))
            for charset, target in self.transitions.get(orig, {}).items():
                new_transitions[rep][charset] = state_map[target]

        # 5. Build accept states
        new_accept: Dict[FAState, frozenset[str | Enum]] = {}
        for block, rep in new_states.items():
            if any(s in self.accept for s in block):
                labels = frozenset().union(*(self.accept.get(s, frozenset()) for s in block))
                new_accept[rep] = labels


        # 6. New start state
        new_start = state_map[self.current]

        return DFA(
            universe=self.universe,
            current=new_start,
            accept=FrozenDict(new_accept),
            transitions=FrozenDict({k: FrozenDict(v) for k, v in new_transitions.items()}),
            nfa2dfa=FrozenDict()
        )
    



    def tagged(self, tag: str | Enum, append:bool=False) -> DFA[C]:
        if append:
            return replace(self, accept=FrozenDict({a: (tags | frozenset({tag})) for a, tags in self.accept.items()}))
        else:
            return replace(self, accept=FrozenDict({a: frozenset({tag}) for a in self.accept}))


    @staticmethod
    def _complete_transitions(universe: CodeUniverse,
                            transitions: dict[FAState, dict[CharSet[C], FAState]],
                            accept: dict[FAState, frozenset]) -> tuple[dict[FAState, dict[CharSet[C], FAState]], dict[FAState, frozenset], FAState]:
        # copy inputs shallow
        trans_copy: Dict[FAState, Dict[CharSet[C], FAState]] = {s: dict(m) for s, m in transitions.items()}

        # create sink state
        sink = FAState()

        # ensure sink exists in map to be consistent
        trans_copy.setdefault(sink, {})

        # For each state, compute covered charset and add missing piece mapped to sink
        for s, mapping in list(trans_copy.items()):
            # union all key charsets into 'covered'
            covered: CharSet[C] = CharSet.none(universe)
            for cs in mapping.keys():
                covered = covered | cs
            missing = (-covered)
            if missing.interval:  # any uncovered codepoints
                # If the state's mapping already has a CharSet that equals missing, merge would have caught it
                mapping[missing] = sink
                trans_copy[s] = mapping

        # ensure sink loops to itself on all chars
        trans_copy[sink] = {CharSet.any(universe): sink}

        # Optionally: merge adjacent pieces in each state's mapping (keeps mapping compact)
        for s, mapping in list(trans_copy.items()):
            trans_copy[s] = DFA.merge_adjacent_transitions(universe, mapping)

        return trans_copy, accept, sink



    @property
    def complement(self) -> DFA[C]:
        universe = self.universe
        # Make a copy of transitions and add a sink for missing chars
        transitions: dict[FAState, dict[CharSet[C], FAState]] = {s: dict(t) for s, t in self.transitions.items()}
        sink = FAState()
        for s, trans in transitions.items():
            # union of all existing intervals in this state
            covered: CharSet[C] = CharSet.none(universe)
            for cs in trans.keys():
                covered |= cs
            missing = -covered
            if missing.interval:  # any uncovered chars
                trans[missing] = sink
        # sink transitions to itself on any char
        transitions[sink] = {CharSet.any(universe): sink}

        # flip accepting states
        all_states = set(transitions.keys())
        new_accept: dict[FAState, frozenset[str | Enum]] = {s: frozenset() for s in all_states if s not in self.accept}

        # freeze everything
        frozen_trans: FrozenDict[FAState, FrozenDict[CharSet[C], FAState]] = FrozenDict({s: FrozenDict(t) for s, t in transitions.items()})
        frozen_accept: FrozenDict[FAState, frozenset[str | Enum]] = FrozenDict(new_accept)
        return DFA(
            universe=universe,
            current=self.current,
            accept=frozen_accept,
            transitions=frozen_trans,
            nfa2dfa=self.nfa2dfa
        )
    
    def __neg__(self) -> DFA[C]:
        return self.complement
                       

    def _product(self, other: "DFA[C]", accept_func: Callable[[bool, bool], bool]) -> "DFA[C]":
        if self.universe != other.universe:
            raise MixedUniverseError("Cannot combine DFAs with different universes",
                                    offender=(self.universe, other.universe))

        # sentinel sink states for "no transition" from a DFA on a piece
        sink1 = FAState()
        sink2 = FAState()

        # map (s1, s2) -> new FAState
        state_map: dict[tuple[FAState, FAState], FAState] = {}
        start_pair = (self.current, other.current)
        state_map[start_pair] = FAState()
        work_list = deque([start_pair])

        transitions: dict[FAState, dict[CharSet[C], FAState]] = {}
        accept: dict[FAState, frozenset[str | Enum]] = {}

        while work_list:
            s1, s2 = work_list.popleft()
            new_state = state_map[(s1, s2)]

            trans1: dict[CharSet[C], FAState] = dict(self.transitions.get(s1, {}))
            trans2: dict[CharSet[C], FAState] = dict(other.transitions.get(s2, {}))

            # collect all intervals from both transition maps and partition them
            intvs: List[Tuple[int, int]] = []
            for cs in trans1.keys():
                intvs.extend(cs.interval)
            for cs in trans2.keys():
                intvs.extend(cs.interval)

            # If there are no intervals on either side, we leave transitions empty.
            if not intvs:
                transitions[new_state] = {}
            else:
                pieces = CharSet.partition_charsets(intvs)
                next_trans: dict[CharSet[C], FAState] = {}

                for p in pieces:
                    piece_cs: CharSet[C] = CharSet.from_interval([p], self.universe)

                    # find target in trans1 that covers this piece (if any)
                    t1 = None
                    for cs1, tgt1 in trans1.items():
                        if cs1.overlaps(p):
                            t1 = tgt1
                            break

                    # find target in trans2 that covers this piece (if any)
                    t2 = None
                    for cs2, tgt2 in trans2.items():
                        if cs2.overlaps(p):
                            t2 = tgt2
                            break

                    # if neither automaton moves on this piece, skip it
                    if t1 is None and t2 is None:
                        continue

                    tgt_pair = (t1 if t1 is not None else sink1, t2 if t2 is not None else sink2)
                    if tgt_pair not in state_map:
                        state_map[tgt_pair] = FAState()
                        work_list.append(tgt_pair)

                    next_trans[piece_cs] = state_map[tgt_pair]

                # merge adjacent CharSets that target the same state (keeps DFAs tidy)
                transitions[new_state] = DFA.merge_adjacent_transitions(self.universe, next_trans)

            # acceptance of the product state
            b1 = s1 in self.accept
            b2 = s2 in other.accept
            if accept_func(b1, b2):
                tags = set(self.accept.get(s1, frozenset())) | set(other.accept.get(s2, frozenset()))
                accept[new_state] = frozenset(tags)

        # Optionally: we created sink1/sink2 FAState values; if any pair uses them they are already in state_map
        # Build frozen structures
        frozen_transitions: FrozenDict[FAState, FrozenDict[CharSet[C], FAState]] = FrozenDict({
            s: FrozenDict(t) for s, t in transitions.items()
        })
        frozen_accept: FrozenDict[FAState, frozenset[str | Enum]] = FrozenDict(accept)

        return DFA(
            universe=self.universe,
            current=state_map[start_pair],
            accept=frozen_accept,
            transitions=frozen_transitions,
            nfa2dfa=FrozenDict()
        )


    def intersection(self, other: DFA[C]) -> DFA[C]:
        return self._product(other, lambda b1, b2: b1 and b2)    
    def __and__(self, other: DFA[C]) -> DFA[C]:
        return self.intersection(other)

    def union(self, other: DFA[C]) -> DFA[C]:
        return self._product(other, lambda b1, b2: b1 or b2)
    def __or__(self, other: DFA[C]) -> DFA[C]:
        return self.union(other)
    
    def difference(self, other: DFA[C]) -> DFA[C]:
        return self._product(other, lambda b1, b2: b1 and not b2)
    def __sub__(self, other: DFA[C]) -> DFA[C]:
        return self.difference(other)
    
    @property
    def nfa(self) -> NFA[C]:
        all_states: set[FAState] = set(self.transitions.keys())
        for trans in self.transitions.values():
            all_states.update(trans.values())
        all_states.update(self.accept.keys())
        all_states.add(self.current)
        state_map: dict[FAState, FAState] = {s: FAState() for s in all_states}
        nfa_trans: dict[FAState, FrozenDict[CharSet[C], frozenset[FAState]]] = {}
        for s, trans in self.transitions.items():
            nfa_s = state_map[s]
            nfa_trans[nfa_s] = FrozenDict(
                {cs: frozenset({state_map[tgt]}) for cs, tgt in trans.items()}
            )
        nfa_accept: FrozenDict[FAState, frozenset[str | Enum]] = FrozenDict(
            {state_map[s]: tags for s, tags in self.accept.items()}
        )
        return NFA(
            universe=self.universe,
            current=state_map[self.current],
            accept=nfa_accept,
            transitions=FrozenDict(nfa_trans),
            epsilon=FrozenDict()  
        )
    
    @property
    def star(self) -> DFA[C]:
        return self.nfa.star.dfa
    @property
    def plus(self) -> DFA[C]:
        return self.nfa.plus.dfa
    @property
    def optional(self) -> DFA[C]:
        return self.nfa.optional.dfa
    def __invert__(self) -> DFA[C]:
        return self.optional


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
        accept: dict[FAState, frozenset[str | Enum]] = {}
        for nfa_states, fa_state in dfa_states.items():
            tags: Set[str | Enum] = set()
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

    def run(self, input_seq: str | bytes | list[Enum]) -> DFARunner[C]:
        return self.runner().steps(self, input_seq)

    def match(self, input_seq: str | bytes | list[Enum]) -> bool:
        return self.run(input_seq).is_accepted(self)

@dataclass(frozen=True)
class NFA(Generic[C]):
    universe: CodeUniverse
    current: FAState
    accept: FrozenDict[FAState, frozenset[str | Enum]] = field(default_factory=FrozenDict)
    transitions: FrozenDict[FAState, FrozenDict[CharSet[C], frozenset[FAState]]] = field(default_factory=FrozenDict)
    epsilon: FrozenDict[FAState, frozenset[FAState]] = field(default_factory=FrozenDict)

    @property
    def dfa(self) -> DFA[C]:
        return DFA.from_nfa(self)

    def clone(self) -> NFA[C]:
        state_map: dict[FAState, FAState] = {}
        def get_clone(s: FAState) -> FAState:
            if s not in state_map:
                state_map[s] = FAState()
            return state_map[s]
        new_start = get_clone(self.current)
        new_accept: FrozenDict[FAState, frozenset[str | Enum]] = FrozenDict({get_clone(a):b for a,b in self.accept.items()})
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
    
    def tagged(self, tag: str | Enum, append:bool=False) -> NFA[C]:
        if append:
            return replace(self, accept=FrozenDict({a: (tags | frozenset({tag})) for a, tags in self.accept.items()}))
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

    def run(self, input_seq: str | bytes | list[Enum]) -> NFARunner[C]:
        return self.runner().steps(self, input_seq)

    def match(self, input_seq: str | bytes | list[Enum]) -> bool:
        return self.run(input_seq).is_accepted(self)

    @classmethod
    def _from_charset(cls, c: CharSet[C], tag: Optional[str|Enum] = None) -> NFA[C]:
        assert c.interval != tuple(), "charset cannot be empty"
        current: FAState = FAState()
        accept: FAState = FAState()
        return cls(
                   universe=c.universe,
                   current=current, 
                   accept=FrozenDict({accept: frozenset({tag}) if tag else frozenset()}),
                   transitions=FrozenDict({
                       current: FrozenDict({c: frozenset({accept})})
                   }),
                   epsilon=FrozenDict())

    @classmethod
    def from_charset(cls, 
                  char: str | bytes | list[Enum], 
                  universe: CodeUniverse, 
                  negation:bool = False,  
                  tag: Optional[str|Enum] = None) -> NFA[Any]:
        charset: CharSet[C] = CharSet.create(char, universe=universe)
        if negation:
            charset = -charset
        if charset.interval == tuple():
            raise CodepointError(f"Character {char!r} is not valid in the specified universe {universe}", offender=char, universe=universe)
        return cls._from_charset(charset, tag=tag)


    def then(self, other: NFA[C]) -> NFA[C]:
        if self.universe != other.universe:
            raise MixedUniverseError("Cannot combine NFAs with different universes", offender=(self.universe, other.universe))
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
    def __rshift__(self, other: NFA[C]) -> NFA[C]:
        return self.then(other)
    
    def union(self, other: NFA[C]) -> NFA[C]:
        if self.universe != other.universe:
            raise MixedUniverseError("Cannot combine NFAs with different universes", offender=(self.universe, other.universe))
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
    def __or__(self, other: NFA[C]) -> NFA[C]:
        return self.union(other)

    @property
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
    
    @property
    def optional(self)->NFA[C]:
        new_current: FAState = FAState()
        eps = {**self.epsilon, new_current: frozenset({self.current})}
        return replace(self,
                        current=new_current, 
                        accept=self.accept | FrozenDict({new_current: frozenset()}), 
                        transitions=self.transitions, 
                        epsilon=FrozenDict(eps))
    def __invert__(self) -> NFA[C]:
        return self.optional

    @property
    def plus(self) -> NFA[C]:
        eps = {**self.epsilon}
        for a in self.accept:
            eps[a] = eps.get(a, frozenset()) | frozenset({self.current})
        return replace(self,
                        current=self.current, 
                        accept=self.accept, 
                        transitions=self.transitions, 
                        epsilon=FrozenDict(eps))
    
    def __pos__(self) -> NFA[C]:
        return self.plus
    
    def many(self, at_least: int = 1, at_most: Optional[int] = None) -> NFA[C]:
        if at_least <=0 or (at_most is not None and at_most < at_least):
            raise SyncraftError(f"Invalid arguments for many: at_least={at_least}, at_most={at_most}", offender=(at_least, at_most), expect="at_least>0 and (at_most is None or at_most>=at_least)")
        if at_least == 1 and at_most is None:
            return self.plus
        nfa = self
        for _ in range(at_least - 1):
            nfa = nfa.then(self)
        if at_most is None:
            nfa = nfa.then(self.star)
        else:
            optional_count = at_most - at_least
            for _ in range(optional_count):
                nfa = nfa.then(self.optional)
        return nfa
    
Automata = TypeVar('Automata', bound=Any, contravariant=True)
@dataclass(frozen=True)
class Runner(Protocol[C, Automata]):
    accepted: Tuple[Tuple[int, Any, frozenset[str | Enum]], ...] = field(default_factory=tuple)
    @classmethod
    def create(cls, a: Automata) -> Self: ...
    def step(self, a: Automata, symbol: C, pos: int) -> Self: ...
    def steps(self, fa: Automata, input: str | bytes | list[Enum]) -> Self:
        runner = self
        for i, symbol in enumerate(input):
            runner = runner.step(fa, symbol, i)
            if not runner.is_valid():
                break  # no valid transitions, stop early
        return replace(runner, accepted=tuple(sorted(runner.accepted, key=lambda x: x[0], reverse=True)))

    def is_accepted(self, a: Automata) -> bool: ...
    def is_valid(self) -> bool: ...
    def resumable(self, a: Automata) -> frozenset[CharSet[C]]: ...
    def tags(self, a: Automata) -> frozenset[str|Enum]: ...
    def gen(self, a: Automata, times: int = 1) -> List[Tuple[List[Enum] | str | bytes, frozenset[str | Enum]]]:
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
        ret: List[Tuple[List[Enum] | str | bytes, frozenset[str | Enum]]] = []
        runner = self
        for _ in range(times):
            txt: List[Any]= []
            while runner.resumable(a):
                match gen_one(runner, a):
                    case None:
                        break
                    case (c, r):
                        txt.append(c)
                        runner = r
                if runner.is_accepted(a):
                    if len(txt) > 0:
                        if isinstance(txt[0], str):
                            ret.append((''.join(txt), runner.tags(a)))
                        elif isinstance(txt[0], int):
                            ret.append((bytes(txt), runner.tags(a)))
                        else:
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
        ss = [symbol] if isinstance(symbol, Enum) else (bytes(symbol) if isinstance(symbol, int) else symbol)
        assert len(ss) == 1, "symbol must be a single character"
        next_states = set()
        for s in self.current:
            entry: FrozenDict[CharSet[C], frozenset[FAState]] = nfa.transitions.get(s, {})
            k: CharSet[C] = CharSet.create(ss, universe=nfa.universe)
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

    def tags(self, nfa: NFA[C]) -> frozenset[str | Enum]:
        tags: Set[str | Enum] = set()
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
        ss = [symbol] if isinstance(symbol, Enum) else (bytes([symbol]) if isinstance(symbol, int) else symbol)
        assert len(ss) == 1, "symbol must be a single character"
        next_state: Optional[FAState] = None
        entry: FrozenDict[CharSet[C], FAState] = dfa.transitions.get(self.current, {})
        k: CharSet[C] = CharSet.create(ss, universe=dfa.universe)
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

    def tags(self, dfa: DFA[C]) -> frozenset[str|Enum]:
        return dfa.accept.get(self.current, frozenset())

        
@dataclass(frozen=True)
class Automaton(Generic[C]):
    fa: NFA[C] | DFA[C]
    runner: Runner[C, NFA[C]] | Runner[C, DFA[C]]

    @property
    def universe(self) -> CodeUniverse:
        return self.fa.universe
    


from __future__ import annotations

from typing import (
    TypeVar, Optional, Generic, Tuple, ClassVar, Set, Any, List,
    Callable, Dict, Sequence, Union, Iterator, Literal, Hashable
)

from dataclasses import dataclass, field, replace

from collections import deque
from syncraft.utils import  FrozenDict

from syncraft.charset import CharSet, CharSetFactory
from syncraft.alphabet import AlphabetProtocol, Alphabet
from enum import Enum
from collections import defaultdict
from functools import reduce
import random

Tag = str | Enum
C = TypeVar('C', bound=Hashable)
FAState = int
FAStateBuilder = Callable[[], FAState]
@dataclass(frozen=True, slots=True)
class FAStateFactory:
    _counter: ClassVar[int] = 0  # shared across all states
    # id: int = field(default_factory=lambda: FAStateFactory._next_id())

    @classmethod
    def builder(cls, init: int = 0) -> FAStateBuilder:
        def build() -> FAState:
            nonlocal init
            init += 1
            return init
        return build

    @classmethod
    def next(cls) -> int:
        val = cls._counter
        cls._counter += 1
        return val
    


@dataclass(frozen=True, slots=True)
class ReverseDFA(Generic[C]):
    cs_factory: CharSetFactory[C]
    final: FAState
    accept: FrozenDict[Tag|None, frozenset[FAState]] = field(default_factory=FrozenDict)    
    transitions: FrozenDict[FAState, FrozenDict[CharSet, FAState]] = field(default_factory=FrozenDict)

    def gen(self, tag: Tag | None, rnd: random.Random) -> C | Tuple[C, ...]:
        current_states = self.accept.get(tag, frozenset())
        assert current_states, f"Tag '{tag}' not accepted by DFA"
        current = rnd.choice(list(current_states))
        result: List[C] = []
        sample_f = self.cs_factory.sample
        while current != self.final:
            if current not in self.transitions:
                break
            char_set: CharSet
            next_state: FAState 
            char_set, next_state = rnd.choice(list(self.transitions[current].items()))
            result.append(sample_f(char_set, rnd))
            current = next_state
        return self.cs_factory.alphabet.concat(result[::-1])

@dataclass(frozen=True, slots=True)
class DFA(Generic[C]):
    cs_factory: CharSetFactory[C]
    init: FAState
    accept: FrozenDict[FAState, frozenset[Tag]] = field(default_factory=FrozenDict)
    transitions: FrozenDict[FAState, FrozenDict[CharSet, FAState]] = field(default_factory=FrozenDict)

    @property
    def reverse(self) -> ReverseDFA[C]:
        # Build reverse transitions
        acc_map: Dict[Tag, Set[FAState]] = defaultdict(set)
        for s, tags in self.accept.items():
            for t in tags:
                acc_map[t].add(s)

        trans: Dict[FAState, Dict[CharSet, FAState]] = defaultdict(dict)  
        for s, mapping in self.transitions.items():
            for cs, tgt in mapping.items():
                trans[tgt][cs] = s
        return ReverseDFA(
            cs_factory=self.cs_factory,
            final=self.init,
            accept=FrozenDict({t: frozenset(ss) for t, ss in acc_map.items()}),
            transitions=FrozenDict({s: FrozenDict(m) for s,m in trans.items()}))
    
    
    @property
    def normalized(self)->DFA[C]:
        fabuilder = FAStateFactory.builder()
        
        states: Set[FAState] = set(self.transitions.keys()) | set(self.accept.keys()) | {self.init}
        st_map: dict[FAState, FAState] = {k: fabuilder() for k in states}
        new_universe = self.cs_factory
        new_init = st_map[self.init]
        new_accept: FrozenDict[FAState, frozenset[Tag]] = FrozenDict({st_map[s]: v for s, v in self.accept.items()})
        new_trans: dict[FAState, FrozenDict[CharSet, FAState]] = {}
        for k, v in self.transitions.items():
            new_trans[st_map[k]] = FrozenDict({cs: st_map[tgt] for cs, tgt in v.items()})

        return DFA(cs_factory=new_universe,
                   init=new_init, 
                   accept=new_accept, 
                   transitions=FrozenDict(new_trans))


    
    @property
    def minimize(self) -> DFA[C]:
        """Return the (language) minimal DFA using Hopcroft's algorithm.

        This replaces the previous implementation which incorrectly merged states by
        unifying predecessors across all symbols. We:
          1. Build a global partition of the alphabet from all transition CharSets.
          2. For each state and each partition piece, define a total transition
             (adding a synthetic sink only if needed for missing pieces).
          3. Apply Hopcroft refinement using piece indices as alphabet symbols.
          4. Reconstruct minimized DFA merging contiguous intervals that target the
             same new state.
        """
        if not self.transitions:
            # Edge: single state DFA (maybe accepting)
            return self

        # alphabet = self.alphabet
        fabuilder = FAStateFactory.builder()

        # Collect all states explicitly referenced.
        states: Set[FAState] = set(self.transitions.keys()) | set(self.accept.keys())
        for trans in self.transitions.values():
            states.update(trans.values())
        states.add(self.init)

        # Build global disjoint alphabet partition from all outgoing CharSet intervals.
        all_intvs: List[Tuple[int, int]] = []
        for mapping in self.transitions.values():
            for cs in mapping.keys():
                all_intvs.extend(cs)
        # If no intervals (degenerate), return self
        if not all_intvs:
            return self
        pieces: List[Tuple[int, int]] = list(self.cs_factory.partition_charsets(all_intvs))
        piece_charsets: List[CharSet] = [self.cs_factory.from_interval([p]) for p in pieces]

        # Map: state -> list[target_state or None] per piece; also build reverse maps.
        sink: Optional[FAState] = None
        # reverse[piece_index][target_state] = set(source_states)
        reverse: List[Dict[FAState, Set[FAState]]] = [defaultdict(set) for _ in piece_charsets]

        # For each state we keep parallel arrays:
        #  - targets: the (possibly sink) target for each piece (used during refinement)
        #  - real_mask: True if the transition existed in the original DFA, False if it was synthesized (missing piece -> sink)
        per_state_targets: Dict[FAState, List[FAState]] = {}
        per_state_real_mask: Dict[FAState, List[bool]] = {}
        for s in states:
            targets: List[FAState] = []
            real_mask: List[bool] = []
            mapping = self.transitions.get(s, {})
            for i, pcs in enumerate(piece_charsets):
                tgt: Optional[FAState] = None
                # Find matching outgoing transition (deterministic => first overlap)
                for cs, dest in mapping.items():
                    # CharSets used in DFA transitions are disjoint per state, so cheap overlap
                    if self.cs_factory.overlaps(cs, pcs[0]):
                        tgt = dest
                        break
                if tgt is None:
                    # Missing piece -> implicit dead sink
                    if sink is None:
                        sink = fabuilder()
                    tgt = sink
                    real_mask.append(False)
                else:
                    real_mask.append(True)
                targets.append(tgt)
                reverse[i][tgt].add(s)
            per_state_targets[s] = targets
            per_state_real_mask[s] = real_mask

        if sink is not None and sink not in states:
            # Add sink transitions: loops to itself on every piece
            states.add(sink)
            per_state_targets[sink] = [sink] * len(piece_charsets)
            per_state_real_mask[sink] = [False] * len(piece_charsets)
            for i in range(len(piece_charsets)):
                reverse[i][sink].add(sink)

        # Initial partition: accepting vs non-accepting.
        accept_block = frozenset(s for s in states if s in self.accept)
        non_accept_block = frozenset(states - accept_block)
        P: List[frozenset[FAState]] = []
        if accept_block:
            P.append(accept_block)
        if non_accept_block:
            P.append(non_accept_block)
        W: Set[frozenset[FAState]] = set(P)  # use set for O(1) lookup

        # Hopcroft refinement using piece indices.
        while W:
            A = W.pop()
            # For each symbol piece, compute predecessors leading into A.
            for i in range(len(piece_charsets)):
                # Gather preds: union of reverse[i][t] for t in A
                preds: Set[FAState] = set()
                add = preds.add
                rev_i = reverse[i]
                for t in A:
                    sset = rev_i.get(t)
                    if sset:
                        for s in sset:
                            add(s)
                if not preds:
                    continue
                new_P: List[frozenset[FAState]] = []
                for Y in P:
                    inter = Y & preds
                    diff = Y - preds
                    if inter and diff:
                        inter_fs = frozenset(inter)
                        diff_fs = frozenset(diff)
                        new_P.extend([inter_fs, diff_fs])
                        if Y in W:
                            W.remove(Y)
                            # add both parts
                            if len(inter) <= len(diff):
                                W.add(inter_fs)
                            else:
                                W.add(diff_fs)
                        else:
                            # add smaller part
                            if len(inter) <= len(diff):
                                W.add(inter_fs)
                            else:
                                W.add(diff_fs)
                    else:
                        new_P.append(Y)
                P = new_P

        # Map old states to new representatives
        block_rep: Dict[FAState, FAState] = {}
        new_accept: Dict[FAState, frozenset[Tag]] = {}
        for block in P:
            rep = fabuilder()
            for s in block:
                block_rep[s] = rep
            # Union tags if any state accepting
            tags: Set[Tag] = set()
            accepting = False
            for s in block:
                if s in self.accept:
                    accepting = True
                    tags.update(self.accept.get(s, frozenset()))
            if accepting:
                new_accept[rep] = frozenset(tags)

        # Rebuild transitions only for pieces that were REAL in the original DFA (skip synthesized sink edges)
        new_transitions: Dict[FAState, Dict[CharSet, FAState]] = {}
        for block in P:
            exemplar = next(iter(block))
            rep = block_rep[exemplar]
            targets = per_state_targets[exemplar]
            rm = per_state_real_mask.get(exemplar)
            if rm is None:
                rm = [False] * len(pieces)  # treat all as synthetic
            real_mask = rm
            grouped: List[Tuple[List[Tuple[int, int]], FAState]] = []
            for idx, tgt in enumerate(targets):
                if not real_mask[idx]:
                    continue  # Skip synthesized edge
                tgt_rep = block_rep.get(tgt)
                if tgt_rep is None:
                    continue
                if grouped and grouped[-1][1] == tgt_rep:
                    grouped[-1][0].append(pieces[idx])
                else:
                    grouped.append(([pieces[idx]], tgt_rep))
            rep_trans: Dict[CharSet, FAState] = {}
            for intv_list, tgt_rep in grouped:
                cs = self.cs_factory.from_interval(intv_list)
                rep_trans[cs] = tgt_rep
            if rep_trans:
                # Optional: merge adjacent for same target (already contiguous grouping but safe)
                rep_trans = DFA.merge_adjacent_transitions(self.cs_factory, rep_trans)
                new_transitions[rep] = rep_trans

        # Prune unreachable states (e.g. sink representative if all synthesized edges were removed)
        reachable: Set[FAState] = set()
        work = [block_rep[self.init]]
        while work:
            s = work.pop()
            if s in reachable:
                continue
            reachable.add(s)
            for tgt in new_transitions.get(s, {}).values():
                if tgt not in reachable:
                    work.append(tgt)
        new_accept = {s: tags for s, tags in new_accept.items() if s in reachable}
        new_transitions = {s: m for s, m in new_transitions.items() if s in reachable}

        new_init = block_rep[self.init]

        return DFA(
            cs_factory=self.cs_factory,
            init=new_init,
            accept=FrozenDict(new_accept),
            transitions=FrozenDict({s: FrozenDict(m) for s, m in new_transitions.items()})
        )
    



    def tagged(self, tag: Tag) -> DFA[C]:
        return replace(self, accept=FrozenDict({a: frozenset({tag}) for a in self.accept}))
        
    @property
    def any(self) -> DFA[C]:
        cs_factory = self.cs_factory
        # Single state DFA accepting everything
        s = FAStateFactory.next()
        transitions: FrozenDict[FAState, FrozenDict[CharSet, FAState]] = FrozenDict({s: FrozenDict({cs_factory.any(): s})})
        accept: FrozenDict[FAState, frozenset[Tag]] = FrozenDict({s: frozenset()})
        return DFA(
            cs_factory=cs_factory,
            init=s,
            accept=accept,
            transitions=transitions
        )
    @property
    def complement(self) -> DFA[C]:
        return self.any.difference(self)
    
    def __neg__(self) -> DFA[C]:
        return self.complement
                       

    def _product(self, other: DFA[C], 
                 op: Literal['intersection', 'union', 'difference'],
                 accept_func: Callable[[Tuple[bool, frozenset[Tag]], Tuple[bool, frozenset[Tag]]], Tuple[bool, frozenset[Tag]]]) -> "DFA[C]":
        assert self.cs_factory == other.cs_factory, "Cannot combine DFAs with different universes"
        cs_factory = self.cs_factory
        # sentinel sink states for "no transition" from a DFA on a piece
        sink1 = FAStateFactory.next()
        sink2 = FAStateFactory.next()

        # map (s1, s2) -> new FAState
        state_map: dict[tuple[FAState, FAState], FAState] = {}
        start_pair = (self.init, other.init)
        state_map[start_pair] = FAStateFactory.next()
        work_list = deque([start_pair])

        transitions: dict[FAState, dict[CharSet, FAState]] = {}
        accept: dict[FAState, frozenset[Tag]] = {}

        while work_list:
            s1, s2 = work_list.popleft()
            new_state = state_map[(s1, s2)]

            trans1: dict[CharSet, FAState] = dict(self.transitions.get(s1, {}))
            trans2: dict[CharSet, FAState] = dict(other.transitions.get(s2, {}))

            # collect all intervals from both transition maps and partition them
            lintvs: List[Tuple[int, int]] = []
            rintvs: List[Tuple[int, int]] = []
            for cs in trans1.keys():
                lintvs.extend(cs)
            for cs in trans2.keys():
                rintvs.extend(cs)

            # If there are no intervals on either side, we leave transitions empty.
            if not lintvs and not rintvs:
                transitions[new_state] = {}
            else:
                match op:
                    case 'intersection':
                        pieces = cs_factory.intersect_interval(lintvs, rintvs)
                    case 'union':
                        pieces = cs_factory.partition_charsets(lintvs + rintvs)
                    case 'difference':
                        pieces = cs_factory.difference_interval(lintvs, rintvs)
                next_trans: dict[CharSet, FAState] = {}

                for p in pieces:
                    piece_cs: CharSet = cs_factory.from_interval([p])

                    # find target in trans1 that covers this piece (if any)
                    t1 = None
                    for cs1, tgt1 in trans1.items():
                        if cs_factory.overlaps(cs1, p):
                            t1 = tgt1
                            break

                    # find target in trans2 that covers this piece (if any)
                    t2 = None
                    for cs2, tgt2 in trans2.items():
                        if cs_factory.overlaps(cs2, p):
                            t2 = tgt2
                            break

                    # if neither automaton moves on this piece, skip it
                    if t1 is None and t2 is None:
                        continue

                    tgt_pair = (t1 if t1 is not None else sink1, t2 if t2 is not None else sink2)
                    if tgt_pair not in state_map:
                        state_map[tgt_pair] = FAStateFactory.next()
                        work_list.append(tgt_pair)

                    next_trans[piece_cs] = state_map[tgt_pair]

                # merge adjacent CharSets that target the same state (keeps DFAs tidy)
                transitions[new_state] = DFA.merge_adjacent_transitions(cs_factory, next_trans)

            # acceptance of the product state
            b1 = s1 in self.accept
            b2 = s2 in other.accept
            rb, rs = accept_func((b1, self.accept.get(s1, frozenset())), (b2, other.accept.get(s2, frozenset())))
            if rb:
                accept[new_state] = rs

        # Optionally: we created sink1/sink2 FAState values; if any pair uses them they are already in state_map
        # Build frozen structures
        frozen_transitions: FrozenDict[FAState, FrozenDict[CharSet, FAState]] = FrozenDict({
            s: FrozenDict(t) for s, t in transitions.items()
        })
        frozen_accept: FrozenDict[FAState, frozenset[Tag]] = FrozenDict(accept)

        return DFA(
            cs_factory=cs_factory,
            init=state_map[start_pair],
            accept=frozen_accept,
            transitions=frozen_transitions            
        )


    def intersection(self, other: DFA[C]) -> DFA[C]:
        def accept_func(a: Tuple[bool, frozenset[Tag]], b: Tuple[bool, frozenset[Tag]]) -> Tuple[bool, frozenset[Tag]]:
            accepts = a[0] and b[0]
            tags = a[1] | b[1] if accepts else frozenset()
            return (accepts, tags)
        return self._product(other, 'intersection', accept_func)    
    def __and__(self, other: DFA[C]) -> DFA[C]:
        return self.intersection(other)

    def union(self, other: DFA[C]) -> DFA[C]:
        def accept_func(a: Tuple[bool, frozenset[Tag]], b: Tuple[bool, frozenset[Tag]]) -> Tuple[bool, frozenset[Tag]]:
            accepts = a[0] or b[0]
            tags = a[1] | b[1] if accepts else frozenset()
            return (accepts, tags)
        return self._product(other,'union', accept_func)
    def __or__(self, other: DFA[C]) -> DFA[C]:
        return self.union(other)
    
    def difference(self, other: DFA[C]) -> DFA[C]:
        # return self.intersection(other.complement)
        def accept_func(a: Tuple[bool, frozenset[Tag]], b: Tuple[bool, frozenset[Tag]]) -> Tuple[bool, frozenset[Tag]]:
            accepts = a[0] and not b[0]
            tags = a[1] - b[1]
            return (accepts, tags)
        return self._product(other,'difference', accept_func)
    def __sub__(self, other: DFA[C]) -> DFA[C]:
        return self.difference(other)
    
    @property
    def nfa(self) -> NFA[C]:
        all_states: set[FAState] = set(self.transitions.keys())
        for trans in self.transitions.values():
            all_states.update(trans.values())
        all_states.update(self.accept.keys())
        all_states.add(self.init)
        state_map: dict[FAState, FAState] = {s: FAStateFactory.next() for s in all_states}
        nfa_trans: dict[FAState, FrozenDict[CharSet, frozenset[FAState]]] = {}
        for s, trans in self.transitions.items():
            nfa_s = state_map[s]
            nfa_trans[nfa_s] = FrozenDict(
                {cs: frozenset({state_map[tgt]}) for cs, tgt in trans.items()}
            )
        nfa_accept: FrozenDict[FAState, frozenset[Tag]] = FrozenDict(
            {state_map[s]: tags for s, tags in self.accept.items()}
        )
        return NFA(
            cs_factory=self.cs_factory,
            init=state_map[self.init],
            accept=nfa_accept,
            transitions=FrozenDict(nfa_trans),
            epsilon=FrozenDict()  
        )
    
    @property
    def dfa(self) -> DFA[C]:
        return self

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
    def merge_adjacent_transitions(cs_factory: CharSetFactory[C], transitions: dict[CharSet, FAState]) -> dict[CharSet, FAState]:
        """Merge consecutive CharSets with the same target into a single CharSet."""
        merged: List[Tuple[List[Tuple[int,int]], FAState]] = []
        sorted_trans = sorted(transitions.items(), key=lambda x: x[0])
        
        for charset, target in sorted_trans:
            if merged and merged[-1][1] == target:
                merged[-1][0].extend(charset)  # merge intervals
            else:
                merged.append((list(charset), target))

        return {cs_factory.from_interval(intv): target for intv, target in merged}
    
    @classmethod
    def from_nfa(cls, nfa: NFA[C]) -> DFA[C]:
        cs_factory = nfa.cs_factory
        start:frozenset[FAState] = nfa.closure({nfa.init})
        work_list = deque([start])
        dfa_states : dict[frozenset[FAState], FAState] = {start: FAStateFactory.next()}
        trans: dict[FAState, dict[CharSet, FAState]] = {}
        while work_list:
            current = work_list.popleft()
            current_dfa_state = dfa_states[current]
            edges: List[Tuple[CharSet, frozenset[FAState]]] = []
            for s in current:
                for e, targets in nfa.transitions.get(s, {}).items():
                    edges.append((e, targets))

            intvs: List[Tuple[int, int]] = [interval for e, _ in edges for interval in (e if isinstance(e, tuple) and isinstance(e[0], int) else e)]
            pieces: List[Tuple[int, int]] = list(cs_factory.partition_charsets(intvs))
            for p in pieces:
                tgt_states: Set[FAState] = set()
                for e, targets in edges:
                    if cs_factory.overlaps(e, p):
                        tgt_states.update(targets)                         
                closure = nfa.closure(tgt_states)
                if closure not in dfa_states:
                    dfa_states[closure] = FAStateFactory.next()
                    work_list.append(closure)
                trans.setdefault(current_dfa_state, {})[cs_factory.from_interval([p])] = dfa_states[closure]

        for s, e in trans.items():
            trans[s] = DFA.merge_adjacent_transitions(cs_factory, e)
        accept: dict[FAState, frozenset[Tag]] = {}
        for nfa_states, fa_state in dfa_states.items():
            tags: Set[Tag] = set()
            is_accept: bool = False
            for ns in nfa_states:
                is_accept = is_accept or (ns in nfa.accept)
                tags.update(nfa.accept.get(ns, frozenset()))
            if is_accept:
                accept[fa_state] = frozenset(tags)

        transitions: FrozenDict[FAState, FrozenDict[CharSet, FAState]] = FrozenDict({k: FrozenDict(v) for k, v in trans.items()})
        dead_states = [s for s in transitions if not transitions[s]]
        assert len(dead_states) <= 1, f"DFA can have at most one dead state, found {len(dead_states)}: {dead_states}"
        
        return cls(
                   cs_factory=cs_factory,
                   init=dfa_states[start],
                   accept=FrozenDict(accept),
                   transitions=transitions
               )

    def runner(self, *, non_greedy: frozenset[Tag] | None = None) -> Runner[C]:
        return Runner.create(self, non_greedy=non_greedy)
    
@dataclass(frozen=True, slots=True)
class NFA(Generic[C]):
    cs_factory: CharSetFactory[C]
    init: FAState
    accept: FrozenDict[FAState, frozenset[Tag]] = field(default_factory=FrozenDict)
    transitions: FrozenDict[FAState, FrozenDict[CharSet, frozenset[FAState]]] = field(default_factory=FrozenDict)
    epsilon: FrozenDict[FAState, frozenset[FAState]] = field(default_factory=FrozenDict)



    def start(self) -> NFA[C]:
        # New synthetic start state with a START-labeled edge into original init
        new_start = FAStateFactory.next()
        # Build transitions with the same FrozenDict shape
        trans: dict[FAState, dict[CharSet, frozenset[FAState]]] = {s: dict(m) for s, m in self.transitions.items()}
        trans[new_start] = {self.cs_factory.start(): frozenset({self.init})}
        frozen_trans: FrozenDict[FAState, FrozenDict[CharSet, frozenset[FAState]]] = FrozenDict({s: FrozenDict(m) for s, m in trans.items()})
        return replace(self, init=new_start, transitions=frozen_trans)


    def end(self) -> NFA[C]:
        # Create a new accept state reachable via END from all previous accepts
        new_accept = FAStateFactory.next()
        trans: dict[FAState, dict[CharSet, frozenset[FAState]]] = {s: dict(m) for s, m in self.transitions.items()}
        # Add END edge from each old accept to new_accept
        for acc in self.accept.keys():
            mapping = trans.get(acc, {})
            mapping[self.cs_factory.end()] = frozenset({new_accept})
            trans[acc] = mapping
        # Only the new_accept carries tags (union of all old tags)
        tags = set()
        for t in self.accept.values():
            tags.update(t)
        accept_fd: FrozenDict[FAState, frozenset[Tag]] = FrozenDict({new_accept: frozenset(tags)})
        frozen_trans: FrozenDict[FAState, FrozenDict[CharSet, frozenset[FAState]]] = FrozenDict({s: FrozenDict(m) for s, m in trans.items()})
        return replace(self, accept=accept_fd, transitions=frozen_trans)


    @property
    def dfa(self) -> DFA[C]:
        return DFA.from_nfa(self)

    @property
    def nfa(self) -> NFA[C]:
        return self

    def clone(self) -> NFA[C]:
        state_map: dict[FAState, FAState] = {}
        def get_clone(s: FAState) -> FAState:
            if s not in state_map:
                state_map[s] = FAStateFactory.next()
            return state_map[s]
        new_start = get_clone(self.init)
        new_accept: FrozenDict[FAState, frozenset[Tag]] = FrozenDict({get_clone(a):b for a,b in self.accept.items()})
        new_transitions: dict[FAState, FrozenDict[CharSet, frozenset[FAState]]] = {}
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
                        init=new_start,
                        accept=new_accept,
                        transitions=FrozenDict(new_transitions),
                        epsilon=new_epsilon)
    
    def tagged(self, tag: Tag) -> NFA[C]:
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
    
    def runner(self, *, non_greedy: frozenset[Tag] | None = None) -> NFARunner[C]:
        return NFARunner.create(self, non_greedy=non_greedy)
    

    @classmethod
    def from_raw_charset(cls, *,
                         c: CharSet, 
                         cs_factory: CharSetFactory[C],
                         tag: Optional[Tag] = None) -> NFA[C]:
        assert c != tuple(), "charset cannot be empty"
        current: FAState = FAStateFactory.next()
        accept: FAState = FAStateFactory.next()
        return cls(
                   cs_factory=cs_factory,
                   init=current, 
                   accept=FrozenDict({accept: frozenset({tag}) if tag else frozenset()}),
                   transitions=FrozenDict({
                       current: FrozenDict({c: frozenset({accept})})
                   }),
                   epsilon=FrozenDict())
    
    @classmethod
    def oneof(cls, *, s: str | bytes | Sequence[C], cs_factory: CharSetFactory[C], negation:bool = False, tag: Optional[Tag] = None) -> NFA[Any]:
        
        charset: CharSet = cs_factory.create(s) # type: ignore
        if negation:
            charset = cs_factory.complement(charset)
        return cls.from_raw_charset(cs_factory=cs_factory, c=charset, tag=tag)

    @classmethod
    def seq(cls, *,
            s: str | bytes | Sequence[C], 
            cs_factory: CharSetFactory[C], 
            tag: Optional[Tag] = None) -> NFA[Any]:
        nfa = None
        if isinstance(s, bytes):
            ss: Sequence[Any] = [bytes([x]) for x in list(s)]
        else:
            ss  = s
        for ch in ss:
            p = cls.oneof(s=ch, cs_factory=cs_factory) # type: ignore
            nfa = p if nfa is None else nfa.then(p)
        assert nfa is not None, "from_string produced no NFA"
        if tag:
            nfa = nfa.tagged(tag)
        return nfa
                

    def then(self, other: NFA[C]) -> NFA[C]:
        assert self.cs_factory == other.cs_factory, "Cannot combine NFAs with different universes"
        this = self.clone()
            
        eps = {**this.epsilon}
        for a in this.accept:
            eps[a] = eps.get(a, frozenset()) | frozenset({other.init})
        
        for k, v in other.epsilon.items():
            eps[k] = eps.get(k, frozenset()) | v
    
        new_transitions = {**this.transitions}
        for k, v in other.transitions.items():
            new_transitions[k] = new_transitions.get(k, FrozenDict()) | v
            
        return this.__class__(
                              cs_factory=this.cs_factory,
                              init=this.init, 
                              accept=FrozenDict({k: frozenset() for k in other.accept}), 
                              transitions=FrozenDict(new_transitions), 
                              epsilon=FrozenDict(eps))
    
    def __rshift__(self, other: NFA[C]) -> NFA[C]:
        return self.then(other)
    
    def union(self, other: NFA[C]) -> NFA[C]:
        assert self.cs_factory == other.cs_factory, "Cannot combine NFAs with different universes"        
        if self is other:
            return self
        new_current: FAState = FAStateFactory.next()
        eps = {new_current: frozenset({self.init, other.init})}
        for k, v in self.epsilon.items():
            eps[k] = eps.get(k, frozenset()) | v
        for k, v in other.epsilon.items():
            eps[k] = eps.get(k, frozenset()) | v
        
        new_transitions = {**self.transitions}
        for k, v in other.transitions.items():
            new_transitions[k] = new_transitions.get(k, FrozenDict()) | v
        

        return replace(self,
                       cs_factory=self.cs_factory,
                       init=new_current, 
                       accept=FrozenDict({k: self.accept.get(k, frozenset()) | other.accept.get(k, frozenset()) for k in (self.accept | other.accept).keys()}), 
                       transitions=FrozenDict(new_transitions), 
                       epsilon=FrozenDict(eps))    
    def __or__(self, other: NFA[C]) -> NFA[C]:
        return self.union(other)

    @property
    def star(self) -> NFA[C]:
        new_current: FAState = FAStateFactory.next()
        eps = {**self.epsilon, new_current: frozenset({self.init})}
        for a in self.accept:
            eps[a] = eps.get(a, frozenset()) | frozenset({self.init})
        return replace(self,
                        init=new_current, 
                        accept=self.accept | FrozenDict({new_current: frozenset()}), 
                        transitions=self.transitions, 
                        epsilon=FrozenDict(eps))
    
    @property
    def optional(self)->NFA[C]:
        new_current: FAState = FAStateFactory.next()
        eps = {**self.epsilon, new_current: frozenset({self.init})}
        return replace(self,
                        init=new_current, 
                        accept=self.accept | FrozenDict({new_current: frozenset()}), 
                        transitions=self.transitions, 
                        epsilon=FrozenDict(eps))
    def __invert__(self) -> NFA[C]:
        return self.optional

    @property
    def plus(self) -> NFA[C]:
        eps = {**self.epsilon}
        for a in self.accept:
            eps[a] = eps.get(a, frozenset()) | frozenset({self.init})
        return replace(self,
                        init=self.init, 
                        accept=self.accept, 
                        transitions=self.transitions, 
                        epsilon=FrozenDict(eps))
    
    def __pos__(self) -> NFA[C]:
        return self.plus
    
    def many(self, at_least: int = 0, at_most: Optional[int] = None) -> NFA[C]:
        assert at_least >= 0, "at_least must be non-negative"
        assert at_most is None or at_least <= at_most, "at_least must <= at_most"
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
    


Automata = TypeVar('Automata', bound=NFA | DFA)


@dataclass(frozen=True, slots=True)
class RunnerResult:
    error: bool
    final: bool
    accepted: Optional[Tuple[int, frozenset[Tag]]] = None

    @classmethod
    def new(cls, *, error: bool, final: bool, accepted: Optional[Tuple[int, frozenset[Tag]]] = None) -> RunnerResult:
        obj = cls.__new__(cls)
        object.__setattr__(obj, 'error', error)
        object.__setattr__(obj, 'final', final)
        object.__setattr__(obj, 'accepted', accepted)
        return obj

    

@dataclass(slots=True)
class Runner(Generic[C]):
    fa: DFA[C]
    accepted: Tuple[Tuple[int, frozenset[Tag]], ...] = field(default_factory=tuple)
    non_greedy: frozenset[Tag] = field(default_factory=frozenset)

    current: Optional[FAState] = None


    @property
    def dfa(self) -> DFA[C]:
        if isinstance(self.fa, DFA):
            return self.fa
        else:
            return self.fa.dfa
    @property
    def nfa(self) -> NFA[C]:
        if isinstance(self.fa, NFA):
            return self.fa
        else:
            return self.fa.nfa
    
    @property
    def candidates(self)-> Tuple[Tuple[int, frozenset[Tag]],...]:
        return tuple((pos, tags) for (pos, tags) in self.accepted)

    def reset(self) -> Runner[C]:
        return self.create(self.fa, non_greedy=self.non_greedy)


    @classmethod
    def create(cls, dfa: DFA[C], *, non_greedy: frozenset[Tag] | None = None) -> Runner[C]:
        return cls(current=dfa.init, fa=dfa, non_greedy=non_greedy if non_greedy is not None else frozenset())

    def start(self) -> RunnerResult:
        start_state = self.current
        entry = self.fa.transitions.get(start_state, {})
        START = self.fa.cs_factory.start()
        for cs, tgt in entry.items():
            if cs == START:
                start_state = tgt
                break
        return self.advance_state(start_state, pos=0)

    def finalize(self) -> RunnerResult:
        cur = self.current
        if cur is not None:
            entry = self.fa.transitions.get(cur, {})
            END = self.fa.cs_factory.end()
            for cs, tgt in entry.items():
                if cs == END:
                    cur = tgt
                    break
        
        return self.advance_state(cur, pos=self.accepted[-1][0] if self.accepted else 0)


    def _has_future_non_anchor(self, state: Optional[FAState]) -> bool:
        if state is None:
            return False
        for cs in self.fa.transitions.get(state, {}).keys():
            if not any(lo < 0 or hi < 0 for (lo, hi) in cs):
                return True
        return False
    
    def advance_state(self, next_state: None | FAState, pos: int) -> RunnerResult:
        self.current = next_state
        if next_state is None:
            if self.accepted:
                result = (self.accepted[-1][0], self.accepted[-1][1])
                self.accepted = tuple()
                return RunnerResult.new(
                    error=False,
                    final=True,
                    accepted=result,
                )
            else:
                return RunnerResult.new(
                    error=True,
                    final=True,
                    accepted=None,
                )
        else:
            has_future = self._has_future_non_anchor(next_state)
            if self.is_accepted() and next_state is not None:
                accepted_tags = self.tags()
                new_accepted = self.accepted + ((pos, accepted_tags),)
                self.accepted = new_accepted
                # new_runner = replace(self, accepted=new_accepted)
                non_greedy_hit = bool(self.non_greedy & accepted_tags)
                if non_greedy_hit or not has_future:
                    self.accepted = tuple()
                    return RunnerResult.new(
                        error=False,
                        final=True,
                        accepted=(pos, accepted_tags),
                    )
            return RunnerResult.new(
                error=False,
                final=False,
                accepted=None,
            )


    def step(self, symbol: C, pos: int) -> RunnerResult:

        next_state: Optional[FAState] = None
        entry: FrozenDict[CharSet, FAState] = self.fa.transitions.get(self.current, {})
        k: CharSet = self.fa.cs_factory.create_one(symbol)
        if k in entry:
            next_state = entry[k]
        else:
            codepoint = k[0][0]  
            matches = self.fa.cs_factory.match_codepoint
            for char_set, targets in entry.items():
                if matches(char_set, codepoint):
                    next_state = targets
                    break
        return self.advance_state(next_state, pos)
    

    def is_accepted(self) -> bool:
        return self.current in self.dfa.accept

    def is_valid(self) -> bool:
        return bool(self.current)
    
    @property
    def resumable(self) -> frozenset[CharSet]:
        entry = self.dfa.transitions.get(self.current, {}) 
        keys = entry.keys()
        filtered = [cs for cs in keys if not any(lo < 0 or hi < 0 for (lo, hi) in cs)]
        return frozenset(filtered)


    def tags(self) -> frozenset[Tag]:
        return self.dfa.accept.get(self.current, frozenset())




@dataclass(slots=True)
class NFARunner(Generic[C]):
    fa: NFA[C]
    accepted: Tuple[Tuple[int, frozenset[Tag]], ...] = field(default_factory=tuple)
    non_greedy: frozenset[Tag] = field(default_factory=frozenset)

    current: frozenset[FAState] = field(default_factory=frozenset)
    @classmethod
    def create(cls, nfa: NFA[C], *, non_greedy: frozenset[Tag] | None = None) -> NFARunner[C]:
        return cls(current=nfa.closure({nfa.init}), fa=nfa, non_greedy=non_greedy or frozenset())

    def advance_state(self, next_state: None | FAState | frozenset[FAState], pos: int) -> RunnerResult: 

        if not next_state:
            if self.accepted:
                result = (self.accepted[-1][0], self.accepted[-1][1])
                self.accepted = tuple()
                self.current = frozenset()
                return RunnerResult.new(
                    error=False,
                    final=True,
                    accepted=result,
                )
            else:
                self.accepted = tuple()
                self.current = frozenset()
                return RunnerResult.new(
                    error=True,
                    final=True,
                    accepted=None,
                )                        
        else:
            assert isinstance(next_state, frozenset)  # type checker hint
            new_current = self.fa.closure(next_state)
            self.current = new_current
            # new_runner = replace(self, current=new_current)
            has_future_non_anchor = False
            for s2 in new_current:
                for cs2 in self.fa.transitions.get(s2, {}).keys():
                    if not any(lo < 0 or hi < 0 for (lo, hi) in cs2):
                        has_future_non_anchor = True
                        break
                if has_future_non_anchor:
                    break
            if self.is_accepted():
                accepted_tags = self.tags()
                self.accepted = self.accepted + ((pos, accepted_tags),)

                # new_runner = replace(new_runner, accepted=new_accepted)
                non_greedy_hit = bool(self.non_greedy & accepted_tags)
                if non_greedy_hit or not has_future_non_anchor:
                    self.accepted = tuple()
                    return RunnerResult.new(
                        # runner=replace(new_runner, accepted=()),
                        error=False,
                        final=True,
                        accepted=(pos, accepted_tags),
                    )
            return RunnerResult.new(
                error=False,
                final=False,
                accepted=None,
            )


    def start(self) -> RunnerResult:
        start_states = self.current
        advanced: set[FAState] = set()
        START = self.fa.cs_factory.start()
        for s in start_states:
            entry = self.fa.transitions.get(s, {})
            for cs, tgts in entry.items():
                if cs == START:
                    advanced.update(tgts)
        if advanced:
            start_states = self.fa.closure(advanced)
        return self.advance_state(start_states, pos=0)

    def step(self, symbol: C, pos: int) -> RunnerResult:
        
        next_states = set()
        for s in self.current:
            entry: FrozenDict[CharSet, frozenset[FAState]] = self.fa.transitions.get(s, {})
            k: CharSet = self.fa.cs_factory.create_one(symbol)
            if k in entry:
                next_states.update(entry[k])
            else:
                matches = self.fa.cs_factory.matches
                for char_set, targets in entry.items():
                    if matches(char_set, symbol):
                        next_states.update(targets)

        return self.advance_state(frozenset(next_states), pos=pos)
    
    def is_accepted(self) -> bool:
        return any(st in self.fa.accept for st in self.current)
    
    def is_valid(self) -> bool:
        return bool(self.current)

    @property
    def resumable(self) -> frozenset[CharSet]:
        result: Set[CharSet] = set()
        for s in self.current:
            result.update(self.fa.transitions.get(s, {}).keys())
        filtered = [cs for cs in result if not any(lo < 0 or hi < 0 for (lo, hi) in cs)]
        return frozenset(filtered)

    def tags(self) -> frozenset[Tag]:
        tags: Set[Tag] = set()
        for s in self.current:
            tags.update(self.fa.accept.get(s, frozenset()))
        return frozenset(tags)
    
    def finalize(self) -> RunnerResult:
        next_states: set[FAState] = set()
        END = self.fa.cs_factory.end()
        for s in self.current:
            entry = self.fa.transitions.get(s, {})
            for cs, tgts in entry.items():
                if cs == END:
                    next_states.update(tgts)
        if next_states:
            new_current = self.fa.closure(next_states)
        else:
            new_current = self.current
        return self.advance_state(new_current, pos=self.accepted[-1][0] if self.accepted else 0)


class _NodeKind(str, Enum):
    RANGE = "RANGE"
    LITERAL = "LITERAL"
    ONEOF = "ONEOF"
    CONCAT = "CONCAT"
    UNION = "UNION"
    INTERSECT = "INTERSECT"  # DFA-only
    DIFF = "DIFF"            # DFA-only (A - B)
    COMPLEMENT = "COMPLEMENT"  # DFA-only (alphabet - A)
    STAR = "STAR"
    PLUS = "PLUS"
    OPTIONAL = "OPTIONAL"
    MANY = "MANY"




class ModeActionEnum(Enum):
    POP = "POP"
    PUSH = "PUSH"
    BELONG = "BELONG"

@dataclass(frozen=True, slots=True)
class ModeAction:
    action: ModeActionEnum
    mode: str
    belong: str | None = None  # only used for PUSH action

@dataclass(frozen=True, slots=True)
class Builder(Generic[C]):
    kind: _NodeKind
    tag: Tag | None = None
    children: Tuple[Builder[C], ...] = field(default_factory=tuple)
    intervals: Tuple[Tuple[str | bytes | C, str | bytes | C], ...] = field(default_factory=tuple)
    text: Optional[Union[str, bytes, Sequence[C]]] = None
    at_least: int = 0
    at_most: Optional[int] = None
    skip: bool = False  # if true, do not include this in the final automaton (used for whitespace, comments, etc)
    priority: int = 0  # higher number means higher priority
    non_greedy: bool = False  # when true, first match wins instead of maximal munch
    action: Optional[ModeAction] = None  # the mode that the lexical rule belongs to

    # ---- Factory entry points ----
    def name(self) -> Optional[str]:
        match self.kind:
            case _NodeKind.LITERAL:
                return f"'{self.text!r}'"
            case _NodeKind.ONEOF:
                return f"[{self.text!r}]"
        return None
            
    def __str__(self) -> str:
        match self.kind:
            case _NodeKind.RANGE:
                ranges_str = ", ".join(f"{start!r}-{end!r}" for start, end in self.intervals)
                return f"/{ranges_str}/"
            case _NodeKind.LITERAL:
                return f"{self.text!r}"
            case _NodeKind.ONEOF:
                return f"[{self.text!r}]"
            case _NodeKind.STAR:
                return f"({self.children[0]})*"
            case _NodeKind.OPTIONAL:
                return f"({self.children[0]})?"
            case _NodeKind.COMPLEMENT:
                return f"-({self.children[0]})"
            case _NodeKind.MANY:
                at_most_str = f", at_most={self.at_most}" if self.at_most is not None else ""
                return f"({self.children[0]}){{at_least={self.at_least}{at_most_str}}}"
            case _NodeKind.CONCAT:
                return f"({self.children[0]} + {self.children[1]})"
            case _NodeKind.UNION:
                return f"({self.children[0]} | {self.children[1]})"
            case _NodeKind.INTERSECT:
                return f"({self.children[0]} & {self.children[1]})"
            case _NodeKind.DIFF:
                return f"({self.children[0]} - {self.children[1]})"
            case _:
                return f"Builder({self.kind})"

    def walk(self) -> Iterator[Builder[C]]:
        yield self
        for child in self.children:
            yield from child.walk()

    @property
    def alphabet(self) -> Optional[AlphabetProtocol[Any]]:    
        for node in self.walk():
            if node.kind == _NodeKind.LITERAL:
                if isinstance(node.text, bytes):
                    return Alphabet(bytes)
                elif isinstance(node.text, str):
                    return Alphabet(str)
            elif node.kind == _NodeKind.RANGE:
                for start, end in node.intervals:
                    if isinstance(start, bytes) or isinstance(end, bytes):
                        return Alphabet(bytes)
                    elif isinstance(start, str) or isinstance(end, str):
                        return Alphabet(str)
            elif node.kind == _NodeKind.ONEOF:
                if isinstance(node.text, bytes):
                    return Alphabet(bytes)
                elif isinstance(node.text, str):
                    return Alphabet(str)
        return None


    @classmethod
    def lit(cls, 
                text: Union[str, bytes], 
                *, 
                tag: Optional[Tag] = None,
                skip: bool = False, 
                priority: int = 0,
                non_greedy: bool = False,
                action: Optional[ModeAction] = None) -> Builder[C]:
        return cls(
            kind=_NodeKind.LITERAL,
            text=text,
            tag=tag,
            action=action,
            skip=skip,
            priority=priority,
            non_greedy=non_greedy,
        )

    @classmethod
    def any(cls, 
            alphabet: AlphabetProtocol[C],
            *,
            tag: Optional[Tag] = None,
            skip: bool = False, 
            priority: int = 0,
            non_greedy: bool = False,
            action: Optional[ModeAction] = None,
            ) -> Builder[C]:
        return cls(kind=_NodeKind.RANGE, 
                   intervals=alphabet.symbols, 
                   tag=tag, 
                   action=action, 
                   skip=skip, 
                   priority=priority, 
                   non_greedy=non_greedy)

    @classmethod
    def none(cls, 
             alphabet: AlphabetProtocol[C],
             *,
             tag: Optional[Tag] = None,
             skip: bool = False, 
             priority: int = 0,
             non_greedy: bool = False,
             action: Optional[ModeAction] = None,
             ) -> Builder[C]:
        any = cls.any(alphabet, tag=tag, skip=skip, priority=priority, non_greedy=non_greedy, action=action)
        return -any
    
    @classmethod
    def unicode_category(cls, 
                         cats: List[str], 
                         *, 
                         tag: Optional[Tag] = None,
                         skip: bool = False, 
                         priority: int = 0,
                         non_greedy: bool = False,
                         action: Optional[ModeAction] = None,
                         ) -> Builder[C]:
        import unicodedata
        from itertools import groupby
        def unicode_category_ranges(*cats: str) -> list[tuple[str, str]]:
            alphabet = range(0x110000)  # full Unicode range (0 .. 0x10FFFF)
            points = [cp for cp in alphabet if unicodedata.category(chr(cp)) in cats]
            # Collapse consecutive codepoints into ranges
            ranges = []
            for _, group in groupby(enumerate(points), key=lambda x: x[0] - x[1]):
                seq = list(group)
                start = chr(seq[0][1])
                end = chr(seq[-1][1])
                ranges.append((start, end))
            return ranges

        ranges = unicode_category_ranges(*cats)
        return cls(kind=_NodeKind.RANGE, 
                   intervals=tuple(ranges), 
                   tag=tag, 
                   action=action, 
                   skip=skip, 
                   priority=priority, 
                   non_greedy=non_greedy)

    @classmethod
    def range(cls, 
              start: Union[str, bytes, C], 
              end: Union[str, bytes, C], 
              *, 
              tag: Optional[Tag] = None,
              skip: bool = False, 
              priority: int = 0,
              non_greedy: bool = False,
              action: Optional[ModeAction] = None) -> Builder[Any]:
        return cls(kind=_NodeKind.RANGE, 
                   intervals=((start, end),), 
                   tag=tag, 
                   action=action, 
                   skip=skip, 
                   priority=priority, 
                   non_greedy=non_greedy)
        

    @classmethod
    def oneof(cls, 
              chars: Union[str, bytes, Sequence[C]], 
              *, 
              tag: Optional[Tag] = None,
              skip: bool = False, 
              priority: int = 0,
              non_greedy: bool = False,
              action: Optional[ModeAction] = None) -> Builder[C]:
        if not isinstance(chars, (str, bytes)):
            if len(chars) > 0:
                if isinstance(chars[0], (str, bytes)):
                    if not all(len(c) == 1 for c in chars): # type: ignore
                        return reduce(lambda a, b: a | b, [cls.lit(e) for e in chars]).with_non_greedy(non_greedy).skipped(skip).tagged(tag).act(action).prioritized(priority) # type: ignore
                    else:
                        return cls.oneof("".join(chars)).with_non_greedy(non_greedy).skipped(skip).tagged(tag).act(action).prioritized(priority) # type: ignore
        return cls(
            kind=_NodeKind.ONEOF,
            text=chars,
            tag=tag,
            action=action,
            skip=skip,
            priority=priority,
            non_greedy=non_greedy,
        )

    # ---- DSL operators ----
    def __add__(self, other: Builder[C]) -> Builder[C]:
        return Builder(kind=_NodeKind.CONCAT, children=(self, other))

    def __or__(self, other: Builder[C]) -> Builder[C]:
        return Builder(kind=_NodeKind.UNION, children=(self, other))

    def __and__(self, other: Builder[C]) -> Builder[C]:
        return Builder(kind=_NodeKind.INTERSECT, children=(self, other))

    def __sub__(self, other: Builder[C]) -> Builder[C]:
        return Builder(kind=_NodeKind.DIFF, children=(self, other))

    def __invert__(self) -> Builder[C]:  # optional (~)
        return Builder(kind=_NodeKind.OPTIONAL, children=(self,))

    def __neg__(self) -> Builder[C]:  # complement (-)
        return Builder(kind=_NodeKind.COMPLEMENT, children=(self,))

    @property
    def star(self) -> Builder[C]:
        return Builder(kind=_NodeKind.STAR, children=(self,))

    @property
    def plus(self) -> Builder[C]:
        return (self + self.star)

    def many(self, 
             *, 
             at_least: int = 0, 
             at_most: Optional[int] = None) -> Builder[C]:
        return Builder(kind=_NodeKind.MANY, 
                         children=(self,), 
                         at_least=at_least, 
                         at_most=at_most)

    def tagged(self, value: Tag) -> Builder[C]:
        return replace(self, tag=value)
    
    def act(self, action: ModeAction | None = None) -> Builder[C]:
        return replace(self, action=action)

    def skipped(self, skip: bool = True) -> Builder[C]:
        return replace(self, skip=skip)
    
    def prioritized(self, priority: int) -> Builder[C]:
        return replace(self, priority=priority)

    def with_non_greedy(self, non_greedy: bool = True) -> Builder[C]:
        return replace(self, non_greedy=non_greedy)

    def compile(self, alphabet: AlphabetProtocol[C]) -> NFA[C] | DFA[C]: 
        cs_factory = CharSetFactory(alphabet=alphabet)
        match self.kind:
            case _NodeKind.RANGE:
                assert self.intervals, "Range can not be empty"
                codes = []
                for (start, end) in self.intervals:
                    code_start = alphabet.encode(start) # type: ignore
                    code_end = alphabet.encode(end) # type: ignore
                    if code_start < code_end:
                        codes.append((code_start, code_end))
                charset = cs_factory.from_interval(codes) # type: ignore
                return NFA.from_raw_charset(cs_factory=cs_factory, c=charset, tag=self.tag)
            case _NodeKind.UNION:
                left = self.children[0].compile(alphabet).nfa
                right = self.children[1].compile(alphabet).nfa
                return left.union(right)
            case _NodeKind.CONCAT:
                left = self.children[0].compile(alphabet).nfa
                right = self.children[1].compile(alphabet).nfa
                return left.then(right)
            case _NodeKind.LITERAL:
                assert self.text is not None, "Literal must have text"
                return NFA.seq(s=self.text, cs_factory=cs_factory, tag=self.tag)
            case _NodeKind.ONEOF:
                assert self.text is not None, "Literal must have text"
                return NFA.oneof(s=self.text, cs_factory=cs_factory, tag=self.tag)
            case _NodeKind.STAR:
                inner = self.children[0].compile(alphabet).nfa
                return inner.star
            case _NodeKind.OPTIONAL:
                inner = self.children[0].compile(alphabet).nfa
                return inner.optional
            case _NodeKind.MANY:
                inner = self.children[0].compile(alphabet).nfa
                return inner.many(at_least=self.at_least, at_most=self.at_most)
            case _NodeKind.PLUS:
                inner = self.children[0].compile(alphabet).nfa
                return inner.star
            case _NodeKind.COMPLEMENT:
                # Require DFA planning for these operations
                inner1 = self.children[0].compile(alphabet).dfa
                return inner1.complement
            case _NodeKind.INTERSECT:
                # Require DFA planning for these operations
                left1 = self.children[0].compile(alphabet).dfa
                right1 = self.children[1].compile(alphabet).dfa
                return left1.intersection(right1)
            case _NodeKind.DIFF:
                # Require DFA planning for these operations
                left1 = self.children[0].compile(alphabet).dfa
                right1 = self.children[1].compile(alphabet).dfa
                return left1.difference(right1)
            case _:
                raise NotImplementedError(f"Unhandled Builder kind: {self.kind}")
            
    
    
    

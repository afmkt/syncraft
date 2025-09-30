from __future__ import annotations

from typing import (
    TypeVar, Optional, Generic, Tuple, ClassVar, Set, Protocol, Any, Self, List, Callable, Dict, Sequence, Union
)

from dataclasses import dataclass, field, replace
from functools import cached_property
from syncraft.algebra import (
    SyncraftError
)
from collections import deque
from syncraft.constraint import  FrozenDict
from syncraft.charset import CharSet, CodeUniverse, MixedUniverseError, CodepointError
from enum import Enum
from collections import defaultdict

import random


C = TypeVar('C', bound=str | int | Enum | Any)

FAStateBuilder = Callable[[], 'FAState']
@dataclass(frozen=True)
class FAState:
    _counter: ClassVar[int] = 0  # shared across all states
    id: int = field(default_factory=lambda: FAState._next_id())

    @classmethod
    def builder(cls, init: int = 0) -> FAStateBuilder:
        def build() -> FAState:
            nonlocal init
            init += 1
            return cls(id=init)
        return build

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
    init: FAState
    accept: FrozenDict[FAState, frozenset[str | Enum]] = field(default_factory=FrozenDict)
    transitions: FrozenDict[FAState, FrozenDict[CharSet[C], FAState]] = field(default_factory=FrozenDict)
    nfa2dfa: FrozenDict[frozenset[FAState], FAState]= field(default_factory=FrozenDict) 

    def all_tags(self) -> frozenset[Tag]:
        seen: set[Tag] = set()
        for tags in self.dfa.accept.values():
            seen.update(tags)
        return frozenset(seen)


    def to_dict(self) -> dict:
        # Serialize DFA to a dict for JSON
        return {
            'init': self.init.id,
            'accept': {s.id: list(tags) for s, tags in self.accept.items()},
            'transitions': {
                str(s.id): [
                    {'interval': cs.interval, 'target': t.id}
                    for cs, t in trans.items()
                ]
                for s, trans in self.transitions.items()
            },
            'universe': self.universe.to_dict()
        }

    @classmethod
    def from_dict(cls, d: dict, enum_classes: Optional[dict] = None) -> 'DFA':
        # Reconstruct DFA from dict
        universe = CodeUniverse.from_dict(d['universe'], enum_classes=enum_classes)
        id2state = {}
        def get_state(i):
            if i not in id2state:
                id2state[i] = FAState(id=i)
            return id2state[i]
        # Accept
        accept = {get_state(int(sid)): frozenset(tags) for sid, tags in d['accept'].items()}
        # Transitions
        transitions = {}
        for sid, lst in d['transitions'].items():
            s = get_state(int(sid))
            trans = {}
            for item in lst:
                cs: CharSet[C] = CharSet.from_interval(item['interval'], universe)
                t = get_state(item['target'])
                trans[cs] = t
            transitions[s] = trans
        return cls(
            universe=universe,
            init=get_state(int(d['init'])),
            accept=FrozenDict(accept),
            transitions=FrozenDict({s: FrozenDict(m) for s, m in transitions.items()}),
            nfa2dfa=FrozenDict()
        )

    def save(self, filename: str) -> None:
        import json
        with open(filename, 'w') as f:
            json.dump(self.to_dict(), f)

    @classmethod
    def load(cls, filename: str) -> 'DFA':
        import json
        with open(filename, 'r') as f:
            d = json.load(f)
        return cls.from_dict(d)
    
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

        universe = self.universe
        fabuilder = FAState.builder()

        # Collect all states explicitly referenced.
        states: Set[FAState] = set(self.transitions.keys()) | set(self.accept.keys())
        for trans in self.transitions.values():
            states.update(trans.values())
        states.add(self.init)

        # Build global disjoint alphabet partition from all outgoing CharSet intervals.
        all_intvs: List[Tuple[int, int]] = []
        for mapping in self.transitions.values():
            for cs in mapping.keys():
                all_intvs.extend(cs.interval)
        # If no intervals (degenerate), return self
        if not all_intvs:
            return self
        pieces: List[Tuple[int, int]] = CharSet.partition_charsets(all_intvs)
        piece_charsets: List[CharSet[C]] = [CharSet.from_interval([p], universe) for p in pieces]

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
                    if cs.overlaps(pcs.interval[0]):
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
        new_accept: Dict[FAState, frozenset[str | Enum]] = {}
        for block in P:
            rep = fabuilder()
            for s in block:
                block_rep[s] = rep
            # Union tags if any state accepting
            tags: Set[str | Enum] = set()
            accepting = False
            for s in block:
                if s in self.accept:
                    accepting = True
                    tags.update(self.accept.get(s, frozenset()))
            if accepting:
                new_accept[rep] = frozenset(tags)

        # Rebuild transitions only for pieces that were REAL in the original DFA (skip synthesized sink edges)
        new_transitions: Dict[FAState, Dict[CharSet[C], FAState]] = {}
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
            rep_trans: Dict[CharSet[C], FAState] = {}
            for intv_list, tgt_rep in grouped:
                cs = CharSet.from_interval(intv_list, universe)
                rep_trans[cs] = tgt_rep
            if rep_trans:
                # Optional: merge adjacent for same target (already contiguous grouping but safe)
                rep_trans = DFA.merge_adjacent_transitions(universe, rep_trans)
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
            universe=universe,
            init=new_init,
            accept=FrozenDict(new_accept),
            transitions=FrozenDict({s: FrozenDict(m) for s, m in new_transitions.items()}),
            nfa2dfa=FrozenDict()
        )
    



    def tagged(self, tag: str | Enum, append:bool=False) -> DFA[C]:
        if append:
            return replace(self, accept=FrozenDict({a: (tags | frozenset({tag})) for a, tags in self.accept.items()}))
        else:
            return replace(self, accept=FrozenDict({a: frozenset({tag}) for a in self.accept}))


    # @staticmethod
    # def _complete_transitions(universe: CodeUniverse,
    #                         transitions: dict[FAState, dict[CharSet[C], FAState]],
    #                         accept: dict[FAState, frozenset]) -> tuple[dict[FAState, dict[CharSet[C], FAState]], dict[FAState, frozenset], FAState]:
    #     # copy inputs shallow
    #     trans_copy: Dict[FAState, Dict[CharSet[C], FAState]] = {s: dict(m) for s, m in transitions.items()}

    #     # create sink state
    #     sink = FAState()

    #     # ensure sink exists in map to be consistent
    #     trans_copy.setdefault(sink, {})

    #     # For each state, compute covered charset and add missing piece mapped to sink
    #     for s, mapping in list(trans_copy.items()):
    #         # union all key charsets into 'covered'
    #         covered: CharSet[C] = CharSet.none(universe)
    #         for cs in mapping.keys():
    #             covered = covered | cs
    #         missing = (-covered)
    #         if missing.interval:  # any uncovered codepoints
    #             # If the state's mapping already has a CharSet that equals missing, merge would have caught it
    #             mapping[missing] = sink
    #             trans_copy[s] = mapping

    #     # ensure sink loops to itself on all chars
    #     trans_copy[sink] = {CharSet.any(universe): sink}

    #     # Optionally: merge adjacent pieces in each state's mapping (keeps mapping compact)
    #     for s, mapping in list(trans_copy.items()):
    #         trans_copy[s] = DFA.merge_adjacent_transitions(universe, mapping)

    #     return trans_copy, accept, sink



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
            init=self.init,
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
        start_pair = (self.init, other.init)
        state_map[start_pair] = FAState()
        work_list = deque([start_pair])

        transitions: dict[FAState, dict[CharSet[C], FAState]] = {}
        accept: dict[FAState, frozenset[Tag]] = {}

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
        frozen_accept: FrozenDict[FAState, frozenset[Tag]] = FrozenDict(accept)

        return DFA(
            universe=self.universe,
            init=state_map[start_pair],
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
        all_states.add(self.init)
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
        start:frozenset[FAState] = nfa.closure({nfa.init})
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
                   init=dfa_states[start],
                   accept=FrozenDict(accept),
                   transitions=transitions,
                   nfa2dfa=FrozenDict(dfa_states)
               )

    def runner(self) -> DFARunner[C]:
        return DFARunner.create(self)
    
@dataclass(frozen=True)
class NFA(Generic[C]):
    universe: CodeUniverse
    init: FAState
    accept: FrozenDict[FAState, frozenset[Tag]] = field(default_factory=FrozenDict)
    transitions: FrozenDict[FAState, FrozenDict[CharSet[C], frozenset[FAState]]] = field(default_factory=FrozenDict)
    epsilon: FrozenDict[FAState, frozenset[FAState]] = field(default_factory=FrozenDict)


    def all_tags(self) -> frozenset[Tag]:
        seen: set[Tag] = set()
        for tags in self.accept.values():
            seen.update(tags)
        return frozenset(seen)
    
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
                state_map[s] = FAState()
            return state_map[s]
        new_start = get_clone(self.init)
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
                        init=new_start,
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
    

    @classmethod
    def _from_charset(cls, c: CharSet[C], tag: Optional[Tag] = None) -> NFA[C]:
        assert c.interval != tuple(), "charset cannot be empty"
        current: FAState = FAState()
        accept: FAState = FAState()
        return cls(
                   universe=c.universe,
                   init=current, 
                   accept=FrozenDict({accept: frozenset({tag}) if tag else frozenset()}),
                   transitions=FrozenDict({
                       current: FrozenDict({c: frozenset({accept})})
                   }),
                   epsilon=FrozenDict())
    
    @classmethod
    def from_charset(cls, 
                  char: str | bytes | Sequence[Enum] | Sequence[C], 
                  universe: CodeUniverse, 
                  negation:bool = False,  
                  tag: Optional[Tag] = None) -> NFA[Any]:
        charset: CharSet[C] = CharSet.create(char, universe=universe)
        if negation:
            charset = -charset
        if charset.interval == tuple():
            raise CodepointError(f"Character {char!r} is not valid in the specified universe {universe}", offender=char, universe=universe)
        return cls._from_charset(charset, tag=tag)

    @classmethod
    def from_string(cls, 
                    s: str | bytes | Sequence[Enum] | Sequence[C], 
                    universe: CodeUniverse, 
                    tag: Optional[Tag] = None) -> NFA[Any]:
        nfa = None
        if isinstance(s, str):
            for ch in list(s):
                p = cls.from_charset(ch, universe=universe)
                nfa = p if nfa is None else nfa.then(p)
            assert nfa is not None, "from_string produced no NFA"
            if tag:
                nfa = nfa.tagged(tag)
            return nfa
        elif isinstance(s, bytes):
            for b in s:
                p = cls.from_charset(bytes([b]), universe=universe)
                nfa = p if nfa is None else nfa.then(p)
            assert nfa is not None, "from_string produced no NFA"
            if tag:
                nfa = nfa.tagged(tag)
            return nfa
        elif isinstance(s, Sequence):
            for e in s:
                p = cls.from_charset([e], universe=universe) # type: ignore
                nfa = p if nfa is None else nfa.then(p)
            assert nfa is not None, "from_string produced no NFA"
            if tag:
                nfa = nfa.tagged(tag)
            return nfa
        else:
            raise SyncraftError(f"Cannot create NFA from {s!r}", offender=s, expect="str, bytes or Sequence[Enum|C]")

    def then(self, other: NFA[C]) -> NFA[C]:
        if self.universe != other.universe:
            raise MixedUniverseError("Cannot combine NFAs with different universes", offender=(self.universe, other.universe))
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
                              universe=this.universe,
                              init=this.init, 
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
        eps = {new_current: frozenset({self.init, other.init})}
        for k, v in self.epsilon.items():
            eps[k] = eps.get(k, frozenset()) | v
        for k, v in other.epsilon.items():
            eps[k] = eps.get(k, frozenset()) | v
        
        new_transitions = {**self.transitions}
        for k, v in other.transitions.items():
            new_transitions[k] = new_transitions.get(k, FrozenDict()) | v
        

        return replace(self,
                       universe=self.universe,
                       init=new_current, 
                       accept=FrozenDict({k: self.accept.get(k, frozenset()) | other.accept.get(k, frozenset()) for k in (self.accept | other.accept).keys()}), 
                       transitions=FrozenDict(new_transitions), 
                       epsilon=FrozenDict(eps))    
    def __or__(self, other: NFA[C]) -> NFA[C]:
        return self.union(other)

    @property
    def star(self) -> NFA[C]:
        new_current: FAState = FAState()
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
        new_current: FAState = FAState()
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
    
Automata = TypeVar('Automata', bound=NFA | DFA)


@dataclass(frozen=True)
class RunnerResult(Generic[C, Automata]):
    runner: Runner[C, Automata]    
    accepted: Optional[Tuple[int, frozenset[FAState] | FAState, Tuple[Tag, ...]]] = None


@dataclass(frozen=True)
class Runner(Protocol[C, Automata]):
    fa: Automata
    accepted: Tuple[Tuple[int, frozenset[FAState] | FAState, frozenset[Tag]], ...] = field(default_factory=tuple)
    post_processing: Callable[[frozenset[Tag]], tuple[Tag, ...]] = lambda t: tuple(sorted(dict.fromkeys(t), key=str))
    
    def priority(self, d: dict[Tag, int])->Runner[C, Automata]:
        def f(t: frozenset[Tag])->tuple[Tag, ...]:
            return tuple(sorted(self.post_processing(t), key=lambda x: d.get(x, -1), reverse=True))
        return replace(self, post_processing = f)
    
    def skip(self, ignore: frozenset[Tag])->Runner[C, Automata]:
        def f(t: frozenset[Tag])->tuple[Tag, ...]:
            return tuple(filter(lambda x: x not in ignore,  self.post_processing(t)))
        return replace(self, post_processing = f)
        
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
    @classmethod
    def create(cls, a: Automata) -> Self: ...
    def step(self, symbol: str | int | C, pos: int) -> RunnerResult[C, Automata]: ...
    def is_accepted(self) -> bool: ...
    def is_valid(self) -> bool: ...
    @cached_property
    def resumable(self) -> frozenset[CharSet[C]]: ...
    def tags(self) -> frozenset[Tag]: ...    
    def finalize(self) -> RunnerResult[C, Automata]: ...
    def gen(self, rnd:random.Random, pos:int = 0) -> None | Tuple[Sequence[C] | Sequence[Enum] | str | bytes, frozenset[str | Enum]]:
        def gen_one(r: Runner[C, Automata], possible_steps:frozenset[CharSet[C]]) -> Optional[Tuple[C, Runner[C, Automata]]]:
            nonlocal pos
            if possible_steps:
                ccls = rnd.choice(list(possible_steps))
                c = ccls.sample(rnd)
                result = r.step(c, pos)
                pos += 1
                return c, result.runner
            else:
                return None
        runner = self
        txt: List[Any]= []
        possible_steps = runner.resumable
        while possible_steps:
            match gen_one(runner, possible_steps):
                case None:
                    break
                case (c, r):
                    txt.append(c)
                    runner = r
            if runner.is_accepted():
                if len(txt) > 0:
                    break
                if rnd.random() < 0.5:
                    break
            possible_steps = runner.resumable
        if txt:
            if isinstance(txt[0], str):
                return (''.join(txt), runner.tags())                        
            elif isinstance(txt[0], int):
                return (bytes(txt), runner.tags())
            else:
                return (txt, runner.tags())
        return None
        
    @classmethod
    def generate(cls, a: Automata, pos: int = 0) -> None | Tuple[Sequence[C] | Sequence[Enum] | str | bytes, frozenset[str | Enum]]:
        return cls.create(a).gen(rnd=random.Random(), pos=pos)


@dataclass(frozen=True)
class NFARunner(Runner[C, NFA[C]]):
    current: frozenset[FAState] = field(default_factory=frozenset)
    @classmethod
    def create(cls, nfa: NFA[C]) -> NFARunner[C]:
        start_states = nfa.closure({nfa.init})
        advanced: set[FAState] = set()
        for s in start_states:
            entry = nfa.transitions.get(s, {})
            for cs, tgts in entry.items():
                if cs.interval == ((CharSet.START_CP, CharSet.START_CP),):
                    advanced.update(tgts)
        if advanced:
            start_states = nfa.closure(advanced)
        return cls(current=start_states, fa=nfa)
    
    def step(self, symbol: str | int | C, pos: int) -> RunnerResult[C, NFA[C]]:
        ss: str|bytes|list[Enum]|list[C]
        if isinstance(symbol, str):
            ss = symbol
        elif isinstance(symbol, int):
            ss = bytes([symbol])
        else:   
            ss = [symbol]
        assert len(ss) == 1, "symbol must be a single character"
        next_states = set()
        for s in self.current:
            entry: FrozenDict[CharSet[C], frozenset[FAState]] = self.fa.transitions.get(s, {})
            k: CharSet[C] = CharSet.create(ss, universe=self.fa.universe)
            if k in entry:
                next_states.update(entry[k])
            else:
                for char_class, targets in entry.items():
                    if isinstance(char_class, CharSet) and char_class(symbol):
                        next_states.update(targets)

        if not next_states:
            return RunnerResult(
                runner=replace(self, current=frozenset(), accepted=tuple()),
                accepted=(self.accepted[-1][0], self.accepted[-1][1], self.post_processing(self.accepted[-1][2])) if self.accepted else None,
            )                        
        else:
            new_current = self.fa.closure(next_states)
            new_runner = replace(self, current=frozenset(new_current))
            has_future_non_anchor = False
            for s2 in new_current:
                for cs2 in new_runner.fa.transitions.get(s2, {}).keys():
                    if not any(lo < 0 or hi < 0 for (lo, hi) in cs2.interval):
                        has_future_non_anchor = True
                        break
                if has_future_non_anchor:
                    break
            if new_runner.is_accepted():
                new_accepted = new_runner.accepted + ((pos, new_current, new_runner.tags()),)
                new_runner = replace(new_runner, accepted=new_accepted)
                if not has_future_non_anchor:
                    return RunnerResult(
                        runner=replace(new_runner, accepted=()),
                        accepted=(pos, new_current, new_runner.post_processing(new_runner.tags())),
                    )
            return RunnerResult(
                runner=new_runner,
                accepted=None,
            )
    
    def is_accepted(self) -> bool:
        return any(st in self.nfa.accept for st in self.current)
    
    def is_valid(self) -> bool:
        return bool(self.current)

    @cached_property
    def resumable(self) -> frozenset[CharSet[C]]:
        result: Set[CharSet[C]] = set()
        for s in self.current:
            result.update(self.nfa.transitions.get(s, {}).keys())
        filtered = [cs for cs in result if not any(lo < 0 or hi < 0 for (lo, hi) in cs.interval)]
        return frozenset(filtered)

    def tags(self) -> frozenset[str | Enum]:
        tags: Set[str | Enum] = set()
        for s in self.current:
            tags.update(self.nfa.accept.get(s, frozenset()))
        return frozenset(tags)
    
    def finalize(self) -> RunnerResult[C, NFA[C]]:
        next_states: set[FAState] = set()
        for s in self.current:
            entry = self.fa.transitions.get(s, {})
            for cs, tgts in entry.items():
                if cs.interval == ((CharSet.END_CP, CharSet.END_CP),):
                    next_states.update(tgts)
        if next_states:
            new_current = self.fa.closure(next_states)
        else:
            new_current = self.current
        
        new_runner = replace(self, current=new_current)
        if new_runner.is_accepted():
            pos = new_runner.accepted[-1][0] if new_runner.accepted else 0
            new_accepted = new_runner.accepted + ((pos, new_current, new_runner.tags()),)
            new_runner = replace(new_runner, accepted=new_accepted)
        return RunnerResult(
                runner=replace(new_runner, accepted = ()),
                accepted=(new_runner.accepted[-1][0], 
                        new_runner.accepted[-1][1], 
                        new_runner.post_processing(new_runner.accepted[-1][2])) if new_runner.accepted else None,
            )                        

    

@dataclass(frozen=True)
class DFARunner(Runner[C, DFA[C]]):
    current: Optional[FAState] = None

    @classmethod
    def create(cls, dfa: DFA[C]) -> DFARunner[C]:
        # Initialize at DFA init, then virtually consume one START anchor if present
        cur = dfa.init
        entry = dfa.transitions.get(cur, {})
        for cs, tgt in entry.items():
            if cs.interval == ((CharSet.START_CP, CharSet.START_CP),):
                cur = tgt
                break
        return cls(current=cur, fa=dfa)

    def _has_future_non_anchor(self, state: Optional[FAState]) -> bool:
        if state is None:
            return False
        for cs in self.fa.transitions.get(state, {}).keys():
            # Only count non-anchor charsets as future steps
            if not any(lo < 0 or hi < 0 for (lo, hi) in cs.interval):
                return True
        return False
    
    def step(self, symbol: str | int | C, pos: int) -> RunnerResult[C, DFA[C]]:
        ss: str|bytes|list[Enum]|list[C]
        if isinstance(symbol, str):
            ss = symbol
        elif isinstance(symbol, int):
            ss = bytes([symbol])
        else:   
            ss = [symbol]
        assert len(ss) == 1, "symbol must be a single character"
        next_state: Optional[FAState] = None
        entry: FrozenDict[CharSet[C], FAState] = self.fa.transitions.get(self.current, {})
        k: CharSet[C] = CharSet.create(ss, universe=self.fa.universe)
        if k in entry:
            next_state = entry[k]
        else:
            for char_class, targets in entry.items():
                if isinstance(char_class, CharSet) and char_class(symbol):
                    next_state = targets
                    break
        new_runner = replace(self, current=next_state)
        has_future = self._has_future_non_anchor(next_state)
        if next_state is None:
            return RunnerResult(
                runner=replace(new_runner, accepted=tuple()),
                accepted=(new_runner.accepted[-1][0], 
                          new_runner.accepted[-1][1], 
                          new_runner.post_processing(new_runner.accepted[-1][2])) if new_runner.accepted else None,
            )
        else:
            if new_runner.is_accepted() and next_state is not None:
                new_accepted = new_runner.accepted + ((pos, next_state, new_runner.tags()),)
                new_runner = replace(new_runner, accepted=new_accepted)
                if not has_future:
                    return RunnerResult(
                        runner=replace(new_runner, accepted=()),
                        accepted=(new_runner.accepted[-1][0], 
                                new_runner.accepted[-1][1], 
                                new_runner.post_processing(new_runner.accepted[-1][2])) if new_runner.accepted else None,
                    )
            return RunnerResult(
                runner=new_runner,
                accepted=None,
            )
    

    def is_accepted(self) -> bool:
        return self.current in self.dfa.accept

    def is_valid(self) -> bool:
        return bool(self.current)
    
    @cached_property
    def resumable(self) -> frozenset[CharSet[C]]:
        keys = self.dfa.transitions.get(self.current, {}).keys()
        filtered = [cs for cs in keys if not any(lo < 0 or hi < 0 for (lo, hi) in cs.interval)]
        return frozenset(filtered)

    def tags(self) -> frozenset[Tag]:
        return self.dfa.accept.get(self.current, frozenset())

    def finalize(self) -> RunnerResult[C, DFA[C]]:
        cur = self.current
        if cur is not None:
            entry = self.fa.transitions.get(cur, {})
            for cs, tgt in entry.items():
                if cs.interval == ((CharSet.END_CP, CharSet.END_CP),):
                    cur = tgt
                    break
        new_runner = replace(self, current=cur)
        if new_runner.is_accepted():
            assert cur is not None, 'Accepted state can not be None for DFA.'
            pos = new_runner.accepted[-1][0] if new_runner.accepted else 0
            new_accepted = new_runner.accepted + ((pos, cur, new_runner.tags()),)
            new_runner = replace(new_runner, accepted=new_accepted)
        return RunnerResult(
                runner=replace(new_runner, accepted = ()),
                accepted=(new_runner.accepted[-1][0], 
                        new_runner.accepted[-1][1], 
                        new_runner.post_processing(new_runner.accepted[-1][2])) if new_runner.accepted else None,
            )                        




Tag = Union[str, Enum]

class _NodeKind(str, Enum):
    LITERAL = "LITERAL"
    ONEOF = "ONEOF"
    CONCAT = "CONCAT"
    UNION = "UNION"
    INTERSECT = "INTERSECT"  # DFA-only
    DIFF = "DIFF"            # DFA-only (A - B)
    COMPLEMENT = "COMPLEMENT"  # DFA-only (universe - A)
    STAR = "STAR"
    PLUS = "PLUS"
    OPTIONAL = "OPTIONAL"
    MANY = "MANY"

FA = TypeVar('FA', bound=Union[NFA, DFA])
@dataclass(frozen=True)
class FABuilder(Generic[C]):
    kind: _NodeKind
    children: Tuple[FABuilder[C], ...] = field(default_factory=tuple)
    text: Optional[Union[str, bytes, Sequence[C]]] = None
    at_least: int = 1
    at_most: Optional[int] = None
    tag: Optional[Tag] = None

    # ---- Factory entry points ----

    @classmethod
    def literal(cls, text: Union[str, bytes, Sequence[C]], *, tag: Optional[Tag] = None) -> "FABuilder[C]":
        return cls(kind=_NodeKind.LITERAL, text=text, tag=tag)

    # Alias for convenience
    @classmethod
    def lit(cls, text: Union[str, bytes, Sequence[C]], *, tag: Optional[Tag] = None) -> FABuilder[C]:
        return cls.literal(text, tag=tag)

    @classmethod
    def oneof(cls, chars: Union[str, bytes, Sequence[C]], *, tag: Optional[Tag] = None) -> FABuilder[C]:
        return cls(kind=_NodeKind.ONEOF, text=chars, tag=tag)
    
    # ---- DSL operators ----
    def __add__(self, other: FABuilder[C]) -> FABuilder[C]:
        return FABuilder(kind=_NodeKind.CONCAT, children=(self, other))

    def __or__(self, other: FABuilder[C]) -> FABuilder[C]:
        return FABuilder(kind=_NodeKind.UNION, children=(self, other))

    def __and__(self, other: FABuilder[C]) -> FABuilder[C]:
        return FABuilder(kind=_NodeKind.INTERSECT, children=(self, other))

    def __sub__(self, other: FABuilder[C]) -> FABuilder[C]:
        return FABuilder(kind=_NodeKind.DIFF, children=(self, other))

    def __invert__(self) -> FABuilder[C]:  # optional (~)
        return FABuilder(kind=_NodeKind.OPTIONAL, children=(self,))

    def __neg__(self) -> FABuilder[C]:  # complement (-)
        return FABuilder(kind=_NodeKind.COMPLEMENT, children=(self,))

    @property
    def star(self) -> FABuilder[C]:
        return FABuilder(kind=_NodeKind.STAR, children=(self,))

    @property
    def plus(self) -> FABuilder[C]:
        # desugar plus -> concat(self, self.star)
        return (self + self.star)

    def many(self, *, at_least: int = 1, at_most: Optional[int] = None) -> FABuilder[C]:
        return FABuilder(kind=_NodeKind.MANY, children=(self,), at_least=at_least, at_most=at_most)

    def tagged(self, value: Tag) -> FABuilder[C]:
        return replace(self, tag=value)

    def compile(self, universe: CodeUniverse[C]) -> NFA[C] | DFA[C]: 
        match self.kind:
            case _NodeKind.UNION:
                left = self.children[0].compile(universe).nfa
                right = self.children[1].compile(universe).nfa
                return left.union(right)
            case _NodeKind.CONCAT:
                left = self.children[0].compile(universe).nfa
                right = self.children[1].compile(universe).nfa
                return left.then(right)
            case _NodeKind.LITERAL:
                if self.text is None:
                    raise SyncraftError("Literal FABuilder must have text", offender=self, expect="text is str, bytes, or Sequence")
                return NFA.from_string(self.text, universe=universe)
            case _NodeKind.ONEOF:
                if self.text is None:
                    raise SyncraftError("OneOf FABuilder must have text", offender=self, expect="text is str, bytes, or Sequence")
                return NFA.from_charset(self.text, universe=universe)
            case _NodeKind.STAR:
                inner = self.children[0].compile(universe).nfa
                return inner.star
            case _NodeKind.OPTIONAL:
                inner = self.children[0].compile(universe).nfa
                return inner.optional
            case _NodeKind.MANY:
                inner = self.children[0].compile(universe).nfa
                return inner.many(at_least=self.at_least, at_most=self.at_most)
            case _NodeKind.PLUS:
                inner = self.children[0].compile(universe).nfa
                return inner.star
            case _NodeKind.COMPLEMENT:
                # Require DFA planning for these operations
                inner1 = self.children[0].compile(universe).dfa
                return inner1.complement
            case _NodeKind.INTERSECT:
                # Require DFA planning for these operations
                left1 = self.children[0].compile(universe).dfa
                right1 = self.children[1].compile(universe).dfa
                return left1.intersection(right1)
            case _NodeKind.DIFF:
                # Require DFA planning for these operations
                left1 = self.children[0].compile(universe).dfa
                right1 = self.children[1].compile(universe).dfa
                return left1.difference(right1)
            case _:
                raise NotImplementedError(f"Unhandled FABuilder kind: {self.kind}")
            
    
    
    

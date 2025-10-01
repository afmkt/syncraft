from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, Optional, Sequence, Tuple, Union, TypeVar, Generic, List, Callable
from syncraft.charset import CodeUniverse
from syncraft.fa import DFA, NFA, FABuilder, ReverseDFA, Runner
from syncraft.ast import SyncraftError
from collections import deque
import random

C = TypeVar('C', bound=str | int | Enum | Any)

Tag = Union[str, Enum]

@dataclass
class Lexer(Generic[C]):
    universe: CodeUniverse[C]
    _current_mode: Mode[C] = field(init=False)
    _stack: deque[Mode[C]] = field(default_factory=deque)
    actions: Dict[Tag, Callable[[Lexer], None]] = field(default_factory=dict)
    modes: Dict[str | None, Mode[C]] = field(default_factory=dict)
    inputs: List[C] = field(default_factory=list)
    index: int = 0
    base: int = 0


    @property
    def current_mode(self) -> Mode[C]:
        if self._current_mode is None:
            if self._stack:
                self._current_mode = self._stack[-1]
            else:
                self._current_mode = self.modes[None]
        return self._current_mode
        
    def pop_mode(self) -> Mode[C]:
        self._stack.pop()
        if self._stack:
            self._current_mode = self._stack[-1]
        else:
            self._current_mode = self.modes[None]
        return self._current_mode

    def push_mode(self, mode_name: str | None = None) -> Mode[C]:
        if mode_name not in self.modes:
            raise SyncraftError(f"Cannot push unknown mode '{mode_name}'", offender=mode_name, expect=f"one of {list(self.modes.keys())}")
        self._stack.append(self.modes[mode_name])
        self._current_mode = self._stack[-1]
        return self._current_mode
    
    def set_mode(self, mode_name: str | None = None) -> Mode[C]:
        if mode_name not in self.modes:
            raise SyncraftError(f"Cannot set unknown mode '{mode_name}'", offender=mode_name, expect=f"one of {list(self.modes.keys())}")
        self._current_mode = self.modes[mode_name]
        return self._current_mode


    def gen(self, tag: Tag, rng: random.Random) -> str | bytes | list[C]:
        return self.current_mode.gen(tag, rng)
    
    def match(self, text: Union[str, bytes, Sequence[C]], index: int) -> Optional[MatchResult]:
        match self.current_mode.match(text, index):
            case int(new_pos):
                self.pos = new_pos
                return None
            case MatchResult(pos, value, tag):
                if pos == -1:



@dataclass(frozen=True)
class MatchResult:
    pos: int
    value: Any
    tag: Optional[Tag] = None

@dataclass
class Mode(Generic[C]):
    runner: Runner[C, DFA[C]]
    rdfa: ReverseDFA[C]
    skip: frozenset[Tag] = field(default_factory=frozenset)
    priority: Dict[Tag, int] = field(default_factory=dict)

    @classmethod
    def from_builder(cls, 
                     universe: CodeUniverse[C], 
                     skip: frozenset[Tag], 
                     priority: Dict[Tag, int], 
                     *rules: FABuilder[C]) -> "Mode[C]":
        if not rules:
            raise SyncraftError("Cannot build a Mode with no rules", offender=rules, expect="at least one rule")

        combined: Optional[NFA[C]] = None 
        for rule in rules:
            nfa = rule.compile(universe).nfa
            nfa = nfa.tagged(rule.tag) if rule.tag is not None else nfa
            combined = nfa if combined is None else combined.union(nfa)

        assert combined is not None
        dfa = combined.dfa.minimize
        return cls(runner=dfa.runner().priority(priority).skip(skip), 
                   rdfa=dfa.reverse, 
                   skip=skip, 
                   priority=priority)

    def gen(self, tag: Tag, rng: random.Random) -> str | bytes | list[C]:
        return self.rdfa.gen(tag, rng)


    def start(self) -> MatchResult:
        self.runner = self.runner.start()
        return MatchResult(pos=0, value=None, tag=None)

    def match(self, text: Union[str, bytes, Sequence[C]], index: int) -> MatchResult | int:            
        runner = self.runner
        pos = index
        last_accept_pos = None
        last_accept_tags : Tuple[Tag, ...] = ()

        if index < 0 or index >= len(text):
            rr = runner.finalize()
            runner = rr.runner
            if rr.accepted:
                last_accept_pos = -1
                last_accept_tags = rr.accepted[2]
        else:
            while pos < len(text):
                sym = text[pos]
                rr = runner.step(sym, pos)
                pos += 1
                runner = rr.runner
                if rr.accepted:
                    last_accept_pos = rr.accepted[0]
                    last_accept_tags = rr.accepted[2]
                    break
                elif not runner.is_valid():
                    break
        self.runner = runner
        if last_accept_pos is None:
            return pos
        chosen_tag = next(iter(last_accept_tags))
        if isinstance(text, str):
            value: Any = text[:last_accept_pos]
        elif isinstance(text, (bytes, bytearray, memoryview)):
            value = bytes(text[:last_accept_pos])
        else:
            value = list(text[:last_accept_pos])
        return MatchResult(pos=last_accept_pos, value=value, tag=chosen_tag)


__all__ = [
    "Lexer",
    "Mode",
    "ModeAction",
    "MatchResult",
]






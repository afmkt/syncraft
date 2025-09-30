from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, Optional, Sequence, Tuple, Union, TypeVar, Generic
from syncraft.charset import CodeUniverse
from syncraft.fa import DFA, NFA, FABuilder
from syncraft.constraint import FrozenDict
from syncraft.ast import SyncraftError
from collections import deque


C = TypeVar('C', bound=str | int | Enum | Any)



# Types
Tag = Union[str, Enum]

                

@dataclass(frozen=True)
class ModeAction:
    """Lexical mode transition action triggered by a matched tag."""
    push: Optional[str] = None
    pop: bool = False
    set: Optional[str] = None


@dataclass
class Lexer(Generic[C]):
    universe: CodeUniverse[C]
    _current_mode: Mode[C] = field(init=False)
    rule_actions: Dict[Tag, ModeAction] = field(default_factory=dict)
    modes: Dict[str | None, Mode[C]] = field(default_factory=dict)
    stack: deque[Mode[C]] = field(default_factory=deque)
    inputs: deque[C] = field(default_factory=deque)


    @property
    def current_mode(self) -> Mode[C]:
        if self._current_mode is None:
            if self.stack:
                self._current_mode = self.stack[-1]
            else:
                self._current_mode = self.modes[None]
        return self._current_mode
        
    def pop_mode(self) -> Mode[C]:
        self.stack.pop()
        if self.stack:
            self._current_mode = self.stack[-1]
        else:
            self._current_mode = self.modes[None]
        return self._current_mode

    def push_mode(self, mode_name: str | None = None) -> Mode[C]:
        if mode_name not in self.modes:
            raise SyncraftError(f"Cannot push unknown mode '{mode_name}'", offender=mode_name, expect=f"one of {list(self.modes.keys())}")
        self.stack.append(self.modes[mode_name])
        self._current_mode = self.stack[-1]
        return self._current_mode
    
    def set_mode(self, mode_name: str | None = None) -> Mode[C]:
        if mode_name not in self.modes:
            raise SyncraftError(f"Cannot set unknown mode '{mode_name}'", offender=mode_name, expect=f"one of {list(self.modes.keys())}")
        self._current_mode = self.modes[mode_name]
        return self._current_mode

    

@dataclass(frozen=True)
class MatchResult:
    end_index: int
    value: Any
    tag: Optional[Tag] = None

    accepted: Optional[Tuple[int, Tuple[Tag, ...]]] = None
@dataclass
class Mode(Generic[C]):
    dfa: DFA[C]
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

        return cls(dfa=combined.dfa.minimize, skip=skip, priority=priority)


    def match(self, text: Union[str, bytes, Sequence[C]], index: int) -> Optional[MatchResult]:
        if index < 0 or index > len(text):
            return None

        runner = self.dfa.runner().priority(self.priority).skip(self.skip)
        pos = index
        last_accept_pos = None
        last_accept_tags: FrozenSet[Tag] = frozenset()

        while pos < len(text):
            sym = text[pos]
            rr = runner.step(sym, pos)
            runner = rr.runner
            if not runner.is_valid():
                break
            tags_here = runner.tags()
            if tags_here:
                last_accept_pos = pos + 1
                last_accept_tags = tags_here
            pos += 1

        if last_accept_pos is None:
            return None
        chosen_tag = next(iter(last_accept_tags))
        if last_accept_pos <= index:
            return None
        if isinstance(text, str):
            value: Any = text[index:last_accept_pos]

        elif isinstance(text, (bytes, bytearray)):
            value = bytes(text[index:last_accept_pos])
        else:
            value = list(text[index:last_accept_pos])
        return MatchResult(end_index=last_accept_pos, value=value, tag=chosen_tag)


__all__ = [
    "Lexer",
    "Mode",
    "ModeAction",
    "MatchResult",
]






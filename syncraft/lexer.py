from __future__ import annotations
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, Set, Optional, Union, TypeVar, Generic, Tuple
from syncraft.charset import CodeUniverse
from syncraft.fa import DFA, NFA, FABuilder, ReverseDFA, Runner, ModeAction, ModeActionEnum
from syncraft.ast import SyncraftError
from syncraft.cache import Either, Left, Right, Cache
from collections import deque, defaultdict

import random

C = TypeVar('C', bound=str | int | Enum | Any)
A = TypeVar('A')
Ret = TypeVar('Ret', bound=Either[Any, Tuple[Any, Any]])




Tag = Union[str, Enum]


@dataclass
class Mode(Generic[C]):
    runner: Runner[C, DFA[C]]
    rdfa: ReverseDFA[C]
    priority: Dict[Tag, int] = field(default_factory=dict)
    skip: frozenset[Tag] = field(default_factory=frozenset)
    start_index: Optional[int] = None

    def reset(self) -> Mode[C]:
        return replace(self, runner=self.runner.reset(), start_index=None)
    
    def select_tag(self, tags: frozenset[Tag]) -> Optional[Tag]:
        if not tags:
            return None
        ordered = sorted(tags, key=str)
        filtered = [tag for tag in ordered if tag not in self.skip]
        if not filtered:
            return None
        if self.priority:
            filtered.sort(key=lambda tag: (-self.priority.get(tag, -1), str(tag)))
        return filtered[0]



@dataclass(frozen=True)
class LexerResult(Generic[C]):
    tag: Tag | None
    start: int
    end: int
    
@dataclass
class Lexer(Generic[C]):
    universe: CodeUniverse[C]
    modes: Dict[str | None, Mode[C]] 
    actions: Dict[Tag, ModeAction]
    _stack: deque[Mode[C]] = field(default_factory=deque)
    
    def _reset_runner(self, mode: Mode[C]) -> None:
        mode.runner = mode.runner.reset()
        mode.start_index = None
    
    def reset(self) -> Lexer[C]:
        ret = Lexer(
            universe=self.universe,
            modes={name: mode.reset() for name, mode in self.modes.items()},
            actions=self.actions,
            _stack=deque())
        ret.push_mode(None)
        return ret

    def clone(self) -> "Lexer[C]":
        """Return a deep-ish copy preserving runner state for backtracking."""
        mode_copies: Dict[str | None, Mode[C]] = {}
        for name, mode in self.modes.items():
            mode_copies[name] = replace(
                mode,
                runner=mode.runner,
                priority=dict(mode.priority),
                skip=frozenset(mode.skip),
                start_index=mode.start_index,
            )

        cloned = Lexer(
            universe=self.universe,
            modes=mode_copies,
            actions=dict(self.actions),
            _stack=deque(),
        )

        mode_lookup = {id(mode): name for name, mode in self.modes.items()}
        cloned._stack = deque(
            mode_copies[mode_lookup[id(mode)]] for mode in self._stack
        )
        return cloned
    
    @property
    def current_mode(self) -> Mode[C]:
        if not self._stack:
            return self.push_mode(None)
        return self._stack[-1]
        
    def pop_mode(self, mode_name: str | None = None) -> Mode[C]:
        if not self._stack:
            raise SyncraftError("Cannot pop mode from empty stack", offender=self._stack, expect="non-empty stack")
        if mode_name not in self.modes:
            raise SyncraftError(f"Cannot pop unknown mode '{mode_name}'", offender=mode_name, expect=f"one of {list(self.modes.keys())}")
        if self._stack[-1] is not self.modes.get(mode_name):
            raise SyncraftError(f"Cannot pop mode '{mode_name}' because it is not the current mode", offender=mode_name, expect=f"current mode '{self._stack[-1]}'")
        self._stack.pop()
        return self.current_mode

    def push_mode(self, mode_name: str | None = None) -> Mode[C]:
        if mode_name not in self.modes:
            raise SyncraftError(f"Cannot push unknown mode '{mode_name}'", offender=mode_name, expect=f"one of {list(self.modes.keys())}")
        target_mode = self.modes[mode_name]
        current = self._stack[-1] if self._stack else None
        if current is target_mode:
            return target_mode
        self._stack.append(target_mode)
        self._reset_runner(target_mode)
        return target_mode
            

    @staticmethod
    def one_mode(universe: CodeUniverse[C], *rules: FABuilder[C]) -> "Mode[C]":
        if not rules:
            raise SyncraftError("Cannot build a Mode with no rules", offender=rules, expect="at least one rule")
        skip: Set[Tag] = set()
        priority: Dict[Tag, int] = {}
        combined: Optional[NFA[C]] = None 
        for rule in rules:
            if rule.skip:
                assert rule.tag is not None, "Skip rules must have a tag"
                skip.add(rule.tag)
            if rule.priority != 0:
                assert rule.tag is not None, "Priority rules must have a tag"
                priority[rule.tag] = rule.priority
            nfa = rule.compile(universe).nfa
            nfa = nfa.tagged(rule.tag) if rule.tag is not None else nfa
            combined = nfa if combined is None else combined.union(nfa)

        assert combined is not None
        dfa = combined.dfa
        return Mode(runner=dfa.runner(), rdfa=dfa.reverse, priority=dict(priority), skip=frozenset(skip))

    @classmethod
    def from_builders(cls, 
                      universe: CodeUniverse[C], 
                      *rules: FABuilder[C],
                      default_mode: str | None = None) -> "Lexer[C]":
        modes: Dict[str | None, Set[FABuilder[C]]] = defaultdict(set)
        actions: Dict[Tag, ModeAction] = {}
        for rule in rules:
            match rule.action:
                case None:
                    modes[None].add(rule)
                case ModeAction(action=ModeActionEnum.PUSH, mode=mode_name, belong=belong_name):
                    assert mode_name is not None, "PUSH actions must have a mode"
                    if belong_name is not None:
                        modes[belong_name].add(rule)
                    else:
                        for mode, fas in modes.items():
                            if mode != mode_name:
                                fas.add(rule)
                    assert rule.tag is not None, "PUSH actions must have a tag"
                    actions[rule.tag] = rule.action
                case ModeAction(action=ModeActionEnum.BELONG, mode=mode_name, belong=belong_name):
                    assert mode_name is not None, "BELONG actions must have a mode"
                    assert belong_name is None, "BELONG actions cannot have a belong"
                    modes[mode_name].add(rule)
                case ModeAction(action=ModeActionEnum.POP, mode=mode_name, belong=belong_name):
                    assert mode_name is not None, "POP actions must have a mode"
                    assert belong_name is None, "POP actions cannot have a belong"
                    assert rule.tag is not None, "POP actions must have a tag"
                    actions[rule.tag] = rule.action
                    modes[mode_name].add(rule)

        

        lexer_modes: Dict[str | None, Mode[C]] = {}
        for mname, mode_rules in modes.items():
            lexer_modes[mname] = cls.one_mode(universe, *mode_rules)

        lexer = cls(universe=universe, modes=lexer_modes, actions=actions)
        lexer.push_mode(default_mode)
        return lexer

    def gen(self, tag: Tag, rng: random.Random) -> str | bytes | Tuple[C, ...]:
        ret = self.current_mode.rdfa.gen(tag, rng)
        act = self.actions.get(tag)
        if act is not None:
            match act:
                case ModeAction(action=ModeActionEnum.PUSH, mode=mode_name):
                    self.push_mode(mode_name)
                case ModeAction(action=ModeActionEnum.POP, mode=mode_name):
                    self.pop_mode(mode_name)
                case _:
                    raise SyncraftError(f"Unknown action {act}", offender=act, expect="PUSH, POP, or BELONG action")
        return ret

    def varify(self, tag: Tag | None, txt: str | bytes | Tuple[C, ...]) -> bool:
        lexer = self
        for index, char in enumerate(txt):
            match lexer.match(char, index): # type: ignore
                case Left(_):
                    return False
                case Right(None):
                    continue
                case Right(LexerResult(tag=t, start=s, end=e)):
                    if t != tag:
                        return False
                    if s != 0 or e != len(txt) - 1:
                        return False
                    if index != len(txt) - 1:
                        return False
                    return True
        return False

    def match(self, char: C, index: int) -> Either[Any, None | LexerResult[C]]:
        mode = self.current_mode
        if mode.start_index is None:
            mode.start_index = index
        rr = mode.runner.step(char, index)
        mode.runner = rr.runner
        if rr.error:
            mode.runner = mode.runner.reset()
            return Left(f"Lexing error at index {index} on char {char}")
        elif rr.final and rr.accepted is None:
            mode.runner = mode.runner.reset()
            return Left(f"Lexing reached final state at index {index} without acceptance")
        elif rr.final and rr.accepted is not None:
            accepted_pos, accepted_tags = rr.accepted
            tag = mode.select_tag(accepted_tags)
            if tag is None:
                self._reset_runner(mode)
                return Right(None)
            act = self.actions.get(tag)
            if act is not None:
                match act:
                    case ModeAction(action=ModeActionEnum.PUSH, mode=mode_name):
                        self.push_mode(mode_name)
                    case ModeAction(action=ModeActionEnum.POP, mode=mode_name):
                        self.pop_mode(mode_name)
                    case _:
                        raise SyncraftError(f"Unknown action {act}", offender=act, expect="PUSH, POP, or BELONG action")
            mode.runner = mode.runner.reset()
            start = mode.start_index if mode.start_index is not None else accepted_pos
            end = accepted_pos + 1
            mode.start_index = None
            return Right(
                LexerResult(
                    tag=tag,
                    start=start,
                    end=end
                )
            )
        return Right(None)






@dataclass
class CacheWithLexer(Cache[A, Ret], Generic[C, A, Ret]):
    lexer: Optional[Lexer[C]] = None

from __future__ import annotations
from dataclasses import dataclass, field, fields, replace, asdict, is_dataclass
from enum import Enum
from typing import (
    Any, Dict, Set, Optional, Union, TypeVar, Generic, Tuple, Protocol, 
    runtime_checkable, Callable, Mapping, Hashable, Type, List
)
from typing import TYPE_CHECKING
from syncraft.utils import CallWith
from syncraft.charset import CodeUniverse
from syncraft.fa import DFA, NFA, FABuilder, ReverseDFA, Runner, ModeAction, ModeActionEnum
from syncraft.ast import SyncraftError, Token
from syncraft.cache import Either, Left, Right, Cache
from collections import deque, defaultdict
import random
import re


def object_to_dict(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if is_dataclass(value):
        return asdict(value) # type: ignore[arg-type]
    if hasattr(value, "__dict__"):
        return vars(value)
    if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
        return {str(idx): elem for idx, elem in enumerate(value)}
    raise SyncraftError("Cannot introspect token fields", offender=value)


C = TypeVar('C', bound=str | int | Enum | Any)
A = TypeVar('A')
Ret = TypeVar('Ret', bound=Either[Any, Tuple[Any, Any]])


if TYPE_CHECKING:  # pragma: no cover - avoids circular import at runtime
    from syncraft.syntax import FactorySpec, Syntax




Tag = str


@dataclass
class Mode(Generic[C]):
    runner: Runner[C, DFA[C]]
    rdfa: ReverseDFA[C]
    priority: Dict[Tag, int] = field(default_factory=dict)
    skip: frozenset[Tag] = field(default_factory=frozenset)
    non_greedy: frozenset[Tag] = field(default_factory=frozenset)
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
    value: Any | None = None


@runtime_checkable
class LexerProtocol(Protocol, Generic[C]):
    def clone(self) -> "LexerProtocol[C]": ...

    def match(self, tag: frozenset[Tag], char: C, index: int) -> Either[Any, None | LexerResult[C]]: ...

    def varify(self, tag: frozenset[Tag], value: Any) -> bool: ...


    def gen(self, tag: Tag, rng: random.Random) -> Any: ...

    def candidate(self) -> Either[Any, None | LexerResult[C]]: ...
    
    @classmethod
    def from_kwargs(cls, **kwargs: Any) -> "LexerProtocol[C]": ...

    @classmethod
    def bind(cls, *args:Any, **kwargs: Any) -> Type["LexerProtocol[C]"]: ...

@dataclass
class Lexer(LexerProtocol[C], Generic[C]):
    universe: CodeUniverse[C]
    modes: Dict[str | None, Mode[C]] 
    actions: Dict[Tag, ModeAction]
    _stack: deque[Mode[C]] = field(default_factory=deque)

    @classmethod
    def from_kwargs(cls, **kwargs: Any) -> "Lexer[C]":
        raise NotImplementedError("Lexer cannot be constructed from syntax directly; use from_builders or another method")


    def _reset_runner(self, mode: Mode[C]) -> None:
        mode.runner = mode.runner.reset()
        mode.start_index = None
    
    def clone(self) -> "Lexer[C]":
        """Return a deep-ish copy preserving runner state for backtracking."""
        mode_copies: Dict[str | None, Mode[C]] = {}
        for name, mode in self.modes.items():
            mode_copies[name] = replace(
                mode,
                runner=mode.runner,
                priority=dict(mode.priority),
                skip=frozenset(mode.skip),
                non_greedy=frozenset(mode.non_greedy),
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
        non_greedy: Set[Tag] = set()
        combined: Optional[NFA[C]] = None 
        for rule in rules:
            if rule.skip:
                assert rule.tag is not None, "Skip rules must have a tag"
                skip.add(rule.tag)
            if rule.priority != 0:
                assert rule.tag is not None, "Priority rules must have a tag"
                priority[rule.tag] = rule.priority
            if rule.non_greedy:
                assert rule.tag is not None, "Greedy rules must have a tag"
                non_greedy.add(rule.tag)
            nfa = rule.compile(universe).nfa
            nfa = nfa.tagged(rule.tag) if rule.tag is not None else nfa
            combined = nfa if combined is None else combined.union(nfa)

        assert combined is not None
        dfa = combined.dfa
        non_greedy_set = frozenset(non_greedy)
        return Mode(
            runner=dfa.runner(non_greedy=non_greedy_set),
            rdfa=dfa.reverse,
            priority=dict(priority),
            skip=frozenset(skip),
            non_greedy=non_greedy_set,
        )

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

    def gen(self, tag: Tag, rng: random.Random) -> Any:
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

    def varify(self, tag: frozenset[Tag], value: Any) -> bool:
        if isinstance(value, Token):
            if len(tag) > 0 and value.token_type not in tag:
                return False
            txt = value.text
        else:
            txt = value

        if not isinstance(txt, (str, bytes, tuple)):
            return False

        lexer = self
        for index, char in enumerate(txt):
            match lexer.match(tag, char, index):  # type: ignore[arg-type]
                case Left(_):
                    return False
                case Right(None):
                    continue
                case Right(LexerResult(tag=t, start=s, end=e)):
                    if len(tag) > 0 and t not in tag:
                        return False
                    if s != 0 or e != len(txt) - 1:
                        return False
                    if index != len(txt) - 1:
                        return False
                    return True
        return False

    def candidate(self) -> Either[Any, None | LexerResult[C]]:
        mode = self.current_mode
        if mode.start_index is None:
            return Left("Cannot get candidate when no input has been processed")
        
        candidate_ = mode.runner.candidates
        if not candidate_:
            return Left("No candidate available")
        latest = candidate_[-1]
        return Right(
            LexerResult(
                tag=mode.select_tag(latest[1]),
                start=mode.start_index,
                end=latest[0] + 1
            )
        )

    def match(self, tags:frozenset[Tag], char: C, index: int) -> Either[Any, None | LexerResult[C]]:
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

    @classmethod
    def bind(cls, universe: CodeUniverse[C], default_mode: str | None = None) -> Type["Lexer[C]"]:
        def fabuilder(**kwargs: Any) -> Set[FABuilder[Any]]:
            acc: Set[FABuilder[Any]] = set()
            for k, v in kwargs.items():
                if isinstance(v, FABuilder):
                    if v.tag is None and k != '_':
                        acc.add(v.tagged(k))
                    else:
                        acc.add(v)                    
            return acc
        class BoundLexer(Lexer[Any]):
            @classmethod
            def from_kwargs(cls, **kwargs: Any) -> "Lexer[C]":
                u = kwargs.pop('universe', universe)
                d = kwargs.pop('default_mode', default_mode)
                builders = fabuilder(**kwargs)
                return cls.from_builders(u, *builders, default_mode=d)
        return BoundLexer






T = TypeVar('T', bound=Hashable)
@runtime_checkable
class TokenSpec(Protocol[T]):
    def tags(self, **kwargs: Any) -> frozenset[Tag]: ...
    def predicate(self, **kwargs: Any) -> Callable[[T], bool]: ...
    def generator(self, **kwargs: Any) -> Callable[[Any, random.Random], T]: ...
    

@dataclass(frozen=True)
class ExtRule(Generic[T]):
    predicate: Callable[[T], bool]
    generator: Callable[[Any, random.Random], T]

@dataclass
class ExtLexer(LexerProtocol[T]):
    tkspec: TokenSpec[T]
    rules: Dict[Tag|None, ExtRule[T]] = field(default_factory=dict)


    @classmethod
    def from_kwargs(cls, **kwargs: Any) -> "ExtLexer[T]":
        raise NotImplementedError("ExtLexer cannot be constructed from syntax directly; use create or another method")
    
    @classmethod
    def bind(cls, tkspec: TokenSpec[T]) -> Type[ExtLexer[T]]:
        class BoundLexer(ExtLexer[Any]):
            @classmethod
            def from_kwargs(cls, **kwargs: Any) -> "ExtLexer[T]":
                ret = cls(tkspec = tkspec)
                ret.register(**kwargs)
                return ret
        return BoundLexer
    
    def clone(self) -> "ExtLexer[T]":
        return replace(self, rules=dict(self.rules))

    def register(
        self,
        **kwargs: Any,
    ) -> None:
        # from rich import print
        def register_one(tag: Tag | None, spec: TokenSpec, **kwargs: Any) -> None:
            existing = self.rules.get(tag)
            if existing is None:
                pred = spec.predicate(**kwargs) 
                gen = spec.generator(**kwargs) 
                self.rules[tag] = ExtRule(pred, gen)

        specs = {k: v for k, v in kwargs.items() if isinstance(v, TokenSpec)}
        non_specs = {k: v for k, v in kwargs.items() if not isinstance(v, TokenSpec)}
        if specs:
            for tag, v in specs.items():
                register_one(tag, v, **non_specs)
        elif non_specs:
            for t in self.tkspec.tags(**non_specs):
                register_one(t, self.tkspec, **non_specs)
        # print(self.rules)

    def candidate(self) -> Either[Any, None | LexerResult[T]]:
        return Left("External lexer cannot provide candidates")

    def match(self, tags: frozenset[Tag], item: T, index: int) -> Either[Any, None | LexerResult[T]]:
        for tag in tags:
            if tag in self.rules and self.rules[tag].predicate(item):
                return Right(LexerResult(tag=tag, start=index, end=index + 1, value=item))            
        return Left(f"External lexer has no rule for token at index {index}: {item!r}")
        

    def varify(self, tag: frozenset[Tag], value: Any) -> bool:
        for t in tag:
            rule = self.rules.get(t)
            if rule is not None:
                if rule.predicate(value):
                    return True
        return False

    def gen(self, tag: Tag, rng: random.Random) -> Any:
        rule = self.rules.get(tag)
        if rule is None or rule.generator is None:
            raise SyncraftError(
                f"External lexer cannot generate tokens for tag '{tag}'",
                offender=self,
                expect="generator callable",
            )
        return rule.generator(tag, rng)







from __future__ import annotations
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import (
    Any, Dict, Set, Optional, TypeVar, Generic, Tuple, Protocol, ClassVar,
    runtime_checkable, Callable, Hashable
)

from syncraft.path import builtin_cache_path, user_cache_path
from syncraft.utils import CallWith
from syncraft.alphabet import AlphabetProtocol
from syncraft.fa import NFA, Builder, ReverseDFA, Runner, ModeAction, ModeActionEnum
from syncraft.ast import SyncraftError, Token
from syncraft.cache import Either, Left, Right
from collections import deque, defaultdict
import random
from pathlib import Path
import hashlib
import threading
from syncraft.token import TokenSpec, all_subclasses
from functools import cached_property
import pickle



C = TypeVar('C', bound=Hashable)
A = TypeVar('A')
Ret = TypeVar('Ret', bound=Either[Any, Tuple])
T = TypeVar('T', bound=Hashable)






Tag = str | Enum

@dataclass(frozen=True, slots=True)
class LexerError:
    message: str
    index: int
    offender: Hashable
    expect: frozenset[Hashable]
    @classmethod
    def new(cls, message: str, index: int, offender: Hashable, expect: frozenset[Hashable]) -> LexerError:
        obj = cls.__new__(cls)
        object.__setattr__(obj, 'message', message)
        object.__setattr__(obj, 'index', index)
        object.__setattr__(obj, 'offender', offender)
        object.__setattr__(obj, 'expect', expect)
        return obj

    @classmethod
    def message_only(cls, message: str) -> "LexerError":
        return cls(message=message, index=-1, offender=None, expect=frozenset())

@dataclass
class Mode(Generic[C]):
    runner: Runner[C]
    rdfa: ReverseDFA[C]
    priority: Dict[Tag, int] = field(default_factory=dict)
    skip: frozenset[Tag] = field(default_factory=frozenset)
    non_greedy: frozenset[Tag] = field(default_factory=frozenset)
    start_index: Optional[int] = None


    @cached_property
    def has_skip(self) -> bool:
        return bool(self.skip)

    
    def reset(self) -> None:
        self.runner = self.runner.reset()
        self.start_index = None
        
    
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



@dataclass(frozen=True, slots=True)
class LexerResult(Generic[C]):
    tag: Tag | None
    start: int
    end: int
    value: Any | None = None

    @classmethod
    def new(cls, tag: Tag | None, start: int, end: int, value: Any | None = None) -> "LexerResult[C]":
        obj = cls.__new__(cls)
        object.__setattr__(obj, 'tag', tag)
        object.__setattr__(obj, 'start', start)
        object.__setattr__(obj, 'end', end)
        object.__setattr__(obj, 'value', value)
        return obj


@runtime_checkable
class LexerProtocol(Protocol, Generic[C]):
    def reset(self) -> None: ...

    def match(self, tag: frozenset[Tag | None], char: C, index: int) -> LexerError | None | LexerResult[C]: ...

    def varify(self, tag: frozenset[Tag | None], value: Any) -> bool: ...

    def tags(self) -> frozenset[str|Enum|None]: ...

    def gen(self, tag: Tag | None, rng: random.Random) -> Tuple[Tuple[Any, ...], Dict[str, Any]]: ...

    def candidate(self) -> LexerError | LexerResult[C]: ...
    
    @classmethod
    def create(cls, *args: Any, **kwargs: Any) -> Optional[LexerProtocol[C]]: ...


    @classmethod
    def from_kwargs(cls, *args: Any, **kwargs: Any) -> Tuple[Optional[LexerProtocol[C]], Dict[str, Any]]: ...

    @property
    def filepath(self) -> Optional[Path]: ...

class LexerBase(LexerProtocol[C]):
    @classmethod
    def from_kwargs(cls, *args: Any, **kwargs: Any) -> Tuple[Optional[LexerProtocol[C]], Dict[str, Any]]:
        for sub in all_subclasses(cls):
            c = CallWith(sub.create, *args, **kwargs)
            if not c.missing_args and not c.missing_kwargs:
                ret = c()
                if ret is not None:
                    return ret, c.unused_kwargs
        return None, kwargs

@dataclass(slots=True)
class LexerCache:

    dict: Dict[str, Lexer[Any]] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)

    @staticmethod
    def _load(dir: Path, key: str) -> Optional[Lexer[Any]]:
        file = dir / f"{key}.lex"
        if file.exists():
            with open(file, "rb") as f:
                try:
                    return pickle.load(f)
                except Exception as e:
                    print(e)
                    print("Failed to load lexer from cache:", file)
                    file.unlink()
        return None
    
    @staticmethod
    def _save(dir: Path, key: str, lexer: Lexer[Any]) -> None:
        dir.mkdir(parents=True, exist_ok=True)
        file = dir / f"{key}.lex"
        with open(file, "wb") as f:
            pickle.dump(lexer, f)

    def load(self, 
             *,
             builders: Set[Builder[Any]], 
             factory: Callable[[], Lexer[Any]],
             dir: Path) -> Tuple[Lexer[Any], Path]:
        tmp = sorted(repr(fb) for fb in builders)
        joined = "\n".join(tmp)
        key = hashlib.sha256(joined.encode("utf-8")).hexdigest()

        with self.lock:
            if key in self.dict:
                return self.dict[key], dir / f"{key}.lex"
            else:
                lexer = self._load(dir, key)
                if lexer is not None:
                    self.dict[key] = lexer
                    return lexer, dir / f"{key}.lex"
                lexer = factory()
                if lexer is not None:
                    self.dict[key] = lexer
                    self._save(dir, key, lexer)
                    return lexer, dir / f"{key}.lex"
                raise SyncraftError(
                    "Lexer factory did not produce a lexer",
                    offender=factory,
                    expect="a Lexer instance",
                )
            
@dataclass(slots=True)
class Lexer(LexerBase[C]):
    modes: Dict[str | None, Mode[C]]     
    actions: Dict[Tag | None, ModeAction]
    default_mode: str | None 
    _stack: deque[Mode[C]] = field(default_factory=deque)
    cache: ClassVar[LexerCache] = LexerCache()
    filepath: Optional[Path] = None

    
    def tags(self) -> frozenset[str|Enum|None]:
        all_tags: Set[Tag|None] = set()
        for mode in self.modes.values():
            for tags in mode.runner.dfa.accept.values():
                if tags:
                    all_tags.update(tags)
                else:
                    all_tags.add(None)
        return frozenset(all_tags)

    @classmethod
    def create(cls, 
               *args: Builder,
               default_mode:str|None=None,
               builtin: bool = False,
               cache_path: str | Path | None = None,
               ) -> Optional["Lexer[C]"]:
        def fabuilder(*args: Any) -> Tuple[Set[Builder[Any]], Path]:
            if builtin:
                path = builtin_cache_path()
            else:
                path = user_cache_path(cache_path)

            acc: Set[Builder[Any]] = set()
            for v in args:
                if isinstance(v, Builder):
                    acc.add(v)                    
            return acc, path

        builders, dir = fabuilder(*args)
        if not builders:
            return None
        lexer, path = cls.cache.load(builders=builders, 
                              factory=lambda: cls.from_builders(*builders, default_mode=default_mode),
                              dir=dir)
        lexer.filepath = path
        return lexer

    def reset(self) -> None:
        self.current_mode.reset()
    
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
        target_mode.reset()
        return target_mode
            

    @staticmethod
    def one_mode(*rules: Builder[C]) -> "Mode[C]":
        if not rules:
            raise SyncraftError("Cannot build a Mode with no rules", offender=rules, expect="at least one rule")
        alphabet: Optional[AlphabetProtocol[C]] = None
        for rule in rules:
            if alphabet is None:
                alphabet = rule.alphabet
                break
                
        assert alphabet is not None, "Cannot build a Mode without an alphabet"

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
            nfa = rule.compile(alphabet).nfa
            nfa = nfa.tagged(rule.tag) if rule.tag is not None else nfa
            combined = nfa if combined is None else combined.union(nfa)

        assert combined is not None
        dfa = combined.dfa.normalized
        non_greedy_set = frozenset(non_greedy)
        return Mode(
            runner=dfa.runner(non_greedy=non_greedy_set),
            rdfa=dfa.reverse,
            priority=dict(priority),
            skip=frozenset(skip),
            non_greedy=non_greedy_set,
        )

    @classmethod
    def from_builders(cls, *rules: Builder[C], default_mode: str | None = None) -> Lexer[C]:
        if len(rules) == 0:
            raise SyncraftError("Cannot build a Lexer with no rules", offender=rules, expect="at least one rule")
        modes: Dict[str | None, Set[Builder[C]]] = defaultdict(set)
        actions: Dict[Tag | None, ModeAction] = {}
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
            lexer_modes[mname] = cls.one_mode(*mode_rules)

        lexer = cls(modes=lexer_modes, actions=actions, default_mode=default_mode)
        lexer.push_mode(default_mode)
        return lexer

    def gen(self, tag: Tag | None, rng: random.Random) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
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
        return ((), {'text': ret, 'token_type': tag})

    def varify(self, tag: frozenset[Tag | None], value: Any) -> bool:
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
                case None:
                    continue
                case LexerResult(tag=t, start=s, end=e):
                    if len(tag) > 0 and t not in tag:
                        return False
                    if s != 0 or e != len(txt):
                        return False
                    if index != len(txt) - 1:
                        return False
                    return True
                case _:
                    return False                
        return False

    def candidate(self) -> LexerError | LexerResult[C]:
        mode = self.current_mode
        if mode.start_index is None:
            return LexerError.message_only("Cannot get candidate when no input has been processed")
        
        candidate_ = mode.runner.candidates
        if not candidate_:
            return LexerError.message_only("No candidate available")
        latest = candidate_[-1]
        return LexerResult(
                tag=mode.select_tag(latest[1]),
                start=mode.start_index,
                end=latest[0] + 1
            )
        

    def match(self, tags:frozenset[Tag|None], char: C, index: int) -> LexerError | None | LexerResult[C]:
        mode = self.current_mode
        if mode.start_index is None:
            mode.start_index = index
        rr = mode.runner.step(char, index)
        if rr.error:
            expecting = mode.runner.resumable
            mode.runner = mode.runner.reset()
            return LexerError(
                message="Lexing mismatch",
                index=index,
                offender=char,
                expect=frozenset(str(e) for e in expecting) if expecting else tags,
            )

        if rr.final and rr.accepted is None:
            mode.runner = mode.runner.reset()
            return LexerError(
                message=f"Lexing reached final state at index {index} without acceptance",
                index=index,
                offender=char,
                expect=frozenset(),
            )

        if rr.final and rr.accepted is not None:
            accepted_pos, accepted_tags = rr.accepted
            tag = mode.select_tag(accepted_tags)
            if tag is None and mode.has_skip:
                mode.reset()
                return None
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
            return LexerResult(
                    tag=tag,
                    start=start,
                    end=end
                )
            
        return None
    


@dataclass(frozen=True, slots=True)
class ExtRule(Generic[T]):
    predicate: Callable[[T], bool]
    generator: Callable[[Any, random.Random], Tuple[Tuple[Any, ...], Dict[str, Any]]]

@dataclass(slots=True)
class ExtLexer(LexerBase[T]):
    rules: Dict[Tag|None, ExtRule[T]] = field(default_factory=dict)

    def reset(self) -> None:
        pass

    def tags(self) -> frozenset[str|Enum|None]:
        return frozenset(self.rules.keys())

    @classmethod
    def create(cls, tkspec: TokenSpec) -> Optional[ExtLexer[T]]:
        if isinstance(tkspec, TokenSpec):
            ret = cls()
            for t in tkspec.tags():
                existing = ret.rules.get(t)
                if existing is None:
                    pred = tkspec.predicate()
                    gen = tkspec.generator() 
                    ret.rules[t] = ExtRule(pred, gen)
            return ret
        return None
    
    
    def clone(self) -> "ExtLexer[T]":
        return replace(self, rules=dict(self.rules))

    

    def candidate(self) -> LexerError | LexerResult[T]:
        return LexerError.message_only("External lexer cannot provide candidates")

    def match(self, tags: frozenset[Tag|None], item: T, index: int) -> LexerError | None | LexerResult[T]:
        for tag in tags:
            if tag in self.rules and self.rules[tag].predicate(item):
                return LexerResult(tag=tag, start=index, end=index + 1, value=item)
                
        return LexerError.new(
            message=f"External lexer token mismatch, {tags} did not match item '{item}'",
            index=index,
            offender=item,
            expect=frozenset(tags)
        )
        

    def varify(self, tag: frozenset[Tag | None], value: Any) -> bool:
        for t in tag:
            rule = self.rules.get(t)
            if rule is not None:
                if rule.predicate(value):
                    return True
        return False

    def gen(self, tag: Tag | None, rng: random.Random) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
        rule = self.rules.get(tag)
        if rule is None or rule.generator is None:
            raise SyncraftError(
                f"External lexer cannot generate tokens for tag '{tag}'",
                offender=self,
                expect="generator callable",
            )
        return rule.generator(tag, rng)







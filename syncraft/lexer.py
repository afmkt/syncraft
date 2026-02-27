from __future__ import annotations
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import (
    Any, Dict, Set, Optional, TypeVar, Generic, Tuple, ClassVar,
    Callable, Hashable
)

from syncraft.path import builtin_cache_path, user_cache_path

from syncraft.alphabet import AlphabetProtocol
from syncraft.fa import DEFAULT_TAG, NFA, Builder, ReverseDFA, Runner, ModeAction, ModeActionEnum, DFA
from syncraft.ast import SyncraftError
from syncraft.cache import Either
from collections import deque, defaultdict
import random
from pathlib import Path
import hashlib
import threading
from syncraft.token import TokenSpec
from functools import cached_property
import pickle
from syncraft.lexerprotocol import LexerProtocol, LexerError, LexerResult, LexerBuilder

Tag = str | Enum

C = TypeVar('C', bound=Hashable)
A = TypeVar('A')
Ret = TypeVar('Ret', bound=Either[Any, Tuple])
T = TypeVar('T', bound=Hashable)



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
                    normalize = lexer._normalize_default_tags
                    if callable(normalize) and normalize():
                        self._save(dir, key, lexer)
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
class Lexer(LexerProtocol[C]):
    modes: Dict[str | None, Mode[C]] = field(default_factory=dict)
    actions: Dict[Tag | None, ModeAction] = field(default_factory=dict)

    _stack: deque[Mode[C]] = field(default_factory=deque)
    cache: ClassVar[LexerCache] = LexerCache()
    filepath: Optional[Path] = field(default=None, compare=False, hash=False, repr=False)

    def _normalize_default_tags(self) -> bool:
        def needs_normalization(mode: Mode[C]) -> bool:
            has_default_tag = False
            for tags in mode.runner.dfa.accept.values():
                if not tags:
                    return True
                if DEFAULT_TAG in tags:
                    has_default_tag = True
                    if len(tags) > 1:
                        return True
            if not has_default_tag:
                return False
            return False

        changed = False
        for mode in self.modes.values():
            if not needs_normalization(mode):
                continue
            dfa = mode.runner.dfa.with_default_tag_invariant()
            self._raise_on_unreachable_accept(dfa)
            mode.runner = dfa.runner(non_greedy=mode.non_greedy)
            mode.rdfa = dfa.reverse
            changed = True
        return changed

    @staticmethod
    def _raise_on_unreachable_accept(dfa: DFA[Any]) -> None:
        by_tag = dfa.accept_reachability()
        for tag, (reachable, unreachable) in by_tag.items():
            if unreachable:
                raise SyncraftError(
                    "Unreachable accept state(s) detected",
                    offender={"tag": tag, "reachable": reachable, "unreachable": unreachable},
                    expect="accept states reachable from init",
                )

    
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
                              factory=lambda: cls.from_builders(*builders),
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
        dfa = combined.dfa.normalized.with_default_tag_invariant()
        Lexer._raise_on_unreachable_accept(dfa)
        non_greedy_set = frozenset(non_greedy)
        return Mode(
            runner=dfa.runner(non_greedy=non_greedy_set),
            rdfa=dfa.reverse,
            priority=dict(priority),
            skip=frozenset(skip),
            non_greedy=non_greedy_set,
        )

    @classmethod
    def from_builders(cls, *rules: Builder[C]) -> Lexer[C]:
        if len(rules) == 0:
            raise SyncraftError("Cannot build a Lexer with no rules", offender=rules, expect="at least one rule")
        modes: Dict[str | None, Set[Builder[C]]] = defaultdict(set)
        universal_rules: Set[Builder[C]] = set()
        actions: Dict[Tag | None, ModeAction] = {}
        def add_rule_to_mode(rule: Builder[C], belong_name: str | None) -> None:
            if belong_name == '*':
                universal_rules.add(rule)
            else:
                modes[belong_name].add(rule)

        for rule in rules:
            match rule.action:
                case None:
                    modes[None].add(rule)
                case ModeAction(action=ModeActionEnum.PUSH, belong=belong_name):
                    add_rule_to_mode(rule, belong_name)
                    assert rule.tag is not None, "PUSH actions must have a tag"
                    actions[rule.tag] = rule.action
                case ModeAction(action=ModeActionEnum.BELONG, belong=belong_name):
                    add_rule_to_mode(rule, belong_name)
                case ModeAction(action=ModeActionEnum.POP, belong=belong_name):
                    add_rule_to_mode(rule, belong_name)
                    assert rule.tag is not None, "POP actions must have a tag"
                    actions[rule.tag] = rule.action
        
        for r in universal_rules:
            for mode_rules in modes.values():
                mode_rules.add(r)


        lexer_modes: Dict[str | None, Mode[C]] = {}
        for mname, mode_rules in modes.items():
            lexer_modes[mname] = cls.one_mode(*mode_rules)

        lexer = cls(modes=lexer_modes, actions=actions)
        lexer.push_mode(None)
        return lexer

    def gen(self, tag: Tag | None, rng: random.Random) -> Any:
        ret = self.current_mode.rdfa.gen(tag, rng)
        act = self.actions.get(tag)
        if act is not None:
            match act:
                case ModeAction(action=ModeActionEnum.PUSH, mode=mode_name):
                    self.push_mode(mode_name)
                case ModeAction(action=ModeActionEnum.POP, belong=mode_name):
                    self.pop_mode(mode_name)
                case _:
                    raise SyncraftError(f"Unknown action {act}", offender=act, expect="PUSH, POP, or BELONG action")
        return ((ret, tag), {})

    def verify(self, tag: frozenset[Tag | None], value: Any) -> bool:
        txt = value
        lexer = self
        try:
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
            candidate = lexer.candidate()
            if isinstance(candidate, LexerResult):
                if len(tag) > 0 and candidate.tag not in tag:
                    return False
                return candidate.start == 0 and candidate.end == len(txt)
        except TypeError:
            raise SyncraftError(
                f"Value {value} is not valid for verification, expected an eenumerable object like string, bytes, or tuple",
                offender=value,
                expect="an enumerable object",
            )
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
        old_state = mode.runner.current
        rr = mode.runner.step(char, index)
        if rr.error:
            expecting = mode.runner.resumable_str(old_state)
            mode.runner = mode.runner.reset()
            exp = expecting or tags
            return LexerError(
                message=f"Lexing mismatch '{char}' at index {index}, expect {exp}",
                index=index,
                offender=char,
                expect=exp,
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
class ExtLexer(LexerProtocol[T]):
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
        

    def verify(self, tag: frozenset[Tag | None], value: Any) -> bool:
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





@dataclass(frozen=True, slots=True)
class LocalLexerBuilder(LexerBuilder[C]):
    lexer: LexerProtocol[C] | None = field(default=None, compare=False, hash=False, repr=False)
    def __call__(self, arg: TokenSpec | Builder, **kwargs: Any) -> LocalLexerBuilder[C]:
        if isinstance(arg, TokenSpec):
            tlexer: ExtLexer[C] | None = ExtLexer.create(arg)
            if tlexer is not None:
                return LocalLexerBuilder(lexer=tlexer)
        elif isinstance(arg, Builder):
            lexer: LexerProtocol[C] | None = Lexer.create(arg, **kwargs)
            if lexer is not None:
                return LocalLexerBuilder(lexer=lexer)
        raise SyncraftError(
            f"LocalLexerBuilder cannot create a lexer from argument of type {type(arg)}",
            offender=(arg, kwargs),
            expect="a TokenSpec or Builder instance",
        )

    def resolve(self) -> LexerProtocol[C]:
        assert self.lexer is not None, "LocalLexerBuilder has not been called with valid arguments to create a lexer"
        return self.lexer

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LocalLexerBuilder):
            return False
        return self.lexer is other.lexer

    def __hash__(self) -> int:
        return hash(id(self.lexer))
    

@dataclass(slots=True)
class GlobalLexerBuilder(LexerBuilder[C]):
    args: Set[Builder] = field(default_factory=set)

    builtin: bool = False
    cache_path: str | Path | None = None 
    lexer: LexerProtocol[C] | None = field(default=None, compare=False, hash=False, repr=False)
    def __call__(self, arg: TokenSpec | Builder, **kwargs: Any) -> GlobalLexerBuilder[C]:
        if isinstance(arg, Builder):
            # Set automatically handles deduplication
            self.args.add(arg)
            self.builtin = kwargs.get("builtin", self.builtin)
            self.cache_path = kwargs.get("cache_path", self.cache_path)
            return self
        elif isinstance(arg, TokenSpec):
            assert not self.args, "Cannot mix Syntax.lit with Syntax.re/Syntax.lit"
            lexer: ExtLexer[C] | None = ExtLexer.create(arg)
            if lexer is not None:
                return GlobalLexerBuilder(args=self.args, builtin=self.builtin, cache_path=self.cache_path, lexer=lexer)
        raise SyncraftError(
            f"GlobalLexerBuilder cannot create a lexer from argument of type {type(arg)}",
            offender=(arg, kwargs),
            expect="a TokenSpec or Builder instance",
        )
    
    def resolve(self) -> LexerProtocol[C]:
        if self.lexer is None:
            lexer: LexerProtocol[C] | None = Lexer.create(*self.args, builtin=self.builtin, cache_path=self.cache_path)
            object.__setattr__(self, 'lexer', lexer)
            if self.lexer is None:
                raise SyncraftError(
                    "GlobalLexerBuilder could not create a lexer from the provided builders",
                    offender=(self.args, self.builtin, self.cache_path),
                    expect="at least one valid Builder instance",
                )
            return self.lexer
        else:
            return self.lexer

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GlobalLexerBuilder):
            return False
        return self.args == other.args
        

    def __hash__(self) -> int:
        return hash(frozenset(self.args))
        
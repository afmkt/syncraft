from __future__ import annotations
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import (
    Any, Dict, Set, Optional, TypeVar, Generic, Tuple, Protocol, ClassVar,
    runtime_checkable, Callable, Hashable, Type
)

from syncraft.path import builtin_cache_path, user_cache_path
from syncraft.utils import CallWith
from syncraft.charset import CodeUniverse
from syncraft.fa import DFA, NFA, FABuilder, ReverseDFA, Runner, ModeAction, ModeActionEnum
from syncraft.ast import SyncraftError, Token
from syncraft.cache import Either, Left, Right
from collections import deque, defaultdict
import random
from pathlib import Path
import hashlib
import threading
from syncraft.token import TokenSpec, TokenSpecBase, all_subclasses
import pickle



C = TypeVar('C', bound=str | int | Enum | Any)
A = TypeVar('A')
Ret = TypeVar('Ret', bound=Either[Any, Tuple[Any, Any]])
T = TypeVar('T', bound=Hashable)






Tag = str

@dataclass(frozen=True)
class LexerError:
    message: str
    index: int
    offender: Hashable
    expect: frozenset[Hashable]
    @classmethod
    def message_only(cls, message: str) -> "LexerError":
        return cls(message=message, index=-1, offender=None, expect=frozenset())

@dataclass
class Mode(Generic[C]):
    runner: Runner[C, DFA[C]]
    rdfa: ReverseDFA[C]
    priority: Dict[Tag, int] = field(default_factory=dict)
    skip: frozenset[Tag] = field(default_factory=frozenset)
    non_greedy: frozenset[Tag] = field(default_factory=frozenset)
    start_index: Optional[int] = None

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



@dataclass(frozen=True)
class LexerResult(Generic[C]):
    tag: Tag | None
    start: int
    end: int
    value: Any | None = None


@runtime_checkable
class LexerProtocol(Protocol, Generic[C]):
    def reset(self) -> None: ...

    def match(self, tag: frozenset[Tag | None], char: C, index: int) -> Either[LexerError, None | LexerResult[C]]: ...

    def varify(self, tag: frozenset[Tag | None], value: Any) -> bool: ...

    def tags(self) -> frozenset[str|None]: ...

    def gen(self, tag: Tag | None, rng: random.Random) -> Any: ...

    def candidate(self) -> Either[LexerError, None | LexerResult[C]]: ...
    
    @classmethod
    def create(cls, *args: Any, **kwargs: Any) -> Optional["LexerProtocol[C]"]: ...

    @classmethod
    def bind(cls, *args: Any, **kwargs: Any) -> Type["LexerProtocol[Any]"]:...

    @classmethod
    def from_kwargs(cls, **kwargs: Any) -> Optional["LexerProtocol[C]"]: ...



class LexerBase(LexerProtocol[C]):
    @classmethod
    def normalise_kwargs(cls, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        payload_kind = kwargs.pop("payload_kind", None)
        syn = kwargs.pop("syntax", None)
        if syn and not payload_kind:
            fabuilder: None | FABuilder = None
            for fspec in syn.lexspec:
                for k,v in fspec.kwargs.items():
                    if isinstance(v, FABuilder):
                        fabuilder = v
                        break  
            if fabuilder is None:
                payload_kind = 'token'
            else:
                payload_kind = fabuilder.payload_kind

        if payload_kind in ('text', 'bytes'):
            universe: CodeUniverse[str | bytes] = CodeUniverse.unicode() if payload_kind == 'text' else CodeUniverse.byte()
            return {**kwargs, 'universe': kwargs.pop('universe', universe)}
        elif payload_kind in ('token',):
            tkspec: Optional[TokenSpec[Any]]  = TokenSpecBase.from_kwargs(**kwargs)
            assert tkspec is not None, f"TokenSpec could not be infered from the given parameters {kwargs}."
            return {**kwargs, 'tkspec': kwargs.pop('tkspec', tkspec)}
        else:
            raise SyncraftError(
                "Lexer must be provided with 'payload_kind' or 'syntax' parameter",
                offender=kwargs,
                expect="'payload_kind' or 'syntax' parameter",
            )


    @classmethod
    def from_kwargs(cls, **kwargs: Any) -> Optional["LexerProtocol[C]"]: 
        kwargs = cls.normalise_kwargs(kwargs)
        for sub in all_subclasses(cls):
            c = CallWith(sub.create, **kwargs)
            if c.missing_args or c.missing_kwargs:
                continue
            return c()
        return None

@dataclass
class LexerCache:

    dict: Dict[str, Lexer[Any]] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)

    @staticmethod
    def _load(dir: Path, key: str) -> Optional[Lexer[Any]]:
        file = dir / f"{key}.lex"
        if file.exists():
            with open(file, "rb") as f:
                return pickle.load(f)
        return None
    
    @staticmethod
    def _save(dir: Path, key: str, lexer: Lexer[Any]) -> None:
        dir.mkdir(parents=True, exist_ok=True)
        file = dir / f"{key}.lex"
        with open(file, "wb") as f:
            pickle.dump(lexer, f)

    def load(self, 
             *,
             builders: Set[FABuilder[Any]], 
             factory: Callable[[], Lexer[Any]],
             dir: Path) -> Lexer[Any]:
        tmp = sorted(str(fb) for fb in builders)
        joined = "\n".join(tmp)
        key = hashlib.sha256(joined.encode("utf-8")).hexdigest()
        # print(f"Loading lexer from from {dir} with key {key}")

        with self.lock:
            if key in self.dict:
                return self.dict[key]
            else:
                lexer = self._load(dir, key)
                if lexer is not None:
                    self.dict[key] = lexer
                    return lexer
                lexer = factory()
                if lexer is not None:
                    self.dict[key] = lexer
                    self._save(dir, key, lexer)
                    return lexer
                raise SyncraftError(
                    "Lexer factory did not produce a lexer",
                    offender=factory,
                    expect="a Lexer instance",
                )
            
@dataclass
class Lexer(LexerBase[C]):

    modes: Dict[str | None, Mode[C]]     
    actions: Dict[Tag | None, ModeAction]
    default_mode: str | None 
    _stack: deque[Mode[C]] = field(default_factory=deque)
    cache: ClassVar[LexerCache] = LexerCache()

    
    def tags(self) -> frozenset[str|None]:
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
               *, 
               universe: CodeUniverse, 
               default_mode:str|None=None,
               builtin: bool = False,
               cache_path: str | Path | None = None,
               **kwargs: Any) -> Optional["Lexer[C]"]:
        def fabuilder(**kwargs: Any) -> Tuple[Set[FABuilder[Any]], Path]:
            if builtin:
                path = builtin_cache_path()
            else:
                path = user_cache_path(cache_path)

            acc: Set[FABuilder[Any]] = set()
            for k, v in kwargs.items():
                if isinstance(v, FABuilder):
                    if v.tag is None:
                        acc.add(v.tagged(k))
                    else:
                        acc.add(v)                    
            return acc, path
        
        builders, dir = fabuilder(**kwargs)
        return cls.cache.load(builders=builders, 
                              factory=lambda: cls.from_builders(universe, *builders, default_mode=default_mode),
                              dir=dir)
        
            
    @classmethod
    def bind(cls,*, universe: CodeUniverse[C], default_mode:str|None=None) -> Type["Lexer[Any]"]:
        class BoundLexer(Lexer[Any]):
            @classmethod
            def from_kwargs(cls, **kwargs: Any) -> Optional["Lexer[C]"]:
                return Lexer.create(universe=universe, default_mode=default_mode, **kwargs)
        return BoundLexer


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
    def from_builders(cls, 
                      universe: CodeUniverse[Any], 
                      *rules: FABuilder[C],
                      default_mode: str | None = None) -> "Lexer[C]":
        if len(rules) == 0:
            raise SyncraftError("Cannot build a Lexer with no rules", offender=rules, expect="at least one rule")
        modes: Dict[str | None, Set[FABuilder[C]]] = defaultdict(set)
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
            lexer_modes[mname] = cls.one_mode(universe, *mode_rules)

        lexer = cls(modes=lexer_modes, actions=actions, default_mode=default_mode)
        lexer.push_mode(default_mode)
        return lexer

    def gen(self, tag: Tag | None, rng: random.Random) -> Any:
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

    def candidate(self) -> Either[LexerError, None | LexerResult[C]]:
        mode = self.current_mode
        if mode.start_index is None:
            return Left(LexerError.message_only("Cannot get candidate when no input has been processed"))
        
        candidate_ = mode.runner.candidates
        if not candidate_:
            return Left(LexerError.message_only("No candidate available"))
        latest = candidate_[-1]
        return Right(
            LexerResult(
                tag=mode.select_tag(latest[1]),
                start=mode.start_index,
                end=latest[0] + 1
            )
        )

    def match(self, tags:frozenset[Tag|None], char: C, index: int) -> Either[LexerError, None | LexerResult[C]]:
        mode = self.current_mode
        if mode.start_index is None:
            mode.start_index = index
        rr = mode.runner.step(char, index)
        if rr.error:
            expecting = mode.runner.resumable
            mode.runner = mode.runner.reset()
            return Left(LexerError(
                message="Lexing mismatch",
                index=index,
                offender=char,
                expect=frozenset(str(e) for e in expecting),
            ))

        if rr.final and rr.accepted is None:
            mode.runner = mode.runner.reset()
            return Left(LexerError(
                message=f"Lexing reached final state at index {index} without acceptance",
                index=index,
                offender=char,
                expect=frozenset(),
            ))
        mode.runner = rr.runner
        if rr.final and rr.accepted is not None:
            accepted_pos, accepted_tags = rr.accepted
            tag = mode.select_tag(accepted_tags)
            if tag is None:
                mode.reset()
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
    


@dataclass(frozen=True)
class ExtRule(Generic[T]):
    predicate: Callable[[T], bool]
    generator: Callable[[Any, random.Random], T]

@dataclass
class ExtLexer(LexerBase[T]):
    tkspec: TokenSpec[T]
    rules: Dict[Tag|None, ExtRule[T]] = field(default_factory=dict)

    def reset(self) -> None:
        pass

    def tags(self) -> frozenset[str|None]:
        return frozenset(self.rules.keys())

    @classmethod
    def create(cls, 
               *, 
               tkspec: TokenSpec[T], 
               **kwargs: Any) -> Optional["ExtLexer[T]"]:
        ret = cls(tkspec = tkspec)
        ret.register(**kwargs)
        return ret
    
    @classmethod
    def bind(cls,*, tkspec: TokenSpec[T]) -> Type["ExtLexer[Any]"]:
        class BoundLexer(ExtLexer[Any]):
            @classmethod
            def from_kwargs(cls, **kwargs: Any) -> Optional["ExtLexer[T]"]:
                return ExtLexer.create(tkspec=tkspec, **kwargs)
        return BoundLexer

    
    def clone(self) -> "ExtLexer[T]":
        return replace(self, rules=dict(self.rules))

    def register(
        self,
        **kwargs: Any,
    ) -> None:

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
        

    def candidate(self) -> Either[LexerError, None | LexerResult[T]]:
        return Left(LexerError.message_only("External lexer cannot provide candidates"))

    def match(self, tags: frozenset[Tag|None], item: T, index: int) -> Either[LexerError, None | LexerResult[T]]:
        for tag in tags:
            if tag in self.rules and self.rules[tag].predicate(item):
                return Right(LexerResult(tag=tag, start=index, end=index + 1, value=item))   
                
        return Left(LexerError(
            message="External lexer token mismatch",
            index=index,
            offender=item,
            expect=frozenset(tags)
        ))
        

    def varify(self, tag: frozenset[Tag | None], value: Any) -> bool:
        for t in tag:
            rule = self.rules.get(t)
            if rule is not None:
                if rule.predicate(value):
                    return True
        return False

    def gen(self, tag: Tag | None, rng: random.Random) -> Any:
        rule = self.rules.get(tag)
        if rule is None or rule.generator is None:
            raise SyncraftError(
                f"External lexer cannot generate tokens for tag '{tag}'",
                offender=self,
                expect="generator callable",
            )
        return rule.generator(tag, rng)







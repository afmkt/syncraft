from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any, Dict, Set, Optional, TypeVar, Generic, Tuple, ClassVar,
    Callable, Hashable
)

from syncraft.path import builtin_cache_path, user_cache_path

from syncraft.alphabet import AlphabetProtocol
from syncraft.fa import  NFA, Builder, ReverseDFA, Runner, DFA
from syncraft.ast import SyncraftError
from syncraft.cache import Either

import random
from pathlib import Path
import hashlib
import threading

import pickle
from syncraft.lexerprotocol import LexerProtocol, LexerError, LexerResult, LexerBuilder, GeneratedToken, VerifiedToken, TokenSpecProtocol

    


Tag = str | Enum | None

C = TypeVar('C', bound=Hashable)
A = TypeVar('A')
Ret = TypeVar('Ret', bound=Either[Any, Tuple])
T = TypeVar('T', bound=Hashable)



@dataclass
class Mode(Generic[C]):
    runner: Runner[C]
    rdfa: ReverseDFA[C]
    start_index: Optional[int] = None
    
    def reset(self) -> None:
        self.runner = self.runner.reset()
        self.start_index = None
        
@dataclass(slots=True)
class LexerCache:

    # Use package major.minor version for cache validation - cache invalidates when 
    # major.minor version changes (patch releases are backward compatible)
    
    
    dict: Dict[str, Lexer[Any]] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)

    @staticmethod
    def _load(dir: Path, key: str, signature: str) -> Optional[Lexer[Any]]:
        file = dir / f"{key}.lex"
        if file.exists():
            with open(file, "rb") as f:
                try:
                    data = pickle.load(f)
                    # Validate cache format: expects (version, lexer)
                    if not isinstance(data, tuple) or len(data) != 2:
                        print(f"Invalid cache format in {file}, deleting...")
                        file.unlink()
                        return None
                    version, lexer = data
                    if version != signature:
                        print(f"Cache version mismatch in {file}: got {version}, expected {signature}, deleting...")
                        file.unlink()
                        return None
                    # Additional sanity check: verify the lexer has expected structure
                    if not isinstance(lexer, Lexer):
                        print(f"Invalid lexer type in cache {file}: {type(lexer)}, deleting...")
                        file.unlink()
                        return None
                    return lexer
                except Exception as e:
                    print(e)
                    print("Failed to load lexer from cache:", file)
                    file.unlink()
        return None
    
    @staticmethod
    def _save(dir: Path, key: str, lexer: Lexer[Any], signature: str) -> None:
        dir.mkdir(parents=True, exist_ok=True)
        file = dir / f"{key}.lex"
        tmp_file = file.with_suffix(f".{random.getrandbits(32)}.tmp")
        with open(tmp_file, "wb") as f:
            # Store version alongside lexer for validation on load
            pickle.dump((signature, lexer), f)
        tmp_file.rename(file)

    def load(self, 
             *,
             builders: Set[Builder[Any]], 
             factory: Callable[[], Lexer[Any]],
             dir: Path,
             signatire: str) -> Tuple[Lexer[Any], Path]:
        tmp = sorted(repr(fb) for fb in builders)
        joined = "\n".join(tmp)
        key = hashlib.sha256(joined.encode("utf-8")).hexdigest()

        with self.lock:
            if key in self.dict:
                return self.dict[key], dir / f"{key}.lex"
            else:
                lexer = self._load(dir, key, signature=signatire)
                if lexer is not None:
                    self.dict[key] = lexer
                    return lexer, dir / f"{key}.lex"
                lexer = factory()
                if lexer is not None:
                    self.dict[key] = lexer
                    self._save(dir, key, lexer, signature=signatire)
                    return lexer, dir / f"{key}.lex"
                raise SyncraftError(
                    "Lexer factory did not produce a lexer",
                    offender=factory,
                    expect="a Lexer instance",
                )
            
@dataclass(slots=True)
class Lexer(LexerProtocol[C]):
    _LEXER_SIGNATURE: ClassVar[str | None] = None
    mode : Mode[C]
    cache: ClassVar[LexerCache] = LexerCache()
    filepath: Optional[Path] = field(default=None, compare=False, hash=False, repr=False)

    @staticmethod
    def _summarize_expected(expected: frozenset[Hashable]) -> str:
        if not expected:
            return "valid input"

        items = sorted(str(item) for item in expected)
        if len(items) == 1:
            return f"'{items[0]}'"
        if len(items) <= 10:
            quoted = [f"'{item}'" for item in items]
            return f"one of {', '.join(quoted)}"
        return f"one of {', '.join(items[:5])} ... {len(items)} valid inputs"


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

    @staticmethod
    def signature() -> str:
        if Lexer._LEXER_SIGNATURE is None:
            a: Builder[str] = Builder.lit('a')
            b: Builder[str] = Builder.lit('b')
            c: Builder[str] = Builder.lit('c')
            builder: Builder[str] = ~((a | b) + c).many(at_least=1)
            lexer: Lexer[str] | None = Lexer.from_builders(builder)
            pickle_bytes = pickle.dumps(lexer)
            Lexer._LEXER_SIGNATURE = hashlib.sha256(pickle_bytes).hexdigest()
        return Lexer._LEXER_SIGNATURE

    

    @classmethod
    def create(cls, 
               *args: Builder,
               builtin: bool = False,
               cache_path: str | Path | None = None,
               ) -> Optional[Lexer[C]]:
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
                              dir=dir,
                              signatire=cls.signature())
        lexer.filepath = path
        return lexer

    def reset(self) -> None:
        try:
            self.mode.reset()
        except Exception as e:
            raise SyncraftError(
                f"Failed to reset lexer mode, please clear the lexer cache at `{self.filepath}` and try again.",
                offender=None,
                expect="a valid Mode instance",
            ) from e
    
            

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

        
        
        combined: Optional[NFA[C]] = None 
        for rule in rules:
            nfa = rule.compile(alphabet).nfa
            nfa = nfa.tagged(rule.tag) if rule.tag is not None else nfa
            combined = nfa if combined is None else combined.union(nfa)

        assert combined is not None
        dfa = combined.dfa.normalized.with_default_tag_invariant()
        Lexer._raise_on_unreachable_accept(dfa)
        return Mode(
            runner=dfa.runner(non_greedy=frozenset()),
            rdfa=dfa.reverse,
        )

    @classmethod
    def from_builders(cls, *rules: Builder[C]) -> Lexer[C]:
        if len(rules) == 0:
            raise SyncraftError("Cannot build a Lexer with no rules", offender=rules, expect="at least one rule")
        mode = cls.one_mode(*rules)
        lexer = cls(mode=mode)
        return lexer

    def gen(self, rng: random.Random) -> GeneratedToken:
        ret = self.mode.rdfa.gen(None, rng)
        return GeneratedToken(value=ret, steps=len(ret) if isinstance(ret, (str, bytes, tuple)) else 1)

    def verify(self, value: Any) -> VerifiedToken:
        txt = value
        lexer = self
        try:
            for index, char in enumerate(txt):
                match lexer.match(char, index):  # type: ignore[arg-type]

                    case LexerResult(start=s, end=e):
                        if s != 0 or e != len(txt):
                            return VerifiedToken(False, 0)
                        if index != len(txt) - 1:
                            return VerifiedToken(False, 0)
                        return VerifiedToken(True, len(txt))
                    case None:
                        continue  # Intermediate character, keep going
                    case LexerError():
                        return VerifiedToken(False, 0)
            candidate = lexer.candidate()
            if isinstance(candidate, LexerResult):
                return VerifiedToken(candidate.start == 0 and candidate.end == len(txt), len(txt))
        except TypeError:
            raise SyncraftError(
                f"Value {value} is not valid for verification, expected an eenumerable object like string, bytes, or tuple",
                offender=value,
                expect="an enumerable object",
            )
        return VerifiedToken(False, 0)

    def candidate(self) -> LexerError | LexerResult[C]:
        mode = self.mode
        if mode.start_index is None:
            return LexerError.message_only("Cannot get candidate when no input has been processed")
        
        candidate_ = mode.runner.candidates
        if not candidate_:
            return LexerError.message_only("No candidate available")
        latest = candidate_[-1]
        return LexerResult(
                start=mode.start_index,
                end=latest[0] + 1,
            )
        

    def match(self, char: C, index: int) -> LexerError | None | LexerResult[C]:
        mode = self.mode
        if mode.start_index is None:
            mode.start_index = index
        old_state = mode.runner.current
        rr = mode.runner.step(char, index)
        if rr.error:
            expecting = mode.runner.resumable_str(old_state)
            mode.runner = mode.runner.reset()
            exp = expecting or frozenset()
            expected_str = self._summarize_expected(exp)
            return LexerError(
                message=f"Lexing mismatch '{char}' at index {index}, expected {expected_str}",
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
            mode.runner = mode.runner.reset()
            start = mode.start_index if mode.start_index is not None else accepted_pos
            end = accepted_pos + 1
            mode.start_index = None
            return LexerResult(
                    start=start,
                    end=end,
                )
            
        return None
    



@dataclass(slots=True)
class ExtLexer(LexerProtocol[T]):
    predicate: Callable[[T], bool]
    generator: Callable[[Any, random.Random], GeneratedToken]
    def reset(self) -> None:
        pass

    @classmethod
    def create(cls, tkspec: TokenSpecProtocol) -> Optional[ExtLexer[T]]:
        if isinstance(tkspec, TokenSpecProtocol):
            return cls(predicate=tkspec.predicate, generator=tkspec.generator)
        return None
    
    def candidate(self) -> LexerError | LexerResult[T]:
        return LexerError.message_only("External lexer cannot provide candidates")

    def match(self, item: T, index: int) -> LexerError | None | LexerResult[T]:
        if self.predicate(item):
            return LexerResult(start=index, end=index + 1, value=item)
                
        return LexerError.new(
            message=f"External lexer token mismatch, no tag matched item '{item}'",
            index=index,
            offender=item,
            expect=frozenset()
        )
        

    def verify(self, value: Any) -> VerifiedToken:
        if self.predicate(value):
            return VerifiedToken(True, 1)
        return VerifiedToken(False, 0)

    def gen(self, rng: random.Random) -> GeneratedToken:
        from syncraft.ast import Unknown
        return self.generator(Unknown, rng)





@dataclass(frozen=True, slots=True)
class LocalLexerBuilder(LexerBuilder[C]):
    """Per-terminal lexer builder (Syncraft's default mode).
    Each terminal (`S.re()`, `S.lit()`) gets its own independent lexer.        
    """
    lexer: LexerProtocol[C] | None = field(default=None, compare=False, hash=False, repr=False)
    def __call__(self, arg: TokenSpecProtocol | Builder, **kwargs: Any) -> LocalLexerBuilder[C]:
        if isinstance(arg, TokenSpecProtocol):
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
    


from __future__ import annotations

import random
from typing import Any, Callable, Iterable, TypeVar, Hashable, Protocol, runtime_checkable, Dict, Tuple, Optional, Type, Set
import re
from enum import Enum
from syncraft.ast import Token
from syncraft.utils import CallWith
from dataclasses import dataclass, field, fields, is_dataclass
import rstr




Tag = str

T = TypeVar('T', bound=Hashable)
TokenT = TypeVar('TokenT', bound=Hashable)
ScalarValueT = TypeVar('ScalarValueT', bound=Hashable)


def all_subclasses(cls: Type[Any])->Set[Type[Any]]:
    """Recursively find all subclasses of a given class."""
    result = set(cls.__subclasses__())
    for subclass in cls.__subclasses__():
        result.update(all_subclasses(subclass))
    return result

@runtime_checkable
class TokenSpec(Protocol[T]):
    def tags(self, **kwargs: Any) -> frozenset[Tag]: ...
    def predicate(self, **kwargs: Any) -> Callable[[T], bool]: ...
    def generator(self, **kwargs: Any) -> Callable[[Any, random.Random], T]: ...
    @classmethod
    def create(cls, *args: Any, **kwargs: Any) -> TokenSpec[T]: ...


class TokenSpecBase(TokenSpec[T]):


    @classmethod
    def from_kwargs(cls, *args: Any, **kwargs: Any) -> Optional["TokenSpec[T]"]: 
        all = all_subclasses(cls)
        assert all, "No subclasses of TokenSpecBase found. Please import token modules to register TokenSpec subclasses."
        for sub in all_subclasses(cls):
            c = CallWith(sub.create, *args, **kwargs)
            if c.missing_args or c.missing_kwargs:
                continue
            return c()
        return None
    
    def _config_defaults(self) -> Dict[str, Any]:
        if not is_dataclass(self):
            return {}
        return {
            f.name: getattr(self, f.name)
            for f in fields(self)
            if f.metadata.get("is_config", False)
        }

    def _extract_config_kwargs(
        self, kwargs: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        defaults = self._config_defaults()
        config = {k: kwargs[k] for k in defaults if k in kwargs}
        params = {k: v for k, v in kwargs.items() if k not in defaults}
        return defaults | config, params

    def _resolve_tag_kwargs(
        self, params: Dict[str, Any]
    ) -> Tuple[frozenset[Tag], Dict[str, Any]]:
        remaining = dict(params)
        tags: frozenset[Tag] = frozenset()
        tag_callable = getattr(self, "tag", None)
        if callable(tag_callable):
            tags = tag_callable(**remaining)  # type: ignore[misc]
        if not tags and "tag" in remaining:
            raw = remaining.pop("tag")
            if isinstance(raw, (set, frozenset)):
                tags = frozenset(raw)
            else:
                tags = frozenset([raw])
        return tags, remaining

    def normalise_kwargs(
        self, kwargs: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any], frozenset[Tag]]:
        config, params = self._extract_config_kwargs(kwargs)
        tags, params = self._resolve_tag_kwargs(params)
        return config, params, tags

@dataclass(frozen=True)
class TokenMatcher(TokenSpecBase[T]):
    pred: Callable[[T], bool]
    gen: Callable[[Any, random.Random], T]
    tag: None | Callable[..., frozenset[Tag]] = field(default=None)

    @classmethod
    def create(cls,
               *,
                pred: Callable[[T], bool],
                gen: Callable[[Any, random.Random], T],
                tag: None | Tag | Iterable[Tag] | Callable[..., frozenset[Tag]] = None)-> TokenMatcher[T]:
        tag_callable = tag if callable(tag) else lambda **_: frozenset([tag]) if isinstance(tag, (str, Enum)) else frozenset(tag if tag is not None else [])
        return cls(pred=pred, gen=gen, tag=tag_callable)
        
               
    def tags(self, **kwargs: Any) -> frozenset[Tag]:
        _, _, tags = self.normalise_kwargs(dict(kwargs))
        return tags

    def predicate(self, **kwargs: Any) -> Callable[[T], bool]:
        self.normalise_kwargs(dict(kwargs))
        return self.pred

    def generator(self, **kwargs: Any) -> Callable[[Any, random.Random], T]:
        self.normalise_kwargs(dict(kwargs))
        return self.gen

@dataclass(frozen=True)
class Scalar(TokenSpecBase[T]):
    constructor: Callable[..., T]
    pattern: re.Pattern = field(default=re.compile(".*"), metadata={"is_config": True})

    @classmethod
    def create(cls,
                *,
                pattern: str | re.Pattern[str],
                
                constructor: Callable[..., T] = str, # type: ignore
                flags: int | None = None) -> Scalar[T]:
        compiled = re.compile(pattern, flags or 0) if isinstance(pattern, str) else pattern
        return cls(constructor=constructor, pattern=compiled)
        

    def tags(self, **kwargs: Any) -> frozenset[Tag]:
        config, params, tags = self.normalise_kwargs(dict(kwargs))
        if tags:
            return tags
        pattern = params.get("pattern", config.get("pattern", self.pattern))
        if isinstance(pattern, re.Pattern):
            return frozenset([pattern.pattern])
        return frozenset()

    def predicate(self, **kwargs: Any) -> Callable[[T], bool]:
        config, params, _ = self.normalise_kwargs(dict(kwargs))
        pattern = params.get("pattern", config.get("pattern", self.pattern))
        assert isinstance(pattern, re.Pattern)
        def pred(token: T) -> bool:
            return re.fullmatch(pattern, str(token)) is not None
        pred.__name__ = f"P(/{pattern.pattern}/)"
        return pred

    def generator(self, **kwargs: Any) -> Callable[[Any, random.Random], T]:
        config, params, _ = self.normalise_kwargs(dict(kwargs))
        pattern = params.get("pattern", config.get("pattern", self.pattern))
        assert isinstance(pattern, re.Pattern)
        def gen(input: Any, rnd: random.Random) -> T:
            return self.constructor(rstr.xeger(pattern))
        gen.__name__ = f"G(/{pattern.pattern}/)"
        return gen


@dataclass(frozen=True)
class Structured(TokenSpecBase[T]):
    constructor: Callable[..., T]
    case_sensitive: bool = field(default=True, metadata={"is_config": True})
    strict: bool = field(default=False, metadata={"is_config": True})
    tag: None | Callable[..., frozenset[Tag]] = field(default=None)
    
    @classmethod
    def create(cls, 
               *,
               constructor: Callable[..., T] = Token, # type: ignore
               case_sensitive: bool = True,
               strict: bool = False,
               tag: Tag | Iterable[Tag] | None | Callable[..., frozenset[Tag]] = None) -> Structured[T]:
        tag_callable = tag if callable(tag) else lambda **_: frozenset([tag]) if isinstance(tag, (str, Enum)) else frozenset(tag if tag is not None else [])
        return cls(
            constructor=constructor,
            case_sensitive=case_sensitive,
            strict=strict,
            tag=tag_callable,
        )
        

    def tags(self, **kwargs: Any) -> frozenset[Tag]:
        config, kwargs, tags = self.normalise_kwargs(dict(kwargs))
        if tags:
            return tags
        if 'token_type' in kwargs:
            return frozenset([kwargs['token_type']])
        if 'text' in kwargs:
            return frozenset([kwargs['text']])
        return frozenset()
    
    def describe(self, **kwargs: Any) -> str:
        c = CallWith(self.constructor, **kwargs)
        parts = []
        for k, v in c.kwargs.items():
            if isinstance(v, re.Pattern):
                parts.append(f"{k}=/{v.pattern}/")
            else:
                parts.append(f"{k}={v}")
        for x in c.args:
            parts.append(str(x))
        return ", ".join(parts)

    def predicate(self, **kwargs: Any) -> Callable[[T], bool]:
        config, kwargs, _ = self.normalise_kwargs(dict(kwargs))
        case_sensitive = config.get('case_sensitive', True)
        strict = config.get('strict', False)
        def pred(token: T) -> bool:
            for key, pattern in kwargs.items():
                if not hasattr(token, key):
                    if strict:
                        return False
                else:
                    data = getattr(token, key)
                    if isinstance(pattern, re.Pattern):
                        if pattern.fullmatch(str(data)) is None:
                            return False
                        else:
                            continue
                    elif isinstance(pattern, str):
                        if strict:
                            if case_sensitive:
                                if str(data) != pattern:
                                    return False
                            else:
                                if str(data).upper() != pattern.upper():
                                    return False
                        else:
                            if case_sensitive:
                                if str(data).strip() != pattern.strip():
                                    return False
                            else:
                                if str(data).strip().upper() != pattern.strip().upper():
                                    return False
                    elif pattern != data:
                        return False
            return True
        pred.__name__ = f"P({self.describe(**kwargs)})"
        return pred

    def generator(self, **kwargs: Any) -> Callable[[Any, random.Random], T]:
        config, kwargs, _ = self.normalise_kwargs(dict(kwargs))
        def gen(input: Any, rnd: random.Random) -> T:
            data = {}
            for k, v in kwargs.items():
                if isinstance(v, re.Pattern):
                    try:
                        data[k] = rstr.xeger(v)
                    except Exception:
                        data[k] = v.pattern
                else:
                    data[k] = v
            return CallWith(self.constructor, **data)()
        gen.__name__ = f"G({self.describe(**kwargs)})"
        return gen



def matcher(
    *,
    pred: Callable[[TokenT], bool],
    gen: Callable[[Any, random.Random], TokenT],
    tag: None | Tag | Iterable[Tag] | Callable[..., frozenset[Tag]] = None,
) -> TokenMatcher[TokenT]:
    return TokenMatcher.create(pred=pred, gen=gen, tag=tag)


def scalar(
    pattern: str | re.Pattern[str],
    *,
    constructor: Callable[..., ScalarValueT] = str, # type: ignore
    flags: int | None = None,
) -> Scalar[ScalarValueT]:
    return Scalar.create(pattern=pattern, constructor=constructor, flags=flags)


def struct(
    constructor: Callable[..., TokenT],
    *,
    case_sensitive: bool = True,
    strict: bool = False,
    tag: Tag | Iterable[Tag] | None | Callable[..., frozenset[Tag]] = None
) -> Structured[TokenT]:
    return Structured.create(
        constructor=constructor,
        case_sensitive=case_sensitive,
        strict=strict,
        tag=tag,
    )



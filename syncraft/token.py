from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any, Callable, Dict, Tuple, TypeVar, Hashable, Union
import re
from enum import Enum
from syncraft.utils import CallWith
from syncraft.lexer import TokenSpec
from dataclasses import field, fields
import rstr

Tag = Union[str, Enum]

T = TypeVar('T', bound=Hashable)
@dataclass(frozen=True)
class TokenMatcher(TokenSpec[T]):
    pred: Callable[[T], bool]
    gen: Callable[[Any, random.Random], T]
    tag: Callable[..., frozenset[Tag]] = field(default=lambda **kwargs: frozenset())

    def tags(self, **kwargs: Any) -> frozenset[Tag]:
        return self.tag(**kwargs)

    def predicate(self, **kwargs: Any) -> Callable[[T], bool]:
        return self.pred

    def generator(self, **kwargs: Any) -> Callable[[Any, random.Random], T]:
        return self.gen

@dataclass(frozen=True)
class Scalar(TokenSpec[T]):
    constructor: Callable[..., T]
    pattern: re.Pattern = field(default=re.compile(".*"), metadata={"is_config": True})

    def tags(self, **kwargs: Any) -> frozenset[Tag]:
        return frozenset([self.pattern.pattern])

    def predicate(self, **kwargs: Any) -> Callable[[T], bool]:
        def pred(token: T) -> bool:
            return re.fullmatch(self.pattern, str(token)) is not None
        pred.__name__ = f"P(/{self.pattern}/)"
        return pred

    def generator(self, **kwargs: Any) -> Callable[[Any, random.Random], T]:
        def gen(input: Any, rnd: random.Random) -> T:
            return self.constructor(rstr.xeger(self.pattern))
        gen.__name__ = f"G(/{self.pattern}/)"
        return gen


@dataclass(frozen=True)
class Structured(TokenSpec[T]):
    constructor: Callable[..., T]
    case_sensitive: bool = field(default=True, metadata={"is_config": True})
    strict: bool = field(default=False, metadata={"is_config": True})
    tag: None | Callable[..., frozenset[Tag]] = field(default=None)

    def tags(self, **kwargs: Any) -> frozenset[Tag]:
        config, kwargs = self.extract_config(kwargs)
        if self.tag:
            return self.tag(**kwargs)
        elif 'tag' in kwargs:
            return frozenset([kwargs['tag']])
        elif 'token_type' in kwargs:
            return frozenset([kwargs['token_type']])
        elif 'text' in kwargs:
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

    def extract_config(self, kwargs: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        default_config = {f.name: getattr(self, f.name) for f in fields(self) if f.metadata.get("is_config", False)}
        c = CallWith(self.constructor, **kwargs)
        config = {k: v for k, v in kwargs.items() if k in c.unused_kwargs}
        params = {k: v for k, v in kwargs.items() if k not in c.unused_kwargs}
        return default_config | config, params

    def predicate(self, **kwargs: Any) -> Callable[[T], bool]:
        config, kwargs = self.extract_config(kwargs)
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
        config, kwargs = self.extract_config(kwargs)
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



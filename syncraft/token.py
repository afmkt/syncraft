from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any, Callable, Dict, Tuple, TypeVar, Hashable
import re
from syncraft.utils import CallWith
from syncraft.lexer import TokenProtocol
from dataclasses import field, fields
import rstr

T = TypeVar('T', bound=Hashable)
@dataclass(frozen=True)
class TokenMatcher(TokenProtocol[T]):
    pred: Callable[[T], bool]
    gen: Callable[[Any, random.Random], T]

    def predicate(self, **kwargs: Any) -> Callable[[T], bool]:
        return self.pred

    def generator(self, **kwargs: Any) -> Callable[[Any, random.Random], T]:
        return self.gen

@dataclass(frozen=True)
class Scalar(TokenProtocol[T]):
    constructor: Callable[..., T]
    pattern: re.Pattern = field(default=re.compile(".*"), metadata={"is_config": True})

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
class Structured(TokenProtocol[T]):
    constructor: Callable[..., T]
    case_sensitive: bool = field(default=False, metadata={"is_config": True})
    strict: bool = field(default=False, metadata={"is_config": True})

    
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
        c = CallWith(self.constructor)
        config = {k: v for k, v in kwargs.items() if k in c.missing_keyword_params}
        params = {k: v for k, v in kwargs.items() if k not in c.missing_keyword_params}
        return default_config | config, params

    def predicate(self, **kwargs: Any) -> Callable[[T], bool]:
        config, kwargs = self.extract_config(kwargs)
        case_sensitive = config.get('case_sensitive', False)
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

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import random
from typing import Any, Callable, Dict, Mapping, Tuple, cast, TypeVar, Hashable, List
import re
from syncraft.utils import CallWith
from syncraft.lexer import TokenProtocol
from dataclasses import field, fields
from syncraft.ast import SyncraftError
from syncraft.constraint import FrozenDict

Tag = str | Enum
TOKEN_SPEC_KEY = "__token_spec__"
LEGACY_TOKEN_KEYS: frozenset[str] = frozenset({
    "token_type",
    "text",
    "case_sensitive",
    "strict",
})


@dataclass(frozen=True)
class TokenSpecEntry:
    predicate: Callable[[Any], bool] | None = None
    generator: Callable[[Any, random.Random], Any] | None = None
    params: FrozenDict[str, Any] | None = None

    def with_params(self, updates: Mapping[str, Any]) -> "TokenSpecEntry":
        current = self.params or FrozenDict()
        merged = dict(current)
        merged.update(updates)
        return TokenSpecEntry(
            predicate=self.predicate,
            generator=self.generator,
            params=FrozenDict(merged),
        )


TokenSpecMap = FrozenDict[Tag, TokenSpecEntry]


def _coerce_mapping(value: Mapping[str, Any]) -> FrozenDict[str, Any]:
    if not all(isinstance(k, str) for k in value.keys()):
        raise SyncraftError(
            "Token mapping keys must be strings", offender=value, expect="Mapping[str, Any]"
        )
    return FrozenDict(dict(value))


def coerce_token_spec(tag: Tag, value: Any) -> TokenSpecEntry:
    if isinstance(value, tuple):
        if len(value) != 2:
            raise SyncraftError(
                f"Token spec for '{tag}' must be a (predicate, generator) pair",
                offender=value,
                expect="(predicate, generator)",
            )
        predicate, generator = value
        if predicate is not None and not callable(predicate):
            raise SyncraftError(
                f"Predicate for '{tag}' must be callable or None",
                offender=predicate,
                expect="callable",
            )
        if generator is not None and not callable(generator):
            raise SyncraftError(
                f"Generator for '{tag}' must be callable or None",
                offender=generator,
                expect="callable",
            )
        pred_callable = cast(Callable[[Any], bool] | None, predicate)
        gen_callable = cast(Callable[[Any, random.Random], Any] | None, generator)
        return TokenSpecEntry(predicate=pred_callable, generator=gen_callable)

    if isinstance(value, Mapping):
        return TokenSpecEntry(params=_coerce_mapping(value))

    raise SyncraftError(
        f"Token spec for '{tag}' must be a mapping or (predicate, generator)",
        offender=value,
        expect="mapping or (predicate, generator)",
    )


def split_token_kwargs(kwargs: Mapping[Any, Any]) -> Tuple[TokenSpecMap, Dict[Any, Any]]:
    token_specs: Dict[Tag, TokenSpecEntry] = {}
    legacy_kwargs: Dict[Any, Any] = {}

    for key, value in kwargs.items():
        if isinstance(key, (str, Enum)) and key not in LEGACY_TOKEN_KEYS:
            if isinstance(value, tuple) or isinstance(value, Mapping):
                token_specs[key] = coerce_token_spec(key, value)
                continue
        legacy_kwargs[key] = value

    return FrozenDict(token_specs), legacy_kwargs


T = TypeVar('T', bound=Hashable)


@dataclass(frozen=True)
class Structured(TokenProtocol[T]):
    TokenConstructor: Callable[..., T]
    case_sensitive: bool = field(default=False, metadata={"is_config": True})
    strict: bool = field(default=False, metadata={"is_config": True})

    
    def describe(self, **kwargs: Any) -> str:
        c = CallWith(self.TokenConstructor, **kwargs)
        parts = []
        for k, v in c.kwargs.items():
            if isinstance(v, re.Pattern):
                parts.append(f"{k}=/{v.pattern}/")
            else:
                parts.append(f"{k}={v}")
        for x in c.args:
            parts.append(str(x))
        return "(" + ", ".join(parts) + ")"

    def extract_config(self, kwargs: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        default_config = {f.name: getattr(self, f.name) for f in fields(self) if f.metadata.get("is_config", False)}
        c = CallWith(self.TokenConstructor)
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
        pred.__name__ = f"P{self.describe(**kwargs)}"
        return pred

    def generator(self, **kwargs: Any) -> Callable[[Any, random.Random], T]:
        config, kwargs = self.extract_config(kwargs)
        def gen(input: Any, rnd: random.Random) -> T:
            data = {}
            for k, v in kwargs.items():
                if isinstance(v, re.Pattern):
                    import rstr
                    try:
                        data[k] = rstr.xeger(v)
                    except Exception:
                        data[k] = v.pattern
                else:
                    data[k] = v
            return CallWith(self.TokenConstructor, **data)()
        gen.__name__ = f"G{self.describe(**kwargs)}"
        return gen

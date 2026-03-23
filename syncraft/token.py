from __future__ import annotations

import random
from typing import Any, Callable
import re
from dataclasses import is_dataclass, fields, dataclass
from enum import Enum
from syncraft.lexerprotocol import GeneratedToken, TokenSpecProtocol

from syncraft.bimap import is_primitive, DataError


class Str(TokenSpecProtocol):
    def __init__(self, 
                 pattern: str | re.Pattern,
                 *,
                 i: bool = False,
                 fullmatch: bool = True):
        from syncraft.regex import rstr, match        
        self.case_insensitive = i
        self.fullmatch = fullmatch
        self.pattern = pattern
        if isinstance(pattern, re.Pattern):
            self.matcher = match(pattern, case_insensitive=i, fullmatch=fullmatch)
            self.gen = rstr(pattern, case_insensitive=i)
        else:
            def match_fn(token: str) -> bool:
                if i:
                    token = token.lower()
                    pat = pattern.lower()
                else:
                    pat = pattern
                if fullmatch:
                    return token == pat
                else:
                    return token.startswith(pat)
            self.matcher = match_fn
            self.gen = lambda rnd: pattern
        def predicate(token: Any) -> bool:
            return isinstance(token, str) and self.matcher(token)
        def generator(input: Any, rnd: random.Random) -> GeneratedToken:
            if isinstance(input, str) and self.matcher(input):
                return GeneratedToken(value=input, steps=1)
            else:
                return GeneratedToken(value=self.gen(rnd), steps=1)
        self.predicate = predicate
        self.generator = generator
    def __repr__(self) -> str:
        return f"Str(pattern={self.pattern!r}, i={self.case_insensitive}, fullmatch={self.fullmatch})"
        
    def __str__(self) -> str:
        return f"{self.pattern!r}"

class TokenSpec(TokenSpecProtocol):
    def __init__(self, predicate: Callable[[Any], bool], generator: Callable[[Any, random.Random], GeneratedToken]):
        self.predicate = predicate
        self.generator = generator

    @classmethod
    def from_any(cls, spec: Any) -> TokenSpecProtocol:
        from syncraft.ast import Unknown
        if isinstance(spec, str) or isinstance(spec, re.Pattern):
            return Str(spec)
        elif isinstance(spec, TokenSpecProtocol):
            return spec
        elif is_primitive(spec):
            def predicate(token: Any) -> bool:
                return token == spec
            def generator(input: Any, rnd: random.Random) -> GeneratedToken:                    
                return GeneratedToken(value=spec, steps=1)
            return cls(predicate=predicate, generator=generator)
        elif isinstance(spec, dict):
            result = {}
            for k, v in spec.items():                    
                result[k] = TokenSpec.from_any(v)                
            def predicate(token: Any) -> bool:
                if not isinstance(token, dict):
                    return False
                for k, v in result.items():
                    t = token.get(k, ...)
                    if t is ... or not v.predicate(t):
                        return False
                return True
            def generator(input: Any, rnd: random.Random) -> GeneratedToken:
                generated = {}
                if isinstance(input, dict):
                    for k, v in result.items():
                        generated[k] = v.generator(input.get(k, ...), rnd).value
                    return GeneratedToken(value=generated, steps=1)
                elif input is ... or input is Unknown:
                    for k, v in result.items():
                        generated[k] = v.generator(..., rnd).value
                    return GeneratedToken(value=generated, steps=1)
                else:
                    raise DataError(f"Invalid input for token generation: {input}")
            return cls(predicate=predicate, generator=generator)
        elif isinstance(spec, (list, tuple)):
            lst = []
            for item in spec:
                v = TokenSpec.from_any(item)
                lst.append(v)
            def predicate(token: Any) -> bool:
                if not isinstance(token, type(spec)) or len(token) != len(lst):
                    return False
                return all(v.predicate(t) for v, t in zip(lst, token))
            
            def generator(input: Any, rnd: random.Random) -> GeneratedToken:
                if isinstance(input, (list, tuple)):
                    generated = []
                    for v, i in zip(lst, input):
                        generated.append(v.generator(i, rnd).value)
                    return GeneratedToken(value=type(spec)(generated), steps=1)
                elif input is ... or input is Unknown:
                    generated = []
                    for v in lst:
                        generated.append(v.generator(..., rnd).value)
                    return GeneratedToken(value=type(spec)(generated), steps=1)
                else:
                    raise DataError(f"Invalid input for token generation: {input}")
            return cls(predicate=predicate, generator=generator)

        elif is_dataclass(spec):
            all_fields = {}
            for field in fields(spec):
                value = getattr(spec, field.name)
                all_fields[field.name] = TokenSpec.from_any(value)

            def predicate(token: Any) -> bool:
                if not isinstance(token, type(spec)):
                    return False
                for field_name, token_spec in all_fields.items():
                    value = getattr(token, field_name, ...)
                    if value is ... or not token_spec.predicate(value):
                        return False
                return True
            def generator(input: Any, rnd: random.Random) -> GeneratedToken:
                generated_fields = {}
                if isinstance(input, type(spec)):
                    for field_name, token_spec in all_fields.items():
                        value = getattr(input, field_name, ...)
                        generated_fields[field_name] = token_spec.generator(value, rnd).value
                    return GeneratedToken(value=type(spec)(**generated_fields), steps=1) # type: ignore
                elif input is ... or input is Unknown:
                    for field_name, token_spec in all_fields.items():
                        generated_fields[field_name] = token_spec.generator(..., rnd).value
                    return GeneratedToken(value=type(spec)(**generated_fields), steps=1) # type: ignore 
                else:
                    raise DataError(f"Invalid input for token generation: {input}")
            return cls(predicate=predicate, generator=generator)

        raise DataError(f"Invalid token specification: {spec}")
            


@dataclass(frozen=True, slots=True)
class Token:
    """
    A typical structureal terminal token
    """
    text: str | Any
    token_type: str |  Enum | None = None   

    def to_str(self) -> str:
        if isinstance(self.text, str):
            return self.text.strip()
        elif isinstance(self.text, bytes):
            return self.text.decode('utf-8', errors='replace').strip()
        elif isinstance(self.text, tuple):
            return ''.join(str(c) for c in self.text).strip()
        else:
            return str(self.text).strip()
            

    def __repr__(self) -> str:        
        if self.token_type is None:
            return f"Token(text={self.to_str()!r})"
        else:
            return f"Token(text={self.to_str()!r}, token_type={self.token_type!r})"

    def __str__(self) -> str:
        if self.token_type is None:
            return f"t.{self.to_str().strip()}"        
        else:            
            return f"t.({self.to_str().strip()}, {self.token_type})"

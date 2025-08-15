from __future__ import annotations
import re
from sqlglot import tokenize, TokenType, Parser as GlotParser, exp
from typing import (
    Optional, List, Any, TypeVar, Tuple, runtime_checkable, Dict,
    Protocol, Generic, Callable, Union
)
from syncraft.algebra import (
    Either, Left, Right, Error, Insptectable, Algebra, NamedResult, OrResult,ThenResult, ManyResult, ThenKind,
    Lens
)
from dataclasses import dataclass, field, replace, is_dataclass, asdict
from enum import Enum
from functools import reduce, cached_property
from syncraft.dsl import DSL






@runtime_checkable
class TokenProtocol(Protocol):
    @property
    def token_type(self) -> TokenType: ...
    @property
    def text(self) -> str: ...
    

@dataclass(frozen=True)
class Token:
    token_type: TokenType
    text: str
    def __str__(self) -> str:
        return f"{self.token_type.name}({self.text})"
    
    def __repr__(self) -> str:
        return self.__str__()

@dataclass(frozen=True)
class TokenSpec:
    token_type: Optional[TokenType] = None
    text: Optional[str] = None
    case_sensitive: bool = False
    regex: Optional[re.Pattern[str]] = None
        
    def is_valid(self, token: TokenProtocol) -> bool:
        type_match = self.token_type is None or token.token_type == self.token_type
        value_match = self.text is None or (token.text.strip() == self.text.strip() if self.case_sensitive else 
                                                    token.text.strip().upper() == self.text.strip().upper())
        value_match = value_match or (self.regex is not None and self.regex.fullmatch(token.text) is not None)
        return type_match and value_match




T = TypeVar('T', bound=TokenProtocol)  


ParseResult = Union[
    ThenResult['ParseResult[T]', 'ParseResult[T]'], 
    NamedResult['ParseResult[T]', Any], 
    ManyResult['ParseResult[T]'],
    OrResult['ParseResult[T]'],
    Tuple[T, ...],
    T,
] 



@dataclass(frozen=True)
class Crumb(Generic[T]):
    entrance: str
    id: int = field(init=False)
    def __post_init__(self)-> None:
        object.__setattr__(self, 'id', id(self))

    

@dataclass(frozen=True)
class LeftCrumb(Crumb[T]):
    right: ParseResult[T]
    kind: ThenKind
    

@dataclass(frozen=True)
class OrCrumb(Crumb[T]):
    pass
@dataclass(frozen=True)
class RightCrumb(Crumb[T]):
    left: ParseResult[T]
    kind: ThenKind
    
    
@dataclass(frozen=True)
class NamedCrumb(Crumb[T]):
    name: str
    forward_map: Callable[[Any], Any] | None
    backward_map: Callable[[Any], Any] | None
    aggregator: Callable[..., Any] | None

    
@dataclass(frozen=True)
class ManyCrumb(Crumb[T]):
    before: Tuple[ParseResult[T], ...]
    after: Tuple[ParseResult[T], ...]


@dataclass(frozen=True)
class NamedRecord:
    lens: Lens[Any, Any]
    value: Any

@dataclass(frozen=True)
class Walker:
    lens: Optional[Lens[Any, Any]] = None
    def get(self, root: ParseResult[Any]) -> Dict[str, NamedRecord]:
        match root:
            case ManyResult(value=children):
                new_named: Dict[str, NamedRecord] = {}
                for i, child in enumerate(children):
                    new_walker = replace(self, lens=(self.lens / ManyResult.lens(i)) if self.lens else ManyResult.lens(i))
                    new_named |= new_walker.get(child)
                return new_named
            case OrResult(value=value):
                new_walker = replace(self, lens=(self.lens / OrResult.lens()) if self.lens else OrResult.lens())
                return new_walker.get(value)
            case ThenResult(left=left, 
                            right=right, 
                            kind=kind):
                new_walker = replace(self, lens=(self.lens / ThenResult.lens(kind)) if self.lens else ThenResult.lens(kind))
                return new_walker.get(left) | new_walker.get(right)
            case NamedResult(name=name, 
                             value=value, 
                             forward_map=forward_map,
                             backward_map=backward_map,
                             aggregator=aggregator):
                this_lens = (self.lens / NamedResult.lens()) if self.lens else NamedResult.lens()
                if callable(forward_map) and callable(backward_map):
                    this_lens = this_lens.bimap(forward_map, backward_map) 
                elif callable(forward_map):
                    this_lens = this_lens.bimap(forward_map, lambda _: value)
                elif callable(backward_map):
                    raise ValueError("backward_map provided without forward_map")
                new_walker = replace(self, lens=this_lens)
                child_named = new_walker.get(value)
                if aggregator is not None:
                    return child_named | {name: NamedRecord(lens=this_lens, 
                                                            value=aggregator(child_named))}
                else:
                    return child_named
        return {}

    def set(self, root: ParseResult[Any], updated_values: Dict[str, Any]) -> ParseResult[Any]:
        named_records = self.get(root)
        def apply_update(name: str, value: Any, root: ParseResult[Any]) -> ParseResult[Any]:
            if name not in named_records:
                # Skip unknown names safely
                return root
            record = named_records[name]
            target_named: NamedResult[Any, Any] = record.lens.get(root)
            assert isinstance(target_named, NamedResult)

            if target_named.aggregator is not None:
                # Break apart dataclass/dict into child fields
                if isinstance(value, dict):
                    child_updates = value
                elif is_dataclass(value) and not isinstance(value, type):
                    child_updates = asdict(value)
                else:
                    raise TypeError(f"Unsupported aggregator value for '{name}': {type(value)}")

                # Recursively apply each child update
                for child_name, child_value in child_updates.items():
                    root = apply_update(child_name, child_value, root)
                return root

            else:
                # Leaf: just replace the value
                updated_named = replace(target_named, value=value)
                return record.lens.set(root, updated_named)

        for name, value in updated_values.items():
            root = apply_update(name, value, root)

        return root

@dataclass(frozen=True)
class AST(Generic[T]):
    focus: ParseResult[T]
    breadcrumbs: Tuple[Crumb[T], ...] = field(default_factory=tuple)
    closed: frozenset[Crumb[T]] = field(default_factory=frozenset)

    @cached_property
    def is_pruned(self) -> bool:
        for crumb in self.breadcrumbs:
            match crumb:
                case LeftCrumb(kind=ThenKind.RIGHT):
                    return True  # you're in a left child of a then_right
                case RightCrumb(kind=ThenKind.LEFT):
                    return True  # you're in a right child of a then_left
        return False


    def up(self) -> Optional[AST[T]]:
        if not self.breadcrumbs:
            return None
        *rest, last = self.breadcrumbs

        match last:
            case LeftCrumb(right=right, kind=kind):
                parent: ParseResult[T] = ThenResult(kind=kind, left=self.focus, right=right)
            case RightCrumb(left=left, kind=kind):
                parent = ThenResult(kind=kind, left=left, right=self.focus)
            case NamedCrumb(name=name, forward_map=forward_map, backward_map=backward_map, aggregator=aggregator):
                parent = NamedResult(name=name, value=self.focus, forward_map=forward_map, backward_map=backward_map, aggregator=aggregator)
            case ManyCrumb(before=before, after=after):
                parent = ManyResult(value=before + (self.focus,) + after)
            case OrCrumb():
                parent = OrResult(value=self.focus)
            case _:
                raise ValueError(f"Unexpected crumb type: {last}")
        return AST(focus=parent, breadcrumbs=tuple(rest), closed=frozenset(self.closed | {last}))

    def down_left(self) -> Optional[AST[T]]:
        match self.focus:
            case ThenResult(left=left, right=_, kind=kind):
                return AST(focus=left, 
                           breadcrumbs=self.breadcrumbs + (LeftCrumb("\u2199", right=self.focus.right, kind=kind),), 
                           closed=self.closed)
            case NamedResult(name=name, 
                             value=inner, 

                             forward_map=forward_map, 
                             backward_map=backward_map,
                             aggregator=aggregator):
                return AST(focus=inner, 
                           breadcrumbs=self.breadcrumbs + (NamedCrumb("\u2199", 
                                                                      name=name, 

                                                                      forward_map=forward_map, 
                                                                      backward_map=backward_map, 
                                                                      aggregator=aggregator),),
                           closed=self.closed)
            case ManyResult(value=()):
                return None
            case ManyResult(value=(head, *tail)):
                return AST(focus=head, 
                           breadcrumbs=self.breadcrumbs + (ManyCrumb("\u2199", before=(), after=tuple(tail)),),
                           closed=self.closed)
            case OrResult(value=value):
                return AST(focus=value, 
                           breadcrumbs=self.breadcrumbs + (OrCrumb("\u2199"),),
                           closed=self.closed)
            case _:
                return None        




    def right(self) -> Optional[AST[T]]:
        if not self.breadcrumbs:
            return None
        *rest, last = self.breadcrumbs
        match last:
            case ManyCrumb(before=before, after=(next_, *after)):
                # If inside a ManyResult, and there are elements in after, return the next sibling and update before to include current focus
                new_last = ManyCrumb("\u2192", before=before + (self.focus,), after=tuple(after))
                return AST(focus=next_, 
                           breadcrumbs=tuple(rest) + (new_last,),
                           # don't add the ManyCrumb(last) to closed, because we only close one of its children
                           # and the whole ManyCrumb can not be considered closed
                           # so we only add the current focus to closed if it is a Crumb.
                           # if the client code hold MnayCrumb(last) as a scope, it should check 
                           # if the scope is in closed, and update the scope to the new ManyCrumb
                           closed=frozenset(self.closed | {self.focus}) if isinstance(self.focus, Crumb) else frozenset(self.closed)
                        )
            case LeftCrumb(right=right, kind=kind):
                return AST(focus=right, 
                           breadcrumbs=tuple(rest) + (RightCrumb("\u2192", self.focus, kind),),
                           closed=frozenset(self.closed | {last}))
            case _:
                return None
    

    def replace(self, new_focus: ParseResult[T]) -> AST[T]:
        focus = new_focus
        for crumb in reversed(self.breadcrumbs):
            match crumb:
                case LeftCrumb(right=right, kind=kind):
                    focus = ThenResult(left=focus, right=right, kind=kind)
                case RightCrumb(left=left, kind=kind):
                    focus = ThenResult(left=left, right=focus, kind=kind)
                case NamedCrumb(name=name, 
                                
                                forward_map=forward_map, 
                                backward_map=backward_map,
                                aggregator=aggregator):
                    focus = NamedResult(name=name, 
                                        value=focus, 

                                        forward_map=forward_map, 
                                        backward_map=backward_map,
                                        aggregator=aggregator)
                case ManyCrumb(before=before, after=after):
                    focus = ManyResult(value=before + (focus,) + after)
                case OrCrumb():
                    focus = OrResult(value=focus)
        return AST(focus=focus)
    
    @cached_property
    def root(self) -> AST[T]:
        z = self
        while z.breadcrumbs:
            z = z.up() # type: ignore
            assert z is not None, "Zipper should not be None when breadcrumbs are present"
        return z
    
    @cached_property
    def leftmost(self) -> AST[T]:
        z = self
        while True:
            next_z = z.down_left()
            if next_z is None:
                return z
            z = next_z





@dataclass(frozen=True)
class ParserState(Generic[T], Insptectable):
    input: Tuple[T, ...] = field(default_factory=tuple)
    index: int = 0
    
    def token_sample_string(self)-> str:
        def encode_tokens(*tokens:T) -> str:
            return ",".join(f"{token.token_type.name}({token.text})" for token in tokens)
        return encode_tokens(*self.input[self.index:self.index + 2])

    def before(self, length: Optional[int] = 5)->str:
        length = min(self.index, length) if length is not None else self.index
        return " ".join(token.text for token in self.input[self.index - length:self.index])
    
    def after(self, length: Optional[int] = 5)->str:
        length = min(length, len(self.input) - self.index) if length is not None else len(self.input) - self.index
        return " ".join(token.text for token in self.input[self.index:self.index + length])
 
    def to_string(self, interested: Callable[[Any], bool])->str:
        return f"ParserState(\n"\
               f"index={self.index}, \n"\
               f"input({len(self.input)})=[{self.token_sample_string()}, ...]), \n"\
               f"before=({self.before()}), \n"\
               f"after=({self.after()})"  


    def current(self)->T:
        if self.ended():
            raise IndexError("Attempted to access token beyond end of stream")
        return self.input[self.index]
    
    def ended(self) -> bool:
        return self.index >= len(self.input)

    def advance(self) -> ParserState[T]:
        return replace(self, index=min(self.index + 1, len(self.input)))
            
    def delta(self, new_state: ParserState[T]) -> Tuple[T, ...]:
        assert self.input is new_state.input, "Cannot calculate differences between different input streams"
        assert 0 <= self.index <= new_state.index <= len(self.input), "Segment indices out of bounds"
        return self.input[self.index:new_state.index]
    
    def copy(self) -> ParserState[T]:
        return self.__class__(input=self.input, index=self.index)

    @classmethod
    def from_tokens(cls, tokens: Tuple[T, ...]) -> ParserState[T]:
        return cls(input=tokens, index=0)




    
@dataclass(frozen=True)
class Parser(Algebra[Tuple[T,...] | T, ParserState[T]]):
    @classmethod
    def token(cls, 
              token_type: Optional[TokenType] = None, 
              text: Optional[str] = None, 
              case_sensitive: bool = False,
              regex: Optional[re.Pattern[str]] = None
              )-> Algebra[Tuple[T,...] | T, ParserState[T]]:
        spec = TokenSpec(token_type=token_type, text=text, case_sensitive=case_sensitive, regex=regex)
        def token_run(state: ParserState[T], use_cache:bool) -> Either[Any, Tuple[Tuple[T,...] | T, ParserState[T]]]:
            if state.ended():
                return Left(state)
            token = state.current()
            if token is None or not spec.is_valid(token):
                return Left(state)
            return Right((Token(token_type = token.token_type, text=token.text), state.advance()))  # type: ignore
        captured: Algebra[Tuple[T,...] | T, ParserState[T]] = cls(token_run, name=cls.__name__ + f'.token({token_type}, {text})')
        def error_fn(err: Any) -> Error:
            if isinstance(err, ParserState):
                return Error(message=f"Cannot match token at {err}", this=captured, state=err)            
            else:
                return Error(message="Cannot match token at unknown state", this=captured)
        # assign the updated parser(with description) to bound variable so the Error.this could be set correctly
        captured = captured.map_error(error_fn)
        return captured        


    @classmethod
    def until(cls, 
              *open_close: Tuple[Algebra[Any, ParserState[T]], Algebra[Any, ParserState[T]]],
              terminator: Optional[Algebra[Any, ParserState[T]]] = None,
              inclusive: bool = True, 
              strict: bool = True) -> Algebra[Any, ParserState[T]]:
        def until_run(state: ParserState[T], use_cache:bool) -> Either[Any, Tuple[Any, ParserState[T]]]:
            counters = [0] * len(open_close)
            tokens: List[Any] = []
            if not terminator and len(open_close) == 0:
                return Left(Error(this=until_run, message="No terminator and no open/close parsers, nothing to parse", state=state))  
            def run_oc(s: ParserState[T], 
                       sign: int, 
                       *oc: Algebra[Any, ParserState[T]])->Tuple[bool, ParserState[T]]:
                matched = False
                for i, p in enumerate(oc):
                    new = p.run(s, use_cache)
                    if isinstance(new, Right):
                        matched = True
                        counters[i] += sign
                        if inclusive:
                            tokens.append(new.value[0])
                        s = new.value[1]
                return matched, s
            opens, closes = zip(*open_close) if len(open_close) > 0 else ((), ())
            tmp_state: ParserState[T] = state.copy()
            if strict:
                c = reduce(lambda a, b: a.or_else(b), opens).run(tmp_state)
                if c.is_left():
                    return Left(Error(
                        this=until_run,
                        message="No opening parser matched",
                        state=tmp_state
                    ))
            while not tmp_state.ended():
                mopen, tmp_state = run_oc(tmp_state, 1, *opens)
                mclose, tmp_state = run_oc(tmp_state, -1, *closes)
                matched = mopen or mclose
                if all(c == 0 for c in counters):
                    if terminator :
                        new = terminator.run(tmp_state, use_cache)
                        if isinstance(new, Right):
                            matched = True
                            if inclusive:
                                tokens.append(new.value[0])
                            return Right((tuple(tokens), new.value[1]))
                    else:
                        return Right((tuple(tokens), tmp_state))
                elif any(c < 0 for c in counters):
                    return Left(Error(this=until_run, message="Unmatched closing parser", state=tmp_state))
                if not matched:
                    tokens.append(tmp_state.current())
                    tmp_state = tmp_state.advance()
            return Right((tuple(tokens), tmp_state))
        return cls(until_run, name=cls.__name__ + '.until')

def sqlglot(parser: DSL[Any, Any], 
            dialect: str) -> DSL[List[exp.Expression], ParserState[Any]]:
    gp = GlotParser(dialect=dialect)
    return parser.map(lambda tokens: [e for e in gp.parse(raw_tokens=tokens) if e is not None])


def parse(parser: Algebra[Any, ParserState[Token]], 
          sql: str, 
          dialect: str) -> AST[Any] | Any:
    input: ParserState[Token] = token_state(sql, dialect=dialect)
    result = parser.run(input, True)
    if isinstance(result, Right):
        return AST(result.value[0])
    assert isinstance(result, Left), "Parser must return Either[E, Tuple[A, S]]"
    return result.value


def token_state(sql: str, dialect: str) -> ParserState[Token]:
    tokens = tuple([Token(token_type=token.token_type, text=token.text) for token in tokenize(sql, dialect=dialect)])
    return ParserState.from_tokens(tokens) 

def token(token_type: Optional[Enum] = None, 
          text: Optional[str] = None, 
          case_sensitive: bool = False,
          regex: Optional[re.Pattern[str]] = None
          ) -> DSL[Any, Any]:
    token_type_txt = token_type.name if token_type is not None else None
    token_value_txt = text if text is not None else None
    msg = 'token(' + ','.join([x for x in [token_type_txt, token_value_txt, str(regex)] if x is not None]) + ')'
    return DSL(
        lambda cls: cls.factory('token', token_type=token_type, text=text, case_sensitive=case_sensitive, regex=regex)
        ).describe(name=msg, fixity='prefix') 

    
def identifier(value: str | None = None) -> DSL[Any, Any]:
    if value is None:
        return token(TokenType.IDENTIFIER)
    else:
        return token(TokenType.IDENTIFIER, text=value)

def variable(value: str | None = None) -> DSL[Any, Any]:
    if value is None:
        return token(TokenType.VAR)
    else:
        return token(TokenType.VAR, text=value)

def literal(lit: str) -> DSL[Any, Any]:
    return token(token_type=None, text=lit, case_sensitive=True)

def regex(regex: re.Pattern[str]) -> DSL[Any, Any]:
    return token(token_type=None, regex=regex, case_sensitive=True)

def lift(value: Any)-> DSL[Any, Any]:
    if isinstance(value, str):
        return literal(value)
    elif isinstance(value, re.Pattern):
        return token(regex=value)
    elif isinstance(value, Enum):
        return token(value)
    else:
        return DSL(lambda cls: cls.success(value))

def number() -> DSL[Any, Any]:
    return token(TokenType.NUMBER)


def string() -> DSL[Any, Any]:
    return token(TokenType.STRING)



def until(*open_close: Tuple[DSL[Tuple[T, ...] | T, ParserState[T]], DSL[Tuple[T, ...] | T, ParserState[T]]],
          terminator: Optional[DSL[Tuple[T, ...] | T, ParserState[T]]] = None,
          inclusive: bool = True, 
          strict: bool = True) -> DSL[Any, Any]:
    return DSL(
        lambda cls: cls.factory('until', 
                           *[(left.alg(cls), right.alg(cls)) for left, right in open_close], 
                           terminator=terminator.alg(cls) if terminator else None, 
                           inclusive=inclusive, 
                           strict=strict)
        ).describe(name="until", fixity='prefix') 


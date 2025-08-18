

from __future__ import annotations
import re
from typing import (
    Optional, Any, TypeVar, Tuple, runtime_checkable, Dict,
    Protocol, Generic, Callable, Union
)
from syncraft.algebra import (
    NamedResult, OrResult,ThenResult, ManyResult, ThenKind,
    Lens
)
from dataclasses import dataclass, field, replace, is_dataclass, asdict
from enum import Enum
from functools import cached_property

@runtime_checkable
class TokenProtocol(Protocol):
    @property
    def token_type(self) -> Enum: ...
    @property
    def text(self) -> str: ...
    

@dataclass(frozen=True)
class Token:
    token_type: Enum
    text: str
    def __str__(self) -> str:
        return f"{self.token_type.name}({self.text})"
    
    def __repr__(self) -> str:
        return self.__str__()

@dataclass(frozen=True)
class TokenSpec:
    token_type: Optional[Enum] = None
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
    pruned: bool = False
    parent: Optional[AST[T]] = None

    def up(self)->Optional[AST[T]]:
        return self.parent

    def left(self) -> Optional[AST[T]]:
        match self.focus:
            case ThenResult(left=left, kind=kind):
                return replace(self, focus=left, parent=self, pruned = self.pruned or kind == ThenKind.RIGHT)
            case _:
                raise TypeError(f"Invalid focus type({self.focus}) for left traversal")

    def right(self) -> Optional[AST[T]]:
        match self.focus:
            case ThenResult(right=right, kind=kind):
                return replace(self, focus=right, parent=self, pruned = self.pruned or kind == ThenKind.LEFT)
            case _:
                raise TypeError(f"Invalid focus type({self.focus}) for right traversal")


    def down(self, index: int) -> Optional[AST[T]]:
        match self.focus:
            case ManyResult(value=children):
                if 0 <= index < len(children):
                    return replace(self, focus=children[index], parent=self, pruned=self.pruned)
                else:
                    raise IndexError(f"Index {index} out of bounds for ManyResult with {len(children)} children")
            case OrResult(value=value):
                if index == 0:
                    return replace(self, focus=value, parent=self, pruned=self.pruned)
                else:
                    raise IndexError(f"Index {index} out of bounds for OrResult")
            case _:
                raise TypeError(f"Invalid focus type({self.focus}) for down traversal")

    def how_many(self)->int:
        match self.focus:
            case ManyResult(value=children):
                return len(children)
            case _:
                raise TypeError(f"Invalid focus type({self.focus}) for how_many")
            
    

    @cached_property
    def root(self) -> AST[T]:
        while self.parent is not None:
            self = self.parent  
        return self
    

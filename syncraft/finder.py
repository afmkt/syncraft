from __future__ import annotations

from typing import (
    Any, Tuple, Generator as PyGenerator, TypeVar, Generic, Hashable
)

from dataclasses import dataclass
from syncraft.algebra import (
    Algebra,  YieldChannelType, SendChannelType
)
from syncraft.ast import  ParseResult, Choice, Many, Then, Marked, Collect, Lazy
from syncraft.cache import Either, Left, Right
from syncraft.generator import GenState, Generator
from syncraft.cache import Cache
from syncraft.syntax import Syntax


T=TypeVar('T', bound=Hashable)
@dataclass(frozen=True)
class Finder(Generator[T], Generic[T]):
    """Generator backend used to search/inspect parse trees.

    This class is passed to a ``Syntax`` to obtain an ``Algebra`` that can be
    run against a ``GenState``. In this module it's used to implement tree-wide search utilities
    such as ``matches`` and ``find``.
    """
    @classmethod
    def anything(cls)->Algebra[Any, GenState[T]]:
        """Match any node and return it unchanged.

        Succeeds on any input ``GenState`` and returns the current AST node as
        the value, leaving the state untouched. Useful as a catch‑all predicate
        when searching a tree.

        Returns:
            Algebra[Any, GenState[T]]: An algebra that always succeeds with the
            tuple ``(input.ast, input)``.
        """
        def anything_run(input: GenState[T], 
                         cache:Cache[GenState[T]]) -> PyGenerator[YieldChannelType ,
                                                                                           SendChannelType,
                                                                                           Either[Any, Tuple[Any, GenState[T]]]]:
            yield from ()
            return Right((input.ast, input))
        return cls(anything_run)



#: A ``Syntax`` that matches any node and returns it as the result without
#: consuming or modifying state.


def anything(syntax: Syntax[Any, Any]) -> Syntax[Any, Any]:
    return syntax.factory('anything')
        

def _matches(s: Syntax[Any, Any], data: ParseResult[Any], cache: Cache[Any])-> bool:
    from syncraft.generator import Runner
    runner = Runner(ast = data, seed=0, restore_pruned=True)
    ast, _ = runner.once(syntax=s, alg_cls=Finder, state=None, cursor=None, cache=None)
    match ast:
        case Left(_):
            return False
        case _:
            return True


def _find(s: Syntax[Any, Any], data: ParseResult[Any], cache: Cache[Any]) -> PyGenerator[ParseResult[Any], None, None]:
    if _matches(s, data, cache):
        yield data
    match data:
        case Marked(value=value):
            yield from _find(s, value, cache)
        case Collect(value=value):
            yield from _find(s, value, cache)
        case Then(left=left, right=right):
            if left is not None:
                yield from _find(s, left, cache)
            if right is not None:
                yield from _find(s, right, cache)
        case Many(value = value):
            for e in value:
                yield from _find(s, e, cache)
        case Marked(value=value):
            yield from _find(s, value, cache)
        case Choice(value=value):
            if value is not None:
                yield from _find(s, value, cache)
        case Collect(value=value):
            yield from _find(s, value, cache)
        case Lazy(value=value):
            yield from _find(s, value, cache)
        case _:
            pass




def matches(syntax: Syntax[Any, Any], data: ParseResult[Any])-> bool:
    if isinstance(data, (Marked, Collect)):
        return _matches(syntax, data.value, Cache())
    else:
        return _matches(syntax, data, Cache())


def find(syntax: Syntax[Any, Any], data: ParseResult[Any]) -> PyGenerator[ParseResult[Any], None, None]:
    yield from _find(syntax, data, Cache())



    
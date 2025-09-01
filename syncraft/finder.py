from __future__ import annotations

from typing import (
    Any, Tuple, Generator as YieldGen, TypeVar, Generic
)
from dataclasses import dataclass
from syncraft.algebra import (
    Algebra, Either, Right, 
)
from syncraft.ast import TokenProtocol, ParseResult, Choice, Many, Then, Marked, Collect

from syncraft.generator import GenState, Generator

from syncraft.syntax import Syntax


T=TypeVar('T', bound=TokenProtocol)
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
        def anything_run(input: GenState[T], use_cache:bool) -> Either[Any, Tuple[Any, GenState[T]]]:
            return Right((input.ast, input))
        return cls(anything_run, name=cls.__name__ + '.anything')



#: A ``Syntax`` that matches any node and returns it as the result without
#: consuming or modifying state.
anything = Syntax(lambda cls: cls.factory('anything')).describe(name="Anything", fixity='infix') 

def _matches(alg: Algebra[Any, GenState[Any]], data: ParseResult[Any])-> bool:
    state = GenState[Any].from_ast(ast = data, restore_pruned=True)
    result = alg.run(state, use_cache=True)
    return isinstance(result, Right)


def _find(alg: Algebra[Any, GenState[Any]], data: ParseResult[Any]) -> YieldGen[ParseResult[Any], None, None]:
    if not isinstance(data, (Marked, Collect)):
        if _matches(alg, data):
            yield data
    match data:
        case Then(left=left, right=right):
            if left is not None:
                yield from _find(alg, left)
            if right is not None:
                yield from _find(alg, right)
        case Many(value = value):
            for e in value:
                yield from _find(alg, e)
        case Marked(value=value):
            yield from _find(alg, value)
        case Choice(value=value):
            if value is not None:
                yield from _find(alg, value)
        case Collect(value=value):
            yield from _find(alg, value)
        case _:
            pass


def matches(syntax: Syntax[Any, Any], data: ParseResult[Any])-> bool:
    """Check whether a syntax matches a specific node.

    Runs the given ``syntax`` (compiled with ``Finder``) against ``data`` only;
    it does not traverse the tree. ``Marked`` and ``Collect`` node are treated as transparent.

    Args:
        syntax: The ``Syntax`` to run.
        data: The AST node (``ParseResult``) to test.

    Returns:
        bool: ``True`` if the syntax succeeds on ``data``, ``False`` otherwise.
    """
    gen = syntax(Finder)
    if isinstance(data, (Marked, Collect)):
        return _matches(gen, data.value)
    else:
        return _matches(gen, data)


def find(syntax: Syntax[Any, Any], data: ParseResult[Any]) -> YieldGen[ParseResult[Any], None, None]:
    """Yield all subtrees that match a syntax.

    Performs a depth‑first traversal of ``data`` and yields each node where the
    provided ``syntax`` (compiled with ``Finder``) succeeds. Wrapper nodes like
    ``Marked`` and ``Collect`` are treated as transparent for matching and are
    not yielded themselves.

    Args:
        syntax: The ``Syntax`` predicate to apply at each node.
        data: The root ``ParseResult`` to search.

    Yields:
        ParseResult[Any]: Each node that satisfies ``syntax`` (pre‑order: the
        current node is tested before visiting its children).
    """
    gen = syntax(Finder)
    yield from _find(gen, data)
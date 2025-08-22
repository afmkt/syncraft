from __future__ import annotations
from typing import Any, List, Tuple
from syncraft.algebra import Biarrow, ThenResult, ThenKind, OrResult, ManyResult, NamedResult
from rich import print

def test_or()->None:
    inc: Biarrow[Any, int, int] = Biarrow(
        forward=lambda s, x: (s, x + 1),
        inverse=lambda s, x: (s, x - 1),
    )
    data  = OrResult(value=1)
    b = data.biarrow()
    b = b >> inc
    s, x = b.forward(None, data)
    assert x == 2
    s, y = b.inverse(s, x)
    assert y == data

def test_named()->None:
    inc: Biarrow[Any, NamedResult[int], int] = Biarrow(
        forward=lambda s, x: (s, x.value + 1),
        inverse=lambda s, y: (s, NamedResult(name="", value=y - 1)),
    )
    data  = NamedResult(name="test", value=1)
    b = data.biarrow()
    c = b >> inc
    s, x = c.forward(None, data)
    assert x == 2
    s, y = c.inverse(s, x)
    assert y == data

def test_many()->None:
    inc: Biarrow[Any, int, int] = Biarrow(
        forward=lambda s, x: (s, x + 1),
        inverse=lambda s, y: (s, y - 1),
    )

    inc2: Biarrow[Any, List[int], List[int]] = Biarrow(
        forward=lambda s, x: (s, [xx + 1 for xx in x]),
        inverse=lambda s, y: (s, [yy - 1 for yy in y]),
    )
    data  = ManyResult(value=(1,2))
    b = data.biarrow(inc)
    c = b >> inc2
    s, x = c.forward(None, data)
    assert x == [3,4]
    s, y = c.inverse(s, x)
    assert y == data

def test_then()->None:
    inc: Biarrow[Any, int, int] = Biarrow(
        forward=lambda s, x: (s, x + 1),
        inverse=lambda s, y: (s, y - 1),
    )
    inc2: Biarrow[Any, Tuple[int, ...], Tuple[int, ...]] = Biarrow(
        forward=lambda s, x: (s, tuple(xx + 1 for xx in x)),
        inverse=lambda s, y: (s, tuple(yy - 1 for yy in y)),
    )

    data  = ThenResult(kind=ThenKind.BOTH, left=1, right=2)
    b = data.biarrow(inc)
    c = b >> inc2
    s, x = c.forward(None, data)
    assert x == (3, 4)
    s, y = c.inverse(s, x)
    assert y == data


def test_left()->None:
    inc: Biarrow[Any, int, int] = Biarrow(
        forward=lambda s, x: (s, x + 1),
        inverse=lambda s, y: (s, y - 1),
    )
    inc2: Biarrow[Any, int, int] = Biarrow(
        forward=lambda s, x: (s, x + 1),
        inverse=lambda s, y: (s, y - 1),
    )

    data  = ThenResult(kind=ThenKind.LEFT, left=1, right=2)
    b = data.biarrow(inc)
    c = b >> inc2
    s, x = c.forward(None, data)
    assert x == 3
    s, y = c.inverse(s, x)
    assert y == data

def test_right()->None:
    inc: Biarrow[Any, int, int] = Biarrow(
        forward=lambda s, x: (s, x + 1),
        inverse=lambda s, y: (s, y - 1),
    )
    inc2: Biarrow[Any, int, int] = Biarrow(
        forward=lambda s, x: (s, x + 1),
        inverse=lambda s, y: (s, y - 1),
    )

    data  = ThenResult(kind=ThenKind.RIGHT, left=1, right=2)
    b = data.biarrow(inc)
    c = b >> inc2
    s, x = c.forward(None, data)
    assert x == 4
    s, y = c.inverse(s, x)
    assert y == data

def test_nested()->None:
    inc: Biarrow[Any, int, int] = Biarrow(
        forward=lambda s, x: (s, x + 1),
        inverse=lambda s, y: (s, y - 1),
    )
    inc2: Biarrow[Any, Tuple[int, ...], Tuple[int, ...]] = Biarrow(
        forward=lambda s, x: (s, tuple(xx + 1 for xx in x)),
        inverse=lambda s, y: (s, tuple(yy - 1 for yy in y)),
    )

    data  = ThenResult(kind=ThenKind.BOTH, left=ThenResult(kind=ThenKind.BOTH, left=0, right=1), right=ThenResult(kind=ThenKind.BOTH, left=2, right=3))
    b = data.biarrow(inc)
    c = b >> inc2
    s, x = c.forward(None, data)
    assert x == (2,3,4,5)
    s, y = c.inverse(s, x)
    assert y == data



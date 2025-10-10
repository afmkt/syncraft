from typing import Any, Generator

import pytest

pytest.importorskip("rstr")

from syncraft.cache import Cache, InProgress, Right


def _dummy_rule(state: int, cache: Cache[int, Right]) -> Generator[Any, Any, Right]:
    yield from ()
    return Right((state, state))


def _make_right(value: int) -> Right:
    return Right((value, value))


def test_gc_removes_entries_below_threshold() -> None:
    cache: Cache[int, Right] = Cache()
    cache.cache[_dummy_rule] = {1: _make_right(1), 5: _make_right(5)}

    removed = cache.gc(3)

    assert removed == 1
    assert 1 not in cache.cache[_dummy_rule]
    assert 5 in cache.cache[_dummy_rule]


def test_gc_prunes_auxiliary_structures() -> None:
    cache: Cache[int, Right] = Cache()
    cache.cache[_dummy_rule] = {1: _make_right(1), 4: _make_right(4)}

    old_ip = InProgress(f=_dummy_rule, key=1, cache_key=1)
    keep_ip = InProgress(f=_dummy_rule, key=4, cache_key=4)
    cache._heads_by_start["start"] = [old_ip, keep_ip]
    cache._agenda = [old_ip, keep_ip]

    cache.gc(3)

    heads = cache._heads_by_start["start"]
    assert heads == [keep_ip]
    assert cache._agenda == [keep_ip]
    assert 1 not in cache.cache[_dummy_rule]


def test_gc_updates_key_mappings_and_counter() -> None:
    cache: Cache[int, Right] = Cache()
    cache._key_registry._ids = {"a": 1, "b": 10}
    cache._key_registry._next = 2

    removed = cache.gc(5)

    assert removed == 0
    assert "a" not in cache._key_registry._ids
    assert cache._key_registry._ids["b"] == 10
    assert cache._key_registry._next == 5


def test_gc_raises_when_active_left_recursion() -> None:
    cache: Cache[int, Right] = Cache()
    ip = InProgress(f=_dummy_rule, key=0, cache_key=0)
    cache._lr_stack.append(ip)

    assert cache.gc(0) == 0

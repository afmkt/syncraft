from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading
import time

from syncraft.grammar import Grammar, grammar, rule
from syncraft.syntax import LazyState, Syntax


S = Syntax


@grammar
class ParallelGrammar(Grammar):
    a = S.tok("a")
    root = rule(a, is_root=True)


def test_grammar_parser_cache_is_singleton_under_concurrency(monkeypatch):
    import syncraft.grammar as grammar_mod

    lock = threading.Lock()
    calls = {"n": 0}
    original_parser_builder = grammar_mod.parser

    def tracked_parser_builder(*args, **kwargs):
        time.sleep(0.01)
        with lock:
            calls["n"] += 1
        return original_parser_builder(*args, **kwargs)

    monkeypatch.setattr(grammar_mod, "parser", tracked_parser_builder)

    def worker():
        return ParallelGrammar.parser()

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _: worker(), range(64)))

    first = results[0]
    assert all(r is first for r in results)
    assert calls["n"] == 1


def test_lazy_state_cached_resolves_once_under_concurrency():
    lock = threading.Lock()
    calls = {"n": 0}

    def thunk():
        time.sleep(0.01)
        with lock:
            calls["n"] += 1
        return S.tok("x")

    state = LazyState(thunk=thunk)

    def worker():
        return state.cached

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _: worker(), range(64)))

    first = results[0]
    assert all(r is first for r in results)
    assert calls["n"] == 1

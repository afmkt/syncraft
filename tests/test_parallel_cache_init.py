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


def test_grammar_parser_cache_reused_within_thread():
    """Verify parser instances are reused when called multiple times in the same thread."""
    parsers = []
    for _ in range(10):
        parsers.append(ParallelGrammar.parser())
    
    # All calls in same thread return the same instance
    first_parser = parsers[0]
    assert all(p is first_parser for p in parsers), "Parser should be cached and reused within thread"


def test_grammar_parser_cache_isolated_per_thread():
    """Verify each thread has its own isolated parser cache."""
    parsers_by_thread = {}
    lock = threading.Lock()
    
    def worker(worker_id):
        thread_id = threading.get_ident()
        # Call parser multiple times in this thread
        parser1 = ParallelGrammar.parser()
        time.sleep(0.01)  # Simulate some work
        parser2 = ParallelGrammar.parser()
        
        with lock:
            parsers_by_thread[thread_id] = (parser1, parser2)
        return thread_id
    
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(worker, range(4)))
    
    # Each thread should have called parser() and gotten consistent results within that thread
    for thread_id, (parser1, parser2) in parsers_by_thread.items():
        assert parser1 is parser2, f"Parser should be cached within thread {thread_id}"
    
    # Different threads should have different parser instances
    all_parsers = [p for parser1, parser2 in parsers_by_thread.values() for p in (parser1, parser2)]
    unique_parsers = set(id(p) for p in all_parsers)
    assert len(unique_parsers) == 4, "Each thread should have its own isolated parser instance"


def test_grammar_generator_cache_isolated_per_thread():
    """Verify each thread has its own isolated generator cache."""
    generators_by_thread = {}
    lock = threading.Lock()
    
    def worker(worker_id):
        thread_id = threading.get_ident()
        # Call generator multiple times in this thread
        gen1 = ParallelGrammar.generator()
        time.sleep(0.01)
        gen2 = ParallelGrammar.generator()
        
        with lock:
            generators_by_thread[thread_id] = (gen1, gen2)
        return thread_id
    
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(worker, range(4)))
    
    # Each thread should have consistent generator instances
    for thread_id, (gen1, gen2) in generators_by_thread.items():
        assert gen1 is gen2, f"Generator should be cached within thread {thread_id}"
    
    # Different threads should have different generator instances
    all_generators = [g for gen1, gen2 in generators_by_thread.values() for g in (gen1, gen2)]
    unique_generators = set(id(g) for g in all_generators)
    assert len(unique_generators) == 4, "Each thread should have its own isolated generator instance"


def test_lazy_state_cached_reused_within_thread():
    """Verify LazyState.cached is resolved once per thread and cached afterwards."""
    lock = threading.Lock()
    calls_per_thread = {}

    def thunk():
        thread_id = threading.get_ident()
        time.sleep(0.01)
        with lock:
            calls_per_thread[thread_id] = calls_per_thread.get(thread_id, 0) + 1
        return S.tok("x")

    state = LazyState(thunk=thunk)

    def worker():
        thread_id = threading.get_ident()
        # Call cached multiple times in the same thread
        result1 = state.cached
        result2 = state.cached
        return thread_id, result1, result2

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: worker(), range(4)))

    # Verify within-thread caching: multiple calls return same instance
    for thread_id, result1, result2 in results:
        assert result1 is result2, f"LazyState.cached should be cached within thread {thread_id}"
    
    # Verify each thread called thunk once
    for thread_id, call_count in calls_per_thread.items():
        assert call_count == 1, f"Thunk should be called exactly once per thread, but thread {thread_id} called it {call_count} times"


def test_lazy_state_isolation_across_threads():
    """Verify different threads resolve the lazy state independently."""
    lock = threading.Lock()
    resolved_values_by_thread = {}

    def thunk():
        thread_id = threading.get_ident()
        time.sleep(0.01)
        value = S.tok(f"token_{thread_id}")
        with lock:
            resolved_values_by_thread[thread_id] = value
        return value

    state = LazyState(thunk=thunk)

    def worker():
        return threading.get_ident(), state.cached

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: worker(), range(4)))

    # Each thread got a unique resolved value
    unique_values = set(id(v) for _, v in results)
    assert len(unique_values) == 4, "Each thread should resolve LazyState independently"

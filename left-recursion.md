# Left-Recursion Correction Walkthrough

The Syncraft parser runtime performs fixed-point iteration to resolve direct and mutual left recursion. This note explains how the cache, stack, and iteration logic work, using the mutually left-recursive grammar:

````

---

# Cache.py Implementation Design

## Overview

The `cache.py` implementation provides a robust left-recursion correction algorithm that handles both same-position mutual recursion and cross-position dependencies. The design combines stack-based group detection with agenda-driven propagation to ensure complete dependency resolution.

## Key Data Structures

### Core Cache Components
```python
@dataclass
class Cache(Generic[S]):
    cache: DefaultDict[Rule, Dict[int, CacheEntry[S]]]     # Main memoization cache
    start2rules: DefaultDict[int, set[Rule]]               # Position → rules that start there
    end2rules: DefaultDict[int, set[Rule]]                 # Position → rules that end there
    agenda: list[tuple[Rule, int]]                         # Cross-position dependency queue
    group: Optional[Group[S]]                              # Current left-recursion group
    lazy_stack: list[Tuple[Rule, int]]                     # Stack of lazy rule calls
```

### Cache Entries and Progress Tracking
```python
@dataclass
class CacheEntry(Generic[S]):
    payload: Ret | InProgress[S]    # Either final result or in-progress computation
    state: S                        # Parser state when rule started
    
@dataclass
class InProgress(Generic[S]):
    rule: Rule                      # The rule being computed
    revision: int = 0               # Number of successful growth attempts
    growing: bool = False           # Whether latest growth succeeded
    result: Optional[Ret] = None    # Best result found so far
```

### Group Management
```python
@dataclass
class Group(Generic[S]):
    members: list[Tuple[Rule, int]]  # All rules participating in mutual recursion
    
    @property
    def leader(self) -> Tuple[Rule, int]:
        return self.members[-1]      # Last rule triggers group processing
```

## Algorithm Flow

### 1. Entry Point (`exec` method)
```
1. Check cache for existing result
2. If InProgress exists → left recursion detected
   - Build group of all InProgress at same position
   - Return Left(SEEDING) to try non-recursive alternatives
3. If lazy rule → create InProgress entry
4. Run rule and install seed
5. Post-process for group growth and cross-position propagation
```

### 2. Group Detection and Formation
- **Stack-based detection**: `lazy_stack` tracks active lazy rule calls
- **Position-based grouping**: `build_group()` finds all `InProgress` entries at same position using `start2rules`
- **Universal inclusion**: Groups include ALL rules with `InProgress` at position, not just lazy rules

### 3. Same-Position Growth (`post_process` method)
```
For each group member:
    1. Re-run rule with current group state
    2. Check if result improved (consumes more input)
    3. If improved:
       - Update InProgress.result
       - Increment revision
       - Set growing = True
       - Build agenda for cross-position dependencies
    4. Repeat until no member improves (fixed point)
```

### 4. Cross-Position Dependency Handling
- **Agenda building**: When rule improves, scan `end2rules` for rules that ended before improvement
- **Propagation**: `process_agenda()` re-runs affected rules at earlier positions
- **Invalidation**: Clear cache entries to force re-computation

### 5. Finalization
```
1. Unwrap all InProgress → final results
2. Clear group
3. Clear agenda
4. Update end2rules mappings
```

## Key Design Innovations

### Stack-Based Multi-Head Detection
- **Problem**: Traditional approaches miss concurrent parsing attempts at same position
- **Solution**: Extract all lazy rules between recursive call frames on stack
- **Benefit**: Natural grouping without separate bookkeeping

### Position-Based Indexing
- **start2rules**: Fast lookup of all rules beginning at position
- **end2rules**: Efficient cross-position dependency detection
- **Benefit**: O(1) access instead of O(cache_size) scanning

### Two-Phase Dependency Resolution
1. **Same-position phase**: Handle mutual recursion within position using groups
2. **Cross-position phase**: Handle dependencies across positions using agenda
- **Benefit**: Clean separation of concerns, guaranteed completeness

### Incremental Growth Tracking
- **revision counter**: Track improvement attempts per InProgress
- **growing flag**: Signal when improvements occur
- **Benefit**: Precise invalidation, efficient agenda building

## Cross-Position Dependency Example

Consider grammar:
```
Expr -> Expr '-' Term | Term
Term -> Term '*' Factor | Factor  
Factor -> '(' Expr ')' | 'n'
```

Input: `'n - n * n - n'`

### Problem
1. `Expr(0)` initially parses `'n - n'` (ends at pos 3)
2. Later, `Term(2)` grows to parse `'n * n'` (ends at pos 5) 
3. `Expr(0)` should retry since longer `Term` enables `'n - n * n - n'`

### Solution
1. **Group growth**: `Term(2)` improves, sets `growing=True`
2. **Agenda building**: Scan `end2rules[0..4]` for rules ending before pos 5
3. **Find dependency**: `Expr(0)` ended at pos 3 < 5, add to agenda
4. **Propagation**: Re-run `Expr(0)` with improved `Term(2)` result
5. **Complete parse**: `Expr(0)` now consumes full input

## Error Handling

### Non-Productive Recursion Detection
- **Stack-based**: Detect when recursive call returns to original frame without progress
- **Iteration limits**: Prevent infinite growth with `max_revision` counter
- **Progress checking**: Ensure growth advances input position

### Lifecycle Management
- **Group cleanup**: Set to None after processing completes
- **Agenda clearing**: Automatic via processing, explicit on errors  
- **InProgress unwrapping**: Convert to final results after growth
- **Memory management**: GC operations clean position-based indices

## Performance Characteristics

### Time Complexity
- **Cache lookup**: O(1) for memoized results
- **Group formation**: O(rules_at_position) via start2rules
- **Growth iteration**: O(group_size × growth_iterations)
- **Cross-position scan**: O(improved_end × avg_rules_per_position)

### Space Complexity  
- **Cache storage**: O(rules × positions × results)
- **Position indices**: O(positions × rules_per_position)
- **Agenda size**: O(cross_position_dependencies)

### Optimizations
- **Early termination**: Stop growth at first fixed point
- **Targeted invalidation**: Only clear cache entries that need re-computation
- **Lazy agenda building**: Only scan positions that actually improved
- **Position filtering**: GC operations maintain index consistency

This design achieves robust left-recursion handling while maintaining performance through careful indexing and incremental processing strategies.

Values such as `Right((value, state))` always store both the semantic value and the updated `ParserState`. For clarity, this document abbreviates them as `Right(value, state)`.

## Core Data Structures
- **Frame stack** – `Cache.stack` tracks active rule calls. Each frame may hold an `InProgress` head when a lazy rule (i.e., a rule marked as left-recursive) begins seeding.
- **Cache table** – `cache[rule][position]` stores either a finished `Right` result or an `InProgress` head while seeding/growing.
- **InProgress** – A placeholder created for lazy rules. It records the initial state and the best result found so far. `grow()` updates the stored result if a new attempt consumes more input.
- **Group** – All `InProgress` heads that share the same starting position (`cache_key`). Groups are discovered lazily by walking the stack and are reused whenever another head at the same position is encountered. Groups allow mutual recursion of arbitrary size.

## Algorithm Overview
1. **Entry** – When `cache.exec(rule, state)` runs, it looks up `(rule, state.cache_key)`.
   - If a finished `Right` is present and no group is active, that result is reused immediately.
   - If an `InProgress` head for the same position exists, the cache registers the current rule in the group and returns `Left(('SEEDING', state))`. This sentinel prevents infinite descent while the seed is still being computed.
2. **Seeding** – For lazy rules, `exec` installs an `InProgress` head before running the rule body. The rule explores only its base (non-recursive) alternatives because recursive calls bounce back with the seeding sentinel.
3. **Group formation** – When recursion re-enters a rule at the same position, `_collect_heads` gathers every `InProgress` encountered on the stack with the shared `cache_key`. The order is oldest-to-newest entry; the first element is exposed as `Group.leader`, but every head is treated uniformly during growth.
4. **Seed installation** – After the initial pass returns, `install_seed` writes the seed result into the `InProgress`. If a group exists and every head now has a seed (Right or Left), the cache starts the growth phase.
5. **Growth loop** – `_grow_group` iterates across all heads:
   - Each head reruns its rule using the best results from group members already stored in the cache.
   - If any attempt returns a `Right` that advances further than the head’s current best state, the head is updated and the loop repeats.
   - If no head improves, the fixed point is reached. `InProgress` entries are replaced with the best `Right` results; failures remove the cache entry entirely.
6. **Termination and errors** – If every seed fails, a `LeftRecursionError` (`reason='no-progress'`) is raised. If the group keeps improving beyond `max_growth_iterations`, an error with `reason='iteration-cap'` is raised. Otherwise, the cache hands the caller the final `Right` value.

## Mutual Left Recursion Example

The trace below highlights how Syncraft handles the `A/B` cycle at the first input position.

1. **Initial call**
   - Stack: `A@0`
   - Cache: `(A,0) = InProgress(seed=None)`
2. **A selects `B >> A`**
   - Stack: `B@0`, `A@0`
   - Cache: `(B,0) = InProgress(seed=None)`
3. **B selects `A >> B`**
   - Stack: `A@0`, `B@0`, `A@0`
   - Cache: unchanged
   - The recursive `A@0` hits the existing `InProgress` and returns `Left(('SEEDING', state0))`.
4. **Seeding succeeds**
   - `A@0` falls back to `'a'`, yielding `Right('a', state1)`.
   - `B@0` retries `A >> B`: it now obtains `Right('a', state1)` from `A@0`, then recursively calls itself at index 1.
5. **Group expansion**
   - Encountering `B@1` creates another `InProgress` and, through the recursive call to `A@1`, constructs the group `{A@1, B@1}`.
6. **Growth**
   - Once all heads have seeds, `_grow_group` iteratively re-invokes each rule in the group. Successful attempts replace standing results whenever they consume more input (i.e., advance to a higher `cache_key`). The process continues breadth-wise across the group until no head improves.
7. **Finalization**
   - `cache[(A,0)]` and `cache[(B,0)]` now hold finished `Right` results that advance to the furthest reachable state. The corresponding `InProgress` objects are discarded.

This flow repeats independently for each subsequent position (`cache_key`) that participates in left recursion, allowing the parser to handle nested or chained recursive structures.

## Complete Procedure Summary

```
function exec(rule, state):
  cache_key = state.cache_key
  bucket = cache[rule]
  entry = bucket.get(cache_key)

  if entry is finished Right and no group in progress:
    return entry

  if entry is InProgress:
    group = init_group(rule, state)
    return Left(('SEEDING', state))

  if rule is lazy:
    head = InProgress(rule, state)
    bucket[cache_key] = head
    push head onto call stack
    seed = run_rule(rule, state)
    return install_seed(rule, seed, state, bucket)

  seed = run_rule(rule, state)
  if seed is Right:
    bucket[cache_key] = seed
  return seed

function install_seed(rule, seed, state, bucket):
  head = bucket[state.cache_key]  # must be InProgress
  group = groups.get(state.cache_key)

  head.result = seed
  if group missing or some head still has no result:
    if seed is Right: bucket[state.cache_key] = seed
    else: bucket.pop(cache_key, None)
    return seed

  return grow_group(cache_key, group, head)

function grow_group(cache_key, group, focus):
  ensure some head has Right seed else LeftRecursionError
  repeat until no head improves:
    for head in group.heads:
      attempt = run_rule(head.rule, head.initial_state)
      if attempt is Right and attempt advances further:
        head.result = attempt
        improved = true

  replace each InProgress with its best Right
  delete groups[cache_key]
  return focus.result or Left()
```

This algorithm naturally supports mutual left recursion because groups aggregate every `InProgress` head encountered at a shared start position, regardless of which rule created it. Each iteration uses the latest results from all group members, so as soon as one head makes progress, the others see the improvement on their next pass.

# Left-Recursion Correction Walkthrough

The Syncraft parser runtime performs fixed-point iteration to resolve direct and mutual left recursion. This note explains how the cache, stack, and iteration logic work, using the mutually left-recursive grammar:

```
A = (B >> A) | 'a'
B = (A >> B) | 'b'
input  = "a b a b"
```

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

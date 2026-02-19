# Failure Modes in Bidirectional Parsing - Design Notes

**Date:** February 20, 2026  
**Context:** Bug investigation in regex.py revealed a fundamental design tradeoff

## The Problem

### What Happened
While debugging `test_groups_flags_scoped_with_disable()` in try.py, we encountered:

```python
inline_flags = S.seq(+flag_seq, (~(minus >> flag_seq)).map(...)).to(
    lambda env: (env.enabled, env.disabled),  # ← BUG: these fields don't exist!
    lambda env: InlineFlags(env.enabled, env.disabled)
)
```

The unification system created:
- `env.flag_seq` (first component)
- `env.X` (second component)

But `env.enabled` and `env.disabled` were never bound.

### What We Expected
An immediate error: `AttributeError: 'env' has no attribute 'enabled'`

### What Actually Happened
```
env.enabled access fails (soft failure)
  ↓
inline_flags parsing fails silently
  ↓
all group alternatives fail
  ↓
atom.many() returns []
  ↓
piece.many() returns [] (valid for empty branches!)
  ↓
branch with 0 pieces succeeds
  ↓
regex succeeds with empty content
  ↓
eof check FAILS ← error reported HERE, far from the actual bug
```

**Error message:** "Expected end of input" at position 0  
**Actual problem:** Undefined field access in inline_flags definition

---

## The Design Tradeoff

### Current Design: Soft Failures

**Philosophy:** Transformation failures are treated as "this parse path didn't match" and trigger backtracking.

**Benefits:**
- ✅ Enables constraint-based parsing
- ✅ Data validation can guide parsing decisions
- ✅ Flexible backtracking through alternatives
- ✅ Bidirectional transformations can reject invalid structures

**Example Use Case:**
```python
# Parse numbers, but only accept even ones
even_number = number.to(
    lambda env: env.X if env.X % 2 == 0 else FAIL,  # Soft fail = constraint
    ...
)
```

**Drawbacks:**
- ❌ Errors appear far from their source
- ❌ Programmer mistakes (typos, undefined fields) hard to debug
- ❌ Silent failures cascade through the grammar
- ❌ `.many()` and `.sep_by()` can produce empty results, hiding upstream failures

### Alternative: Hard Failures

**Philosophy:** Certain failures (undefined variables, type errors) should stop parsing immediately.

**Benefits:**
- ✅ Immediate, localized error reporting
- ✅ Easier debugging during development
- ✅ Clear distinction between "didn't match" vs "something's wrong"

**Drawbacks:**
- ❌ Breaks constraint-based parsing model
- ❌ Less flexible backtracking
- ❌ Hard to define boundary between "expected failure" and "programmer error"
- ❌ Context-dependent: `env.X.method()` raising `AttributeError` - constraint or bug?

---

## Why This Is Hard

The challenge is **determining which failures should be soft vs hard**:

| Failure Type | Soft or Hard? | Reasoning |
|--------------|---------------|-----------|
| `env.nonexistent_field` | Hard? | Likely a typo/bug |
| `env.X % 2 == 0` returning False | Soft | Valid constraint |
| `int(env.X)` raising ValueError | Soft? Hard? | Could be constraint or bad input |
| `env.X.method()` AttributeError | Soft? Hard? | Method doesn't exist vs wrong type |
| Custom validation raises Exception | Soft? Hard? | Depends on intent |

**The line is blurry and context-dependent.**

---

## Potential Solutions

### Option 1: Developer Mode Toggle
```python
S.set(strict_mode=True)   # Development: all failures are hard
S.set(strict_mode=False)  # Production: soft failures for constraints
```

**Pros:** Simple, non-invasive, easy to toggle  
**Cons:** All-or-nothing, doesn't distinguish failure types  

### Option 2: Explicit Opt-in for Strictness
```python
inline_flags = S.seq(...).to(...).strict()  # Hard failures in this transform
even_number = number.to(...).soft()          # Soft failures (default)
```

**Pros:** Granular control, explicit intent  
**Cons:** Requires choosing mode for every transformation  

### Option 3: Separate Exception Types
```python
class ParseConstraintFailure(Exception):
    """Expected failure - soft fail and backtrack"""
    pass

class ParseError(Exception):
    """Programmer error - hard fail immediately"""
    pass

# In env implementation:
def __getattr__(self, name):
    if name not in self.__dict__:
        raise ParseError(f"Undefined field: {name}")  # Hard fail
```

**Pros:** Semantic distinction, library can handle automatically  
**Cons:** Users must know which exception to raise; undefined variable detection still heuristic-based  

### Option 4: Enhanced Debug/Trace Mode
```python
regex = S.seq(...).debug(level='verbose')  # Show all soft failures with reasons

# Output:
# "inline_flags failed: AttributeError: 'env' has no attribute 'enabled'"
# "group alternative 0 failed at position 0"
# "group alternative 1 failed at position 0"
# ...
# "All group alternatives exhausted, returning empty"
```

**Pros:** No API changes, preserves both models, aids debugging  
**Cons:** Doesn't prevent errors, only helps find them  

### Option 5: Static Analysis / Linting
```python
# External tool that analyzes grammar definitions
$ syncraft-lint regex.py

regex.py:326: error: Field 'enabled' not bound in S.seq(+flag_seq, ...)
  Available fields: flag_seq, X
```

**Pros:** Catches errors before runtime, no library changes  
**Cons:** Requires separate tooling, may have false positives  

### Option 6: Accept Current Design
- Document the soft failure behavior clearly
- Emphasize using `.debug()` for development
- Provide better error context (show deepest parse position reached)
- Train users to expect this behavior

**Pros:** No changes, preserves design philosophy  
**Cons:** Remains difficult for new users  

---

## Open Questions for Future Consideration

1. **How common are programmer errors vs intentional constraints?**
   - If constraints are rare, maybe default to hard failures?
   - If constraints are common, keep soft failures as default?

2. **Can we detect undefined field access automatically?**
   - Track which fields are bound after unification
   - Raise hard error on access to unbound fields
   - But how to handle computed field access (`getattr(env, name)`)?

3. **Should `.many()` and `.sep_by()` have an `allow_empty` flag?**
   - `piece.many(allow_empty=False)` → fail instead of returning []
   - But breaks valid empty branches in regex!

4. **Is there a way to preserve both models cleanly?**
   - Maybe soft failures with better error accumulation?
   - Report all failure reasons when final parse fails?

5. **What do other bidirectional/constraint-based parsers do?**
   - Investigate Prolog parsers, CHR solvers, etc.
   - Are there established patterns for this problem?

---

## Immediate Fixes Applied

**What we fixed:**
1. Changed `env.enabled`/`env.disabled` to `env.enabled_flags`/`env.disabled_flags` (matching actual bound variables)
2. Fixed GroupAtom field mappings for FLAGS and FLAGS_SCOPED alternatives
3. Reverted unnecessary reordering of group alternatives (backtracking handles it)

**Root cause:** Human error (field name typo), exacerbated by soft failure cascade

**Lesson learned:** The soft failure model makes typos in field names particularly dangerous because they fail silently and manifest far from the source.

---

## Recommendation for Next Steps

**Short term:** Add this as a known limitation in documentation

**Medium term:** Experiment with Option 4 (enhanced debug output) - low risk, high value

**Long term:** After more experience with bidirectional grammar authoring, revisit this with real-world usage data:
- How often do users write constraints vs make typos?
- What failure modes are most common?
- Is there an 80/20 solution we're missing?

**Decision:** Deferred pending more practical experience with the library.

---

## References

- Original bug: `test_groups_flags_scoped_with_disable()` in try.py
- Fixed in: syncraft/regex.py (inline_flags definition)
- Discussion date: February 20, 2026

# Left-Recursion Correction Example: 
* A = (B >> A) | 'a', 
* B = (A >> B) | 'b', 
* input: 'a b a b'

## Notation
- Stack: Top = most recent call, Bottom = oldest call
- Cache: Shows entries for (Rule, Position)
- Group: Mutually left-recursive heads at same position
- Group Leader: Coordinates growth (bottom-most in group)

---

## Step-by-Step Walkthrough

### 1. Start: parse(A, 0)
Stack:
- A@0
Cache:
- (A, 0): InProgress (seeding)

### 2. Try first alternative of A: (B >> A)
Stack:
- B@0
- A@0
Cache:
- (A, 0): InProgress (seeding)
- (B, 0): InProgress (seeding)

### 3. Try first alternative of B: (A >> B)
Stack:
- A@0   ← left-recursive re-entry
- B@0
- A@0
Cache:
- (A, 0): InProgress (seeding, on stack twice)
- (B, 0): InProgress (seeding)

### 4. Left-Recursion Detected
- Group formed: [A@0, B@0]
- Group leader: A@0 (bottom-most)

### 5. Seeding phase (base cases only)
- A@0 tries 'a' at pos 0: succeeds, advances to 1
- B@0 tries 'b' at pos 0: fails, tries (A >> B), but A@0 is in progress, so returns Left

Stack unwinds to:
- B@0
- A@0
Cache:
- (A, 0): InProgress (result: Right('a', 1))
- (B, 0): InProgress (result: None)

### 6. Resume B@0: try (A >> B) again
- Calls parse(A, 0): returns Right('a', 1)
- Calls parse(B, 1)
Stack:
- B@1
- B@0
- A@0
Cache:
- (A, 0): InProgress (result: Right('a', 1))
- (B, 0): InProgress (result: None)
- (B, 1): InProgress (seeding)

### 7. B@1 tries (A >> B)
- Calls parse(A, 1)
Stack:
- A@1
- B@1
- B@0
- A@0
Cache:
- (A, 0): InProgress (result: Right('a', 1))
- (B, 0): InProgress (result: None)
- (B, 1): InProgress (seeding)
- (A, 1): InProgress (seeding)

### 8. A@1 tries (B >> A)
- Calls parse(B, 1)
Stack:
- B@1 (again)
- A@1
- B@1
- B@0
- A@0

- Left-recursion detected at B@1 and A@1
- Group: [A@1, B@1]
- Group leader: A@1

### ... (Continue recursively for input 'a b a b')

---

## Growth Phase (Fixed-Point Iteration)

For each group (e.g., [A@0, B@0]):
- Group leader (A@0) initiates growth:
  - Iteratively attempts to improve results for A@0 and B@0
  - If any member's result improves (consumes more input), repeat
  - When no further improvement, fixed point is reached

---

## Example Table (at group [A@0, B@0])

| Stack (top to bottom) | Group Membership | Group Leader | Cache Entry         | Result                |
|----------------------|------------------|--------------|---------------------|-----------------------|
| B@0                  | Yes              | No           | (B, 0): InProgress  | result: Right(...)    |
| A@0                  | Yes              | Yes ⟵        | (A, 0): InProgress  | result: Right(...)    |

---

## Final State (after fixed point)
- All InProgress entries for group members have their .result set to the best parse result.
- The group is finalized.
- The cache for (A, 0) and (B, 0) contains the InProgress objects with their .result fields set.

---

## Notes
- Each new input position (e.g., 1, 2, 3) forms its own group as recursion continues.
- The process repeats for each group until the entire input is parsed or no further progress is possible.

---

This document illustrates the stack, cache, group, and group leader at each key step of left-recursion correction for the given grammar and input.

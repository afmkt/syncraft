# Security Policy

## Scope

Syncraft is a parser combinator library with minimal attack surface:

- No network, file I/O, or code execution.
- Pure grammar matching and value transformation.
- Memoized parsing mitigates ReDoS patterns.

Most security concerns are **user responsibilities**:

- Custom regex patterns in `Syntax.rp()` should be tested for performance.
- Complex grammars may require memory/timeout constraints at the application level.
- Validate and sanitize values before using parsed results in security-sensitive contexts.

## Reporting

If you discover an actual vulnerability in Syncraft itself (not user code), please report privately to: `michael@esacca.com`

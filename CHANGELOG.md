

This project follows Semantic Versioning from `1.0.0` onward.
It's in pre-1.0 status. APIs may change and breaking changes are possible until 1.0.

## [Unreleased]

_No unreleased changes at this time._

## [0.8.0] - 2026-03-12

### Added
- Major parsing/generation roundtrip improvements and bugfixes.
- New documentation on bidirectional parsing, AST space vs. parse subspace, and roundtripping caveats.
- Custom EBNF renderer, EBNFExpr.to_str.
- Expanded and clarified API docstrings for all public symbols.
- Improved test coverage and roundtrip validation for EBNF/Syntax.
- Syntax.case for conditional transformation
- Syntax.to for structural transformation
- Syntax.bimap for converting values
- Syntax.format for specify linebreaks and indentation
- Normalization nested structure in Syntax.alt and Syntax.seq
- Syntax.rp to construct CFG grammar rule from regex


### Changed
- General documentation and quickstart improvements.
- Replace IdTracker with Generator.steps for explicit cache_key maintainance


### Fixed
- Resolved issues with EBNF AST simplification and roundtrip mismatches.
- Fixed edge cases in bidirectional parsing and generation.
- No known test failures; all tests pass.

## [0.3.2] - 2026-03-07

### Changed
- API and docs refinements in preparation for `1.0` planning.

### Fixed
- Multiple parser/generator bug fixes and doc updates (see git history).

## [0.3.1] - 2025

### Changed
- Iterative parser and API improvements.

## [0.3.0] - 2025

### Added
- `0.3.x` line introduced with API cleanup and ergonomics work.

## [0.2.9] - 2025
## [0.2.8] - 2025
## [0.2.7] - 2025
## [0.2.6] - 2025
## [0.2.5] - 2025
## [0.2.4] - 2025

### Notes
- Historical versions existed before this changelog was introduced.
- For exact commit-level details of early releases, inspect tags and commit history:
  - `git tag`
  - `git log --oneline --decorate`

# Contributing

Thanks for your interest in Syncraft.

This project currently has a single official maintainer, so contributions are intentionally lightweight and practical.

## Before You Start

- Open an issue first for non-trivial changes.
- Keep pull requests focused and small.
- Prefer bug fixes, docs improvements, and tests.

## Local Setup

```bash
uv sync --group dev
source .venv/bin/activate
```

Run test:

```bash
pytest
```

## Pull Request Guidelines

- One topic per PR.
- Include tests for behavior changes.
- Update docs for user-visible API changes.
- Keep commit messages clear and short.

## Review and Merge Policy

- The maintainer decides scope and timing.
- Some PRs may be closed in favor of a smaller alternative.
- Large feature work may be asked to start as an RFC issue first.

## Release Policy

- Releases are tag-driven.
- Stability guarantees become stricter from `1.0.0` onward.

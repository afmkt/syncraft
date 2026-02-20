# AI Readiness Guide

This page explains how to make Syncraft usage easy and reliable in AI workflows.
The goal is not to add AI features, but to make the library predictable and well described so
LLM tools can call it correctly.

## 1) Define the public API surface

Keep a small, stable set of public entry points and document them clearly.

Checklist:
- Decide which symbols are supported long term
- Mark internal modules and helpers as private
- Track breaking changes in a changelog

## 2) Provide short, deterministic examples

AI tools learn from examples. Keep them small, fast, and reproducible.

Guidelines:
- Use short inputs with expected outputs
- Avoid randomness or add seeding when needed
- Keep each example under 20 lines

## 3) Make errors actionable

Errors should explain how to fix the issue, not just what went wrong.

Guidelines:
- Use clear exception types
- Include the expected format and a minimal fix
- If possible, include a snippet of the failing input

## 4) Strengthen type hints and docstrings

Type hints help AI tools infer correct usage and parameters.

Guidelines:
- Add type hints to all public functions and methods
- Use docstrings that show parameter meaning and return values
- Prefer examples in docstrings for tricky parts

## 5) Document common tasks and pitfalls

Create a small reference page that answers typical questions:
- How to define a grammar
- How to parse and generate
- How to use marks and `bimap`
- Limitations (such as left recursion and round trip caveats)

## 6) Optional: add AI integration notes

If you expect AI use, consider:
- A short section in the README called "AI usage"
- A single page in docs with copy ready examples and expected outputs
- A stable testing corpus for AI evaluation

## Suggested doc template

Use this simple structure for each example:

```text
Goal: one sentence summary
Input: short input string
Output: short expected output
Code: minimal example
```

Keeping docs consistent helps both humans and AI tools use the library correctly.

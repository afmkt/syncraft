# Prompt Template (rp variant)

You are implementing this task using Syncraft `Syntax.rp` style.

- Prefer `Syntax.rp` for regex-flavored CFG fragments.
- Use external references `(?&name)` when appropriate.
- Keep transformations close to rule definitions.
- Target file(s): {{TARGET_FILES}}
- Test file: {{TEST_FILE}}

Task spec:
{{TASK_SPEC}}

Output requirements:
- Produce working code only.
- Ensure tests pass without changing unrelated code.

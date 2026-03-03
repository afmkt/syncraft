Task: Repair existing Syncraft regex++ grammar code so the test command passes.

Spec (must remain satisfied):
{{SPEC_TEXT}}

Current code (edit/fix this):
{{CURRENT_CODE}}

Executed test command:
{{TEST_COMMAND}}

Failure output:
{{FAILURE_OUTPUT}}

Output requirements:
- Return Python code only (no markdown fences, no prose).
- Keep `Syntax.rp` as the primary style.
- Keep top-level grammar variable name as `grammar`.
- Make minimal changes required to pass the test command.
- Avoid unsupported regex backreferences like `\1`.

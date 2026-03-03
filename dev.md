## Testing

Run the regex fuzz test:


```bash
pytest -q tests/test_regex.py -k test_fuzzing
```

To reproduce a fuzz failure, set a fixed seed:

```bash
SYNCRAFT_REGEX_FUZZ_SEED=12345 pytest -q tests/test_regex.py -k test_fuzzing
```

TODO
- [ ]  Interactive parse tree visualizer
- [ ]  Static analysis tool
- [ ]  Expand `Syntax.rp` docstring with supported regex++ subset, `(?&name)` references, recursion template, and backreference limitation notes
- [ ]  Expand `Syntax.map` docstring with callable arity contract (1 or 2) and common pitfalls (`map(tuple)`)
- [ ]  Clarify `Syntax.sep_by` behavior (one-or-more) and explicitly document that there is no `sep_by1`
- [ ]  Add `syncraft.regex.rp(...)` function docstring covering output shapes, reference wiring, and common error cases
- [ ]  Add an LLM-safe API subset section in README (`rp`, `sep_by`, `map`, `to`, `lazy`, `rule`) plus explicit avoid-list (`transform`, `sep_by1`, regex backreferences)
- [ ]  Add regex++ focused quickstart section in docs with minimal runnable and recursive examples
- [ ]  Add curated AI authoring guidance links at top of API reference docs
- [ ]  Document `@grammar` authoring constraints and introspection caveats (`inspect.getsource`) in grammar docs/docstrings
- [ ]  Add dedicated docs/how-to/ai-authoring-rp.md with strict output contract, positive/negative examples, and repair playbook
- [ ]  Add dedicated docs/how-to/ai-authoring-grammar.md with root-rule patterns and lazy recursion templates
- [ ]  Add scripts/ai_lint_generated_grammar.py for fail-fast checks on common LLM hallucinations and output-shape violations
- [ ]  Add scripts/ai_smoke_check.py to import generated grammar modules and run minimal parse smoke checks with normalized diagnostics
- [ ]  Add tests/test_ai_contracts.py to lock AI-readiness guarantees for docs/API stability

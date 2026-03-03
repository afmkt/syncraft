# Curl Materials for LLM Grammar Authoring

This folder provides a practical path to generate Syncraft regex++ grammar using `curl` with local Ollama.

## Files

- `system_regexpp_authoring.md` — system instructions for writing valid `Syntax.rp` grammar.
- `user_prompt_template.md` — user prompt shape with `{{SPEC_TEXT}}` and `{{EXAMPLES_TEXT}}` placeholders.
- `repair_prompt_template.md` — repair prompt that feeds current code + failing test output back to the model.
- `spec_example_kv.md` — sample grammar spec.
- `ollama_curl_example.sh` — runnable script that calls local Ollama and writes generated code.
- `ollama_repair_loop.sh` — iterative fix loop that reruns a test command until pass or max rounds.

## Quick run (local Ollama)

1. Start Ollama and ensure your model exists (default: `gpt-oss:20b`).
2. Run:

```bash
bash ai/curl/ollama_curl_example.sh
```

This writes generated grammar code to:

- `ai/curl/generated_grammar.py`

### Use a custom spec file

```bash
bash ai/curl/ollama_curl_example.sh ai/curl/spec_example_kv.md ai/curl/my_grammar.py
```

### Use a different model

```bash
OLLAMA_MODEL=qwen2.5-coder:7b bash ai/curl/ollama_curl_example.sh
```

## Repair loop (auto-fix on test failure)

First generate a draft grammar, then run repair loop with a test command.

```bash
bash ai/curl/ollama_repair_loop.sh ai/curl/spec_example_kv.md ai/curl/generated_grammar.py "python ai/curl/generated_grammar.py" 3
```

Arguments:

1. `spec_file` (default: `ai/curl/spec_example_kv.md`)
2. `target_file` (default: `ai/curl/generated_grammar.py`)
3. `test_command` (default: `python ai/curl/generated_grammar.py`)
4. `max_rounds` (default: `3`)

You can also use pytest as the test command, for example:

```bash
bash ai/curl/ollama_repair_loop.sh ai/curl/spec_example_kv.md ai/curl/generated_grammar.py "pytest -q tests/test_ai_t003.py" 4
```

## Notes

- No external API key is required for local Ollama.
- The script uses `temperature=0.1` for more deterministic code generation.
- Repair loop stores a per-round backup at `target_file.bak` before writing model output.
- Review and test generated grammar before production usage.

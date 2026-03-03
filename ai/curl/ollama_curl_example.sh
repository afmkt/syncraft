#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEM_FILE="$BASE_DIR/system_regexpp_authoring.md"
USER_TEMPLATE_FILE="$BASE_DIR/user_prompt_template.md"
SPEC_FILE="${1:-$BASE_DIR/spec_example_kv.md}"
OUT_FILE="${2:-$BASE_DIR/generated_grammar.py}"
MODEL="${OLLAMA_MODEL:-gpt-oss:20b}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434/api/chat}"

if [[ ! -f "$SPEC_FILE" ]]; then
  echo "Spec file not found: $SPEC_FILE" >&2
  exit 2
fi

TMP_PAYLOAD="$(mktemp)"
TMP_RESPONSE="$(mktemp)"
trap 'rm -f "$TMP_PAYLOAD" "$TMP_RESPONSE"' EXIT

python - "$SYSTEM_FILE" "$USER_TEMPLATE_FILE" "$SPEC_FILE" "$MODEL" > "$TMP_PAYLOAD" <<'PY'
import json
import pathlib
import sys

system_file = pathlib.Path(sys.argv[1])
user_template_file = pathlib.Path(sys.argv[2])
spec_file = pathlib.Path(sys.argv[3])
model = sys.argv[4]

system_text = system_file.read_text(encoding="utf-8")
user_template = user_template_file.read_text(encoding="utf-8")
spec_text = spec_file.read_text(encoding="utf-8").strip()

user_text = (
	user_template
	.replace("{{SPEC_TEXT}}", spec_text)
	.replace("{{EXAMPLES_TEXT}}", "(none)")
)

payload = {
	"model": model,
	"stream": False,
	"options": {
		"temperature": 0.1
	},
	"messages": [
		{"role": "system", "content": system_text},
		{"role": "user", "content": user_text},
	],
}

print(json.dumps(payload, ensure_ascii=False))
PY

curl -sS "$OLLAMA_URL" \
  -H 'Content-Type: application/json' \
  --data-binary "@$TMP_PAYLOAD" > "$TMP_RESPONSE"

python - "$TMP_RESPONSE" "$OUT_FILE" <<'PY'
import json
import pathlib
import sys

response_path = pathlib.Path(sys.argv[1])
out_path = pathlib.Path(sys.argv[2])

data = json.loads(response_path.read_text(encoding="utf-8"))
content = ((data.get("message") or {}).get("content") or "").strip()

if not content:
	raise SystemExit("No model content returned from Ollama.")

out_path.write_text(content + "\n", encoding="utf-8")
print(f"Wrote grammar to: {out_path}")
PY

echo "Done. You can inspect and run: $OUT_FILE"

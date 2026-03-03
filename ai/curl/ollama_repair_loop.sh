#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEM_FILE="$BASE_DIR/system_regexpp_authoring.md"
REPAIR_TEMPLATE_FILE="$BASE_DIR/repair_prompt_template.md"
SPEC_FILE="${1:-$BASE_DIR/spec_example_kv.md}"
TARGET_FILE="${2:-$BASE_DIR/generated_grammar.py}"
TEST_CMD="${3:-python $BASE_DIR/generated_grammar.py}"
MAX_ROUNDS="${4:-3}"
MODEL="${OLLAMA_MODEL:-gpt-oss:20b}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434/api/chat}"

if [[ ! -f "$SPEC_FILE" ]]; then
  echo "Spec file not found: $SPEC_FILE" >&2
  exit 2
fi

if [[ ! -f "$TARGET_FILE" ]]; then
  echo "Target file not found: $TARGET_FILE" >&2
  echo "Generate it first with: bash ai/curl/ollama_curl_example.sh $SPEC_FILE $TARGET_FILE" >&2
  exit 2
fi

if ! [[ "$MAX_ROUNDS" =~ ^[0-9]+$ ]] || [[ "$MAX_ROUNDS" -lt 1 ]]; then
  echo "MAX_ROUNDS must be a positive integer, got: $MAX_ROUNDS" >&2
  exit 2
fi

TMP_PAYLOAD="$(mktemp)"
TMP_RESPONSE="$(mktemp)"
TMP_TEST_OUT="$(mktemp)"
trap 'rm -f "$TMP_PAYLOAD" "$TMP_RESPONSE" "$TMP_TEST_OUT"' EXIT

for ((round = 1; round <= MAX_ROUNDS; round++)); do
  echo "[repair] Round $round/$MAX_ROUNDS"

  if eval "$TEST_CMD" > "$TMP_TEST_OUT" 2>&1; then
    echo "[repair] Test command passed. No further changes needed."
    cat "$TMP_TEST_OUT"
    exit 0
  fi

  echo "[repair] Test failed. Requesting model fix..."

  python - "$SYSTEM_FILE" "$REPAIR_TEMPLATE_FILE" "$SPEC_FILE" "$TARGET_FILE" "$TEST_CMD" "$TMP_TEST_OUT" "$MODEL" > "$TMP_PAYLOAD" <<'PY'
import json
import pathlib
import sys

system_file = pathlib.Path(sys.argv[1])
repair_template_file = pathlib.Path(sys.argv[2])
spec_file = pathlib.Path(sys.argv[3])
target_file = pathlib.Path(sys.argv[4])
test_cmd = sys.argv[5]
test_out_file = pathlib.Path(sys.argv[6])
model = sys.argv[7]

system_text = system_file.read_text(encoding="utf-8")
repair_template = repair_template_file.read_text(encoding="utf-8")
spec_text = spec_file.read_text(encoding="utf-8").strip()
current_code = target_file.read_text(encoding="utf-8")
failure_output = test_out_file.read_text(encoding="utf-8")[-12000:]

user_text = (
    repair_template
    .replace("{{SPEC_TEXT}}", spec_text)
    .replace("{{CURRENT_CODE}}", current_code)
    .replace("{{TEST_COMMAND}}", test_cmd)
    .replace("{{FAILURE_OUTPUT}}", failure_output)
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

  python - "$TMP_RESPONSE" "$TARGET_FILE" <<'PY'
import json
import pathlib
import re
import sys

response_path = pathlib.Path(sys.argv[1])
target_path = pathlib.Path(sys.argv[2])

data = json.loads(response_path.read_text(encoding="utf-8"))
content = ((data.get("message") or {}).get("content") or "").strip()

if not content:
    raise SystemExit("No model content returned from Ollama.")

match = re.search(r"```(?:python)?\n(.*?)```", content, flags=re.DOTALL)
if match:
    content = match.group(1).strip()

backup = target_path.with_suffix(target_path.suffix + ".bak")
backup.write_text(target_path.read_text(encoding="utf-8"), encoding="utf-8")
target_path.write_text(content + "\n", encoding="utf-8")
print(f"Updated: {target_path}")
print(f"Backup:  {backup}")
PY

done

echo "[repair] Reached max rounds without passing test command."
echo "[repair] Last failure output:"
cat "$TMP_TEST_OUT"
exit 1

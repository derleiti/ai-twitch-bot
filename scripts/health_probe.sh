#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${QWEN_VL_URL:-http://127.0.0.1:8010/v1}"
MODEL="${QWEN_VL_MODEL:-qwen2.5-vl}"

resp="$(curl -s "${BASE_URL}/chat/completions" \
  -H 'Content-Type: application/json' \
  -d "{
    \"model\": \"${MODEL}\",
    \"messages\": [
      {\"role\":\"user\",\"content\":[{\"type\":\"text\",\"text\":\"ping\"}]}
    ]
  }")"

ok="$(printf '%s' "$resp" | jq -er '.choices[0].message.content' 2>/dev/null || true)"
if [[ -n "${ok}" ]]; then
  echo "Qwen-VL OK: $(printf '%s' "$ok" | head -c 120)"
  exit 0
else
  echo "Qwen-VL FAIL: $(printf '%s' "$resp" | head -c 240)" >&2
  exit 1
fi


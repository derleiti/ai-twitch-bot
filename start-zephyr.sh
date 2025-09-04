#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-service}"
BASE_DIR="/root/zephyr"
ENV_FILE="$BASE_DIR/.env"
VENV_BIN="/root/server/bin"          # <- deine venv (source ~/serverbin/activate)
PYTHON="$VENV_BIN/python"
PATH="$VENV_BIN:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"

cd "$BASE_DIR"

# .env exportieren (nur einfache KEY=VALUE Zeilen)
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

echo "🤖 Zephyr Multi-Platform Bot v2.2"
echo "========================================"
if [[ "$MODE" == "service" ]]; then
  echo "🔧 Service-Modus"
fi

# Bytecode-Caches bereinigen (optional, hält Dinge frisch)
find "$BASE_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Sanity: Python existiert?
if [[ ! -x "$PYTHON" ]]; then
  echo "❌ Python nicht gefunden: $PYTHON"
  exit 1
fi

export PATH

# Start
exec "$PYTHON" "$BASE_DIR/zephyr_multi_bot.py"

#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-foreground}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_SCRIPT="$SCRIPT_DIR/zephyr_bot.py"

echo "🤖 Zephyr Bot - Final Edition"
echo "========================================"

# Venv + .env
# Passt sich an verschiedene venv-Pfade an
if [ -d "$SCRIPT_DIR/.venv" ]; then
  source "$SCRIPT_DIR/.venv/bin/activate"
elif [ -d "$SCRIPT_DIR/venv" ]; then
  source "$SCRIPT_DIR/venv/bin/activate"
elif [ -d "/root/server" ]; then
  source /root/server/bin/activate
fi

if [ -f "$SCRIPT_DIR/.env" ]; then
  # dotenv laden, das auch komplexere Werte verarbeiten kann
  export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi
export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"

if [ ! -f "$BOT_SCRIPT" ]; then
    echo "FEHLER: Bot-Skript nicht gefunden unter $BOT_SCRIPT"
    exit 1
fi

if [ "$MODE" = "service" ] || [ "$MODE" = "foreground" ]; then
  echo "▶  Starte im Vordergrund-Modus..."
  exec python3 "$BOT_SCRIPT"
elif [ "$MODE" = "restart-loop" ]; then
  echo "🔁 Starte im Neustart-Loop..."
  while true; do
    python3 "$BOT_SCRIPT" || true
    echo "[start-zephyr] Bot beendet, Neustart in 5 Sekunden..."
    sleep 5
  done
else
  echo "❓ Unbekannter Modus: $MODE"
  exit 2
fi

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Starte Qwen-VL-Server aus dem Verzeichnis: $SCRIPT_DIR"

# Aktiviere die Python Virtual Environment (mit Fallback auf /root/server)
if [ -d "$SCRIPT_DIR/venv" ]; then
  source "$SCRIPT_DIR/venv/bin/activate"
  echo "Lokale 'venv' aktiviert."
elif [ -d "/root/server" ]; then
  source "/root/server/bin/activate"
  echo "'/root/server' venv aktiviert."
else
  echo "WARNUNG: Kein venv gefunden. Versuche, mit dem System-Python zu starten."
fi

# Lade Umgebungsvariablen für die Konfiguration
if [ -f "$SCRIPT_DIR/.env" ]; then
  export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
  echo ".env-Datei geladen."
fi

# Extrahiere Port aus der .env, Fallback auf 8010
PORT=$(echo ${QWEN_VL_BASE_URL:-http://127.0.0.1:8010} | grep -oP ':\K[0-9]+')
echo "Server wird auf Host 0.0.0.0 und Port $PORT gestartet..."

# Starte den Server mit uvicorn
# 'exec' ersetzt den Shell-Prozess, was für systemd sauberer ist.
exec uvicorn qwen_vl_server:app --host 0.0.0.0 --port "$PORT" --app-dir "$SCRIPT_DIR"

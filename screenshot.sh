#!/usr/bin/env bash
set -Eeuo pipefail

# --------- Einstellungen ---------
SERVER="root@ailinux.me"
REMOTE_DIR="/root/zephyr/screenshots"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/screenshots"
TARGET_FILE="$LOCAL_DIR/current_screenshot.jpg"
INTERVAL_SEC=10           # <- ALLE 10 SEKUNDEN
QUALITY=90
MIN_SIZE_BYTES=10240
SSH_OPTS="-o BatchMode=yes -o ConnectTimeout=3 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
LOG_PREFIX="[screenshot.sh]"
# ---------------------------------

mkdir -p "$LOCAL_DIR"

log(){ echo "[$(date '+%F %T')] $LOG_PREFIX $*"; }

# Remote-Verzeichnis vorbereiten (best effort)
ssh $SSH_OPTS "$SERVER" "mkdir -p '$REMOTE_DIR'" >/dev/null 2>&1 || true

# Screenshot-Tool ermitteln
MODE="unknown"; TOOL="unknown"
if [[ "${XDG_SESSION_TYPE:-}" == "wayland" && -n "${WAYLAND_DISPLAY:-}" ]] && command -v grim >/dev/null 2>&1; then
  MODE="wayland"; TOOL="grim"
elif [[ -n "${DISPLAY:-}" ]]; then
  if command -v maim >/dev/null 2>&1; then MODE="x11"; TOOL="maim"
  elif command -v import >/dev/null 2>&1; then MODE="x11"; TOOL="import"; fi
fi

if [[ "$MODE" == "unknown" ]]; then
  log "Kein Screenshot-Tool gefunden (DISPLAY='${DISPLAY:-}', WAYLAND='${WAYLAND_DISPLAY:-}')."
  exit 1
fi
log "Modus: $MODE, Tool: $TOOL, Intervall: ${INTERVAL_SEC}s"

trap 'log "Beende (Signal gefangen)."; exit 0' INT TERM

i=0
while true; do
  i=$((i+1))
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  tmp_local="${LOCAL_DIR}/.current_screenshot.jpg.tmp"
  remote_tmp="${REMOTE_DIR}/.current_screenshot.jpg.tmp"
  remote_final="${REMOTE_DIR}/current_screenshot.jpg"

  # --- Aufnahme ---
  if [[ "$TOOL" == "maim" ]]; then
    # WICHTIG: Format explizit auf JPG setzen (Fix für „Unknown format type: tmp“)
    if ! maim -u -m 10 -f jpg "$tmp_local"; then
      log "$ts Aufnahme fehlgeschlagen (maim)"
      rm -f "$tmp_local" 2>/dev/null || true
      sleep "$INTERVAL_SEC"; continue
    fi
    command -v jpegoptim >/dev/null 2>&1 && jpegoptim --max="$QUALITY" --strip-all -q "$tmp_local" || true
  elif [[ "$TOOL" == "grim" ]]; then
    if ! grim -t jpeg -q "$QUALITY" "$tmp_local"; then
      log "$ts Aufnahme fehlgeschlagen (grim)"
      rm -f "$tmp_local" 2>/dev/null || true
      sleep "$INTERVAL_SEC"; continue
    fi
  else
    # ImageMagick-Import
    if ! import -window root jpg:- > "$tmp_local"; then
      log "$ts Aufnahme fehlgeschlagen (import)"
      rm -f "$tmp_local" 2>/dev/null || true
      sleep "$INTERVAL_SEC"; continue
    fi
  fi

  # --- Plausibilitätscheck ---
  sz=$(stat -c %s "$tmp_local" 2>/dev/null || echo 0)
  if (( sz < MIN_SIZE_BYTES )); then
    log "$ts -> Bild zu klein (${sz} B), verwerfe."
    rm -f "$tmp_local"
    sleep "$INTERVAL_SEC"; continue
  fi

  # --- lokal „current“ aktualisieren ---
  mv -f "$tmp_local" "$TARGET_FILE"

  # --- Upload & atomar umbenennen ---
  if scp $SSH_OPTS "$TARGET_FILE" "$SERVER:$remote_tmp" >/dev/null 2>&1; then
    ssh $SSH_OPTS "$SERVER" "mv -f '$remote_tmp' '$remote_final'" || log "$ts -> Upload ok, Remote-rename FEHLER"
    log "$ts -> Erfolgreich übertragen (#$i)"
  else
    log "$ts -> Upload fehlgeschlagen (SSH/Netz?)"
  fi

  sleep "$INTERVAL_SEC"
done

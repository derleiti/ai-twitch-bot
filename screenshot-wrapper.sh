#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/screenshot-wrapper.log"
log(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG_FILE"; }

# Desktop-User bestimmen (Wayland/X11)
DESKTOP_USER="$(loginctl list-sessions --no-legend 2>/dev/null \
  | while read -r sid user seat rest; do
      t="$(loginctl show-session "$sid" -p Type --value 2>/dev/null || true)"
      [[ "$t" == "x11" || "$t" == "wayland" ]] && { echo "$user"; break; }
    done)"
[[ -z "$DESKTOP_USER" ]] && DESKTOP_USER="$(id -un)"

UID_NUM="$(id -u "$DESKTOP_USER" 2>/dev/null || echo 1000)"
export XDG_RUNTIME_DIR="/run/user/$UID_NUM"

# Sessionvariablen übernehmen
getenv_from_pid(){ local pid="$1" var="$2"; [[ -r "/proc/$pid/environ" ]] || return 1; tr '\0' '\n' <"/proc/$pid/environ" | awk -F= -v k="$var" '$1==k { $1=""; sub(/^=/,""); print; exit }'; }
adopt_env_from_pid(){ local pid="$1"; for v in DISPLAY WAYLAND_DISPLAY XDG_SESSION_TYPE DBUS_SESSION_BUS_ADDRESS XAUTHORITY; do val="$(getenv_from_pid "$pid" "$v" || true)"; [[ -n "$val" ]] && export "$v"="$val"; done; }

SID="$(loginctl list-sessions --no-legend 2>/dev/null | awk -v u="$DESKTOP_USER" '$3==u {print $1; exit}')"
if [[ -n "$SID" ]]; then
  LEADER="$(loginctl show-session "$SID" -p Leader --value 2>/dev/null || true)"
  [[ -n "$LEADER" ]] && adopt_env_from_pid "$LEADER"
fi

[[ -z "${DISPLAY:-}" && -S /tmp/.X11-unix/X0 ]] && export DISPLAY=:0
[[ -z "${WAYLAND_DISPLAY:-}" && -S "$XDG_RUNTIME_DIR/wayland-0" ]] && export WAYLAND_DISPLAY=wayland-0
if [[ -z "${XDG_SESSION_TYPE:-}" ]]; then
  [[ -n "${DISPLAY:-}" ]] && export XDG_SESSION_TYPE=x11
  [[ -n "${WAYLAND_DISPLAY:-}" ]] && export XDG_SESSION_TYPE=wayland
fi
[[ -z "${DBUS_SESSION_BUS_ADDRESS:-}" && -S "$XDG_RUNTIME_DIR/bus" ]] && export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"

log "Session-Erkennung (Desktop-User: $DESKTOP_USER)"
log "  XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR"
log "  DISPLAY=${DISPLAY:-unset}"
log "  WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-unset}"
log "  XDG_SESSION_TYPE=${XDG_SESSION_TYPE:-unset}"
log "  DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-unset}"
log "  XAUTHORITY=${XAUTHORITY:-unset}"

# Einmaliger Start – das Endlosskript beendet sich NICHT
exec bash "$SCRIPT_DIR/screenshot.sh" 2>&1 | tee -a "$LOG_FILE"

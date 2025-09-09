#!/usr/bin/env bash
set -euo pipefail
echo "=== Zephyr Diag $(date) ==="

echo "[1] Port-Check :8010"
ss -ltnp | grep -E '(:8010 )' || echo "kein Listener auf :8010"
echo

echo "[2] Service-Status qwen-vl-server"
systemctl --no-pager -l status qwen-vl-server.service | sed -n '1,40p' || true
echo

echo "[3] Health-Probe (text -> parts)"
bash "$(dirname "$0")/health_probe.sh" || true
echo

echo "[4] zephyrbot .env & Exec"
systemctl show zephyrbot.service | grep -E 'Environment=|ExecStart=' || true
echo

echo "[5] Letzte Logs zephyrbot (80 Zeilen)"
journalctl -xeu zephyrbot.service -n 80 --no-pager || true
echo

echo "=== Ende ==="

# --- Systemd-Hinweis (nur Kommentar, nicht ausführen) ---
# In /etc/systemd/system/zephyrbot.service sollte stehen:
# EnvironmentFile=/root/zephyr/.env
# Danach bei manuellen Änderungen:
# systemctl daemon-reload
# systemctl restart zephyrbot.service


#!/usr/bin/env bash
set -euo pipefail

echo "[1/4] daemon-reload"
sudo systemctl daemon-reload

echo "[2/4] restart qwen-vl-server"
sudo systemctl restart qwen-vl-server.service
sudo systemctl --no-pager -l status qwen-vl-server.service | sed -n '1,20p'

echo "[2.1] qwen smoke-test"
curl -s http://127.0.0.1:8010/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen2.5-vl","messages":[{"role":"user","content":[{"type":"text","text":"ping"}]}]}' \
  | head -c 200 || true; echo

echo "[3/4] restart zephyrbot"
sudo systemctl restart zephyrbot.service

echo "[4/4] tail zephyrbot logs (Ctrl+C beendet)"
journalctl -xeu zephyrbot.service -n 200 -f

#!/usr/bin/env bash
set -euo pipefail
TS="$(date -Is)"; OUT="logs/zephyr_debug_bundle_${TS//:/-}.txt"
mkdir -p logs
{
  echo "=== ZEITSTEMPEL ${TS} ==="
  echo "=== journalctl qwen-vl-server (letzte 1000) ==="
  journalctl -u qwen-vl-server.service -o short-iso -n 1000
  echo
  echo "=== journalctl zephyrbot (letzte 1000) ==="
  journalctl -u zephyrbot.service -o short-iso -n 1000
  echo
  for f in stream_recap.txt /var/log/zephyr/stream_recap.log; do
    [ -f "$f" ] && { echo "=== $f (letzte 400) ==="; tail -n 400 "$f"; echo; }
  done
} | sed -E \
    -e 's/(oauth:)[^ ]+/\1***REDACTED***/gI' \
    -e 's/(Authorization:)[^\r\n]+/\1 ***REDACTED***/gI' \
    -e 's/(sk-)[A-Za-z0-9_-]+/\1REDACTED/g' \
    -e 's/((token|key|password|oauth|auth)=)[^& ]+/\1REDACTED/gI' \
    > "$OUT"
echo "Bundle bereit: $OUT"

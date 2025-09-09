#!/usr/bin/env bash
set -euo pipefail
dir="${ZEPHYR_SCREENSHOT_DIR:-/root/zephyr/screenshots}"
target="${ZEPHYR_SCREENSHOT_TARGET:-$dir/current_screenshot.jpg}"
mkdir -p "$dir"
# shellcheck disable=SC2012
latest=$(ls -1t "$dir"/*.{jpg,png} 2>/dev/null | head -n1 || true)
if [[ -n "${latest:-}" ]]; then
  ln -sf "$latest" "$target"
  echo "Linked: $latest -> $target"
else
  echo "No screenshots found in $dir" >&2
  exit 2
fi

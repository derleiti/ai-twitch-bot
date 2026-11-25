#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
# Explicitly started for streaming; never enabled at login.
# Refuse changed monitor geometry rather than accidentally transmitting the second monitor.
remote=${ZEPHYR_SSH_TARGET:?Configure ZEPHYR_SSH_TARGET first}
[[ "$remote" != -* ]] || exit 2
interval=${ZEPHYR_CAPTURE_INTERVAL:-30}
d=$(mktemp -d "${XDG_RUNTIME_DIR}/zephyr-capture.XXXXXX")
trap 'rm -rf -- "$d"' EXIT
while true; do
  rm -f "$d/full.png" "$d/frame.jpg"
  if timeout 12 spectacle -b -n -f -o "$d/full.png"; then
    for i in {1..20}; do [[ -s "$d/full.png" ]] && break; sleep .2; done
    geometry=$(kscreen-doctor -o | sed -E 's/\x1b\[[0-9;]*m//g')
    if [[ $(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$d/full.png" 2>/dev/null) == 4480,1440 ]] && grep -q 'Geometry: 0,0 2560x1440' <<< "$geometry" && grep -q 'Geometry: 2560,182 1920x1080' <<< "$geometry"; then
      if ffmpeg -nostdin -v error -i "$d/full.png" -vf 'crop=2560:1440:0:0,scale=1280:720' -frames:v 1 -q:v 4 "$d/frame.jpg"; then
        rm -f "$d/full.png"
        if timeout 15 ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=5 -- "$remote" 'umask 077; set -eu; d=$HOME/.local/state/zephyr/frames; mkdir -p "$d"; t=$(mktemp "$d/.frame.XXXXXX"); trap '\''rm -f "$t"'\'' EXIT; cat > "$t"; test -s "$t"; mv -f "$t" "$d/current_screenshot.jpg"' < "$d/frame.jpg"; then echo 'Primary monitor frame uploaded'; else echo 'SSH upload failed' >&2; fi
      fi
    else echo 'Unexpected monitor geometry or invalid capture; skipped' >&2; fi
  else echo 'Spectacle failed; skipped' >&2; fi
  rm -f "$d/full.png" "$d/frame.jpg"
  sleep "$interval"
done

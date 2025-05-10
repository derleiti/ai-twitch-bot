#!/bin/bash

SERVER="root@derleiti.de"
TARGET_DIR="/root/zephyr/screenshots"

while true; do
  TIMESTAMP=$(date +%s)
  IMG="/tmp/stream_${TIMESTAMP}.jpg"

  ffmpeg -y -f x11grab -video_size 1920x1080 -i :0.0 -vframes 1 "$IMG" \
    >/dev/null 2>&1

  scp -q "$IMG" "$SERVER:$TARGET_DIR/"
  rm -f "$IMG"
  sleep 5
done

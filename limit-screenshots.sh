#!/bin/bash

DIR="$HOME/zephyr/screenshots"
MAX=100

cd "$DIR" || exit

FILES=($(ls -1t *.jpg 2>/dev/null))

if [ ${#FILES[@]} -gt $MAX ]; then
  DELETE=("${FILES[@]:$MAX}")
  for f in "${DELETE[@]}"; do
    rm -f "$f"
  done
fi

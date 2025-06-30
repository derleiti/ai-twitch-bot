#!/usr/bin/env python3
import os
import time
import subprocess

SCREENSHOT_DIR = "/root/zephyr/screenshots"
MAX_FILES = 100
INTERVAL = 5  # Sekunden

def take_screenshot():
    timestamp = int(time.time())
    path = os.path.join(SCREENSHOT_DIR, f"screen_{timestamp}.jpg")
    subprocess.run(["ffmpeg", "-y", "-f", "x11grab", "-video_size", "1920x1080", "-i", ":0.0", "-vframes", "1", path],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return path

def cleanup_old_files():
    files = sorted([f for f in os.listdir(SCREENSHOT_DIR) if f.endswith(".jpg")])
    while len(files) > MAX_FILES:
        old = files.pop(0)
        os.remove(os.path.join(SCREENSHOT_DIR, old))

def main():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    while True:
        take_screenshot()
        cleanup_old_files()
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()

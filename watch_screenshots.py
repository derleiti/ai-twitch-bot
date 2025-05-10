#!/usr/bin/env python3
import time
import os
from analyze_and_respond import analyze_and_comment
from twitch_ollama_bot import send_message

SCREENSHOT_DIR = os.path.expanduser("~/zephyr/screenshots")
SEEN_FILES = set()

def handle_new_file(file_path):
    print(f"📸 Neues Bild erkannt: {file_path}")
    result = analyze_and_comment(file_path)
    if result:
        send_message(f"👁️ {result[:450]}")
    else:
        print("⚠️ Analyse oder Antwort fehlgeschlagen.")

def main():
    print("👁️ Warte auf neue Screenshots...")
    while True:
        try:
            files = sorted(os.listdir(SCREENSHOT_DIR))
            for f in files:
                full_path = os.path.join(SCREENSHOT_DIR, f)
                if f.endswith(".jpg") and full_path not in SEEN_FILES:
                    SEEN_FILES.add(full_path)
                    handle_new_file(full_path)
            time.sleep(3)
        except KeyboardInterrupt:
            print("\n⛔ Beendet.")
            break
        except Exception as e:
            print(f"❌ Fehler: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()

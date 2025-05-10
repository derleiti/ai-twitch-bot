#!/usr/bin/env python3
import os
import json
from datetime import datetime

LOG_FILE = os.path.expanduser("~/zephyr/vision_log.jsonl")

def log_vision_example(image_path, vision_text, user_feedback=None):
    data = {
        "timestamp": datetime.now().isoformat(),
        "image_path": image_path,
        "vision": vision_text,
        "feedback": user_feedback or ""
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(data) + "\n")
    print("📥 Vision-Log gespeichert.")

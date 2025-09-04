# -*- coding: utf-8 -*-
import json
import os
import time
import glob
import pathlib

from vision_summarizer import summarize_image
from commentary_engine import make_comment

BASE = pathlib.Path(__file__).resolve().parent
LATEST_VISION = BASE / "latest_vision.txt"
LATEST_COMMENT = BASE / "latest_comment.txt"
GAME_STATE = BASE / "game_state.json"

def latest_screenshot(folder: str) -> str:
    imgs = []
    for ext in ("*.png","*.jpg","*.jpeg","*.webp"):
        imgs += glob.glob(os.path.join(folder, ext))
    if not imgs:
        return ""
    return max(imgs, key=os.path.getmtime)

def main():
    folder = os.environ.get("SCREENSHOT_DIR", str(BASE))
    img = latest_screenshot(folder)
    if not img:
        print("no screenshot found")
        return

    vision = summarize_image(img)
    LATEST_VISION.write_text(json.dumps(vision, ensure_ascii=False, indent=2))

    try:
        gs = json.loads(GAME_STATE.read_text())
    except Exception:
        gs = {}

    out = make_comment(vision, gs)
    LATEST_COMMENT.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(out.get("short_chat",""))

if __name__ == "__main__":
    main()

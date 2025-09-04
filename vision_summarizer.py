# -*- coding: utf-8 -*-
import base64
import json
import os
from typing import Dict, Any, List

import requests
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
VLM_MODEL  = os.getenv("VLM_MODEL", "llava:latest")
OCR_ENABLE = os.getenv("OCR_ENABLE", "0") == "1"

SYSTEM_PROMPT = (
    "You are ScreenSummarizer v1. Describe exactly what is visible in a single PC game screenshot.\n"
    "HARD RULES:\n"
    "- Do NOT guess the game, genre, location or lore unless clearly printed on-screen. If unknown, write 'unknown'.\n"
    "- Only mention elements clearly visible.\n"
    "- Capture HUD/UI numbers (hp, mana, resources), minimap hints, quest trackers, warnings, timers.\n"
    "- List on-screen text (menus, tooltips, chat lines). If none, put [].\n"
    "- Name key entities (player, ally, enemy, boss, npc) & their states if SHOWN (hp %, buffs, debuffs, cast bars). "
    "  If not visible, use 'unknown'.\n"
    "- Output strictly valid JSON (no markdown, no code fences). Keys:\n"
    "{ 'scene': str, 'ui': { 'hp': str?, 'mana': str?, 'resources': str?, 'minimap': str?, 'quest': str? },"
    "  'entities': [ { 'type': 'player|ally|enemy|boss|npc', 'name': str?, 'lvl': str?, 'state': str? } ],"
    "  'text': [str], 'notable': [str] }"
)

def _b64_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def _ocr_text(path: str) -> List[str]:
    if not OCR_ENABLE:
        return []
    try:
        import pytesseract
        # Falls nötig: pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
        img = Image.open(path)
        text = pytesseract.image_to_string(img)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return lines[:50]
    except Exception:
        return []

def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        # entferne erste fence-Zeile (``` oder ```json)
        s = "\n".join(s.splitlines()[1:])
        # ggf. schließendes ``` entfernen
        if s.endswith("```"):
            s = "\n".join(s.splitlines()[:-1])
    return s.strip()

def summarize_image(path: str) -> Dict[str, Any]:
    images = [_b64_image(path)]
    payload = {
        "model": VLM_MODEL,
        "stream": False,
        "options": {"temperature": 0.0, "top_p": 0.1},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Return only the JSON object.", "images": images},
        ],
    }
    resp = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=120)
    resp.raise_for_status()
    raw = resp.json().get("message", {}).get("content", "").strip()

    txt = _strip_code_fences(raw)

    # OCR-Merge (HUD-Zahlen ergänzen)
    ocr = _ocr_text(path)
    try:
        data = json.loads(txt)
        if ocr:
            data.setdefault("text", [])
            data["text"] = list(dict.fromkeys(data["text"] + ocr))[:100]
        # Sanity-Defaults
        data.setdefault("scene", "")
        data.setdefault("ui", {})
        data.setdefault("entities", [])
        data.setdefault("text", [])
        data.setdefault("notable", [])
        return data
    except Exception:
        # Fallback, falls Modell doch Prosa geliefert hat
        fallback = {"scene": "", "ui": {}, "entities": [], "text": [txt], "notable": []}
        if ocr:
            fallback["text"] += ocr
        return fallback

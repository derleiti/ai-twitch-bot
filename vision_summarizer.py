# -*- coding: utf-8 -*-
import base64
import json
import os
from typing import Dict, Any, List

import requests
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
VLM_MODEL  = os.getenv("VLM_MODEL", "qwen2.5-vl:7b-instruct")
OCR_ENABLE = os.getenv("OCR_ENABLE", "0") == "1"

SYSTEM_PROMPT = (
    "You are ScreenSummarizer v1. Describe exactly what is visible in a single PC game screenshot.\n"
    "HARD RULES:\n"
    "- Do NOT guess the game, genre, location or lore unless clearly printed on-screen. If unknown, write 'unknown'.\n"
    "- Only mention elements clearly visible.\n"
    "- Capture HUD/UI numbers (hp, mana, resources), minimap hints, quest trackers, warnings, timers.\n"
    "- List on-screen text (menus, tooltips, chat lines). If none, put [].\n"
    "- Name key entities (player, ally, enemy, boss, npc) & their states if SHOWN (hp %, buffs, debuffs, cast bars). If not visible, use 'unknown'.\n"
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
        img = Image.open(path)
        text = pytesseract.image_to_string(img)
        lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        return lines[:100]
    except Exception:
        return []

def _strip_code_fences(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("```"):
        s = "\n".join(s.splitlines()[1:])
        if s.endswith("```"):
            s = "\n".join(s.splitlines()[:-1])
    return s.strip()

def _call_ollama_chat(images_b64: List[str]) -> str:
    url = f"{OLLAMA_URL}/api/chat"
    payload = {
        "model": VLM_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Return only the JSON object.", "images": images_b64},
        ],
        "options": {"temperature": 0.0, "top_p": 0.1},
    }
    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    return r.json().get("message", {}).get("content", "").strip()

def _call_ollama_generate(images_b64: List[str]) -> str:
    url = f"{OLLAMA_URL}/api/generate"
    prompt = (
        SYSTEM_PROMPT
        + "\nReturn only the JSON object for the given image(s). If multiple, treat them as one combined screen."
    )
    payload = {
        "model": VLM_MODEL,
        "stream": False,
        "prompt": prompt,
        "images": images_b64,
        "options": {"temperature": 0.0, "top_p": 0.1},
    }
    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    j = r.json()
    return (j.get("response") or j.get("message", {}).get("content", "")).strip()

def summarize_image(path: str) -> Dict[str, Any]:
    images = [_b64_image(path)]
    # 1) Versuche /api/chat
    try:
        raw = _call_ollama_chat(images)
    except requests.HTTPError as e:
        # 404 -> ältere Ollama-Version: auf /api/generate ausweichen
        if getattr(e.response, "status_code", None) == 404:
            raw = _call_ollama_generate(images)
        else:
            raise
    except Exception:
        # Netzwerk/sonstiges -> Fallback
        raw = _call_ollama_generate(images)

    txt = _strip_code_fences(raw)

    # OCR-Merge (HUD-Zahlen ergänzen)
    ocr = _ocr_text(path)
    try:
        data = json.loads(txt)
        if isinstance(data, dict):
            data.setdefault("scene", "")
            data.setdefault("ui", {})
            data.setdefault("entities", [])
            data.setdefault("text", [])
            data.setdefault("notable", [])
            if ocr:
                data["text"] = list(dict.fromkeys((data.get("text") or []) + ocr))[:100]
            return data
    except Exception:
        pass

    # Fallback (falls Modell Prosa geliefert hat)
    fallback = {"scene": "", "ui": {}, "entities": [], "text": [txt], "notable": []}
    if ocr:
        fallback["text"] += ocr
    return fallback

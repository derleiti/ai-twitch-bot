# -*- coding: utf-8 -*-
"""
Qwen-VL local bridge client (OpenAI-compatible /v1/chat/completions)

Design goals:
- Use data URI for images to avoid file path issues
- Keep payload minimal (some bridges 500 on 'response_format' or aggressive system prompts)
- Return raw assistant 'content' as str; caller handles JSON parsing and schema
"""

from __future__ import annotations
import os
import json
import base64
import mimetypes
import urllib.request
import urllib.error
from typing import Optional

# Base URL and model from env
QWEN_BASE = os.getenv("QWEN_BASE", "http://127.0.0.1:8010/v1")
QWEN_MODEL_VL = os.getenv("QWEN_VISION_MODEL", "qwen2.5-vl")

# Tuning knobs
QWEN_TIMEOUT = float(os.getenv("QWEN_TIMEOUT", "30"))
QWEN_TEMPERATURE = float(os.getenv("QWEN_TEMPERATURE", "0.1"))
QWEN_MAX_TOKENS = int(os.getenv("QWEN_MAX_TOKENS", "256"))

# Vision language (de|en); default "de" to preserve current behavior
_VISION_LANG_RAW = (os.getenv("VISION_LANG") or "de").strip().lower()
if _VISION_LANG_RAW.startswith("en"):
    VISION_LANG = "en"
elif _VISION_LANG_RAW.startswith("de") or _VISION_LANG_RAW == "german":
    VISION_LANG = "de"
else:
    # Fallback to German on unknown values
    VISION_LANG = "de"

# If your bridge safely supports response_format json_object, set this to "1"
QWEN_STRICT_JSON = os.getenv("QWEN_STRICT_JSON", "0") in ("1", "true", "TRUE")


def _guess_mime(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    if not mime:
        # default to jpeg; many screenshots are jpg/png
        ext = os.path.splitext(path)[1].lower()
        if ext in (".png",):
            return "image/png"
        return "image/jpeg"
    return mime


def analyze_image(image_path: str) -> Optional[str]:
    """
    Read an image, build a minimal OpenAI-compatible payload, and call the bridge.

    Returns:
        assistant 'content' string on success
        None on error
    """
    if not os.path.exists(image_path):
        return None

    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return None

    mime = _guess_mime(image_path)
    data_uri = f"data:{mime};base64,{b64}"

    # Minimal prompt – let downstream enforce JSON strictly; language via VISION_LANG
    if VISION_LANG == "en":
        user_text = (
            "Briefly analyze the image. "
            "If possible, reply as a JSON object with fields hp, objects, details. "
            "objects is a list of {label, confidence, details}."
        )
    else:
        user_text = (
            "Analysiere das Bild kurz. "
            "Wenn möglich, antworte als JSON-Objekt mit Feldern hp, objects, details. "
            "objects ist eine Liste mit {label, confidence, details}."
        )

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        }
    ]

    payload = {
        "model": QWEN_MODEL_VL,
        "messages": messages,
        "temperature": QWEN_TEMPERATURE,
        "max_tokens": QWEN_MAX_TOKENS,
    }

    # Some bridges 500 on response_format; enable only if explicitly allowed
    if QWEN_STRICT_JSON:
        payload["response_format"] = {"type": "json_object"}

    req = urllib.request.Request(
        f"{QWEN_BASE}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=QWEN_TIMEOUT) as r:
            body = r.read().decode("utf-8")
            data = json.loads(body)
            # Return raw content; caller will parse/normalize
            return data["choices"][0]["message"]["content"]
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError):
        return None

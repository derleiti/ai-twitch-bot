# -*- coding: utf-8 -*-
"""
Vision Summarizer for Zephyrbot

- Robust JSON extraction from model output (balanced braces, codefence tolerant)
- Schema normalization to {hp, objects, details}
- Atomic-friendly screenshot reading with size guard
- Backoff with jitter to avoid collisions with writer cadence
- Detailed debug logging (file size, mtime, md5)

This module depends on qwen_client.analyze_image(image_path) returning either:
- str  -> free-form model content (we will parse JSON from it)
- dict -> already parsed JSON (we will normalize schema)
- None -> on error
"""

from __future__ import annotations
import os
import subprocess
import time
import json
import random
import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

# Local client
import qwen_client

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("vision_summarizer")

# Screenshot path; allow override via systemd Environment or .env
# Use .jpg as canonical; other extensions are dummies
DEFAULT_SCREENSHOT = "/root/zephyr/screenshots/current_screenshot.jpg"
SCREENSHOT_FILE = os.getenv("SCREENSHOT_FILE", DEFAULT_SCREENSHOT)

# Minimal bytes required to consider the screenshot valid (avoid 0B / tiny tmp)
MIN_BYTES = int(os.getenv("ZEPHYR_VISION_MIN_BYTES", "10240"))  # 10 KB default

# Backoff between vision attempts when upstream not ready
BACKOFF_SEC = float(os.getenv("ZEPHYR_VISION_BACKOFF_SEC", "20"))
JITTER_SEC = float(os.getenv("ZEPHYR_VISION_JITTER_SEC", "5"))

# Max length for raw log preview
RAW_PREVIEW = 400


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _md5sum(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_first_json_object(s: str) -> Optional[Dict[str, Any]]:
    """
    Extract the first valid JSON object from a possibly chatty string.

    Strategy:
      1) Try direct json.loads
      2) Strip codefences ```(json)? ... ```
      3) Balanced-brace scan with string/escape awareness
    """
    if not s:
        return None

    # 1) direct
    try:
        return json.loads(s)
    except Exception:
        pass

    # 2) remove codefences gently
    s2 = s.replace("```json", "```").replace("```", "")

    # 3) balanced-brace scan
    depth = 0
    start = -1
    in_str = False
    esc = False

    for i, ch in enumerate(s2):
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            continue

        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            if depth > 0:
                depth -= 1
                if depth == 0 and start != -1:
                    cand = s2[start:i + 1]
                    try:
                        return json.loads(cand)
                    except Exception:
                        start = -1  # continue scanning

    return None


def _normalize_hp_schema(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize to {hp, objects, details}
      - hp: Optional[str]
      - objects: List[{label:str, confidence:float, details:str}]
      - details: Optional[str]
    Also accept alternative keys {scene, ui, action} and map them.
    """
    # Accept scene/ui/action and map to our schema for compatibility
    if "scene" in data or "ui" in data or "action" in data:
        scene = str(data.get("scene", "") or "")
        ui = str(data.get("ui", "") or "")
        action = str(data.get("action", "") or "")
        mapped = {
            "hp": scene if scene else None,
            "objects": [],
            "details": f"{ui} {('· ' + action) if action else ''}".strip() or None,
        }
        data = mapped

    hp = data.get("hp")
    details = data.get("details")
    objects = data.get("objects", [])

    # Types & defaults
    hp = None if hp in ("", None) else str(hp)
    details = None if details in ("", None) else str(details)

    norm_objects: List[Dict[str, Any]] = []
    if isinstance(objects, list):
        for o in objects:
            if not isinstance(o, dict):
                continue
            label = str(o.get("label", "") or "")
            # confidence can be str or number; coerce to float range [0,1] if possible
            conf_raw = o.get("confidence", None)
            try:
                confidence = float(conf_raw)
            except Exception:
                confidence = None
            if confidence is not None:
                if confidence < 0:
                    confidence = 0.0
                if confidence > 1:
                    confidence = 1.0
            details_o = o.get("details", None)
            details_o = None if details_o in ("", None) else str(details_o)
            norm_objects.append({
                "label": label,
                "confidence": confidence,
                "details": details_o
            })

    return {
        "hp": hp,
        "objects": norm_objects,
        "details": details
    }


def _valid_screenshot(path: str) -> Tuple[bool, Optional[str]]:
    # Kurzfristige Race-Condition abfedern (Writer ersetzt Datei atomar)
    for attempt in range(5):
        if not os.path.exists(path):
            time.sleep(0.15)
            continue
        try:
            st = os.stat(path)
        except Exception as e:
            if attempt < 4:
                time.sleep(0.15)
                continue
            return False, f"stat() fehlgeschlagen: {e}"

        if st.st_size < MIN_BYTES:
            if attempt < 4:
                time.sleep(0.20)
                continue
            return False, f"Screenshot zu klein ({st.st_size} Bytes < {MIN_BYTES})."

        return True, None
    return False, f"Bild nicht gefunden: {path}"


def _sleep_backoff():
    dt = BACKOFF_SEC + random.uniform(0.0, max(0.0, JITTER_SEC))
    time.sleep(dt)


# -----------------------------------------------------------------------------
# Public entry points
# -----------------------------------------------------------------------------

def get_vision_comment(image_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Read screenshot, call local vision model via qwen_client, parse & normalize.

    Returns:
        dict with keys {hp, objects, details} or None on failure.
    """
    path = image_path or SCREENSHOT_FILE
    # Try sibling extensions before validation (handles .jpg/.jpeg/.png swaps)
    try:
        def _pick_sibling(pth: str) -> Optional[str]:
            base, ext = os.path.splitext(pth)
            # prefer jpg -> jpeg -> png (or reverse when given png)
            ext_order = [".jpg", ".jpeg", ".png"]
            # rotate so the current ext is first, then try others
            ext_l = ext.lower()
            if ext_l in ext_order:
                order = [ext_l] + [e for e in ext_order if e != ext_l]
            else:
                order = ext_order
            for e in order:
                cand = base + e
                if os.path.exists(cand):
                    ok, _ = _valid_screenshot(cand)
                    if ok:
                        return cand
            return None

        sib = _pick_sibling(path) if not os.path.exists(path) else None
        if sib and sib != path:
            logger.debug("[VISION] primärer Pfad fehlt, weiche auf Sibling aus: %s", sib)
            path = sib
    except Exception:
        pass

    logger.debug("[VISION] pre-check exists=%s path=%s ENV SCREENSHOT_FILE=%r",
                 os.path.exists(path), path, os.getenv("SCREENSHOT_FILE"))
    ok, err = _valid_screenshot(path)
    if not ok:
        # Sibling retry also when file exists but is invalid (e.g., 0B tmp)
        try:
            sib2 = _pick_sibling(path)  # type: ignore[name-defined]
            if sib2 and sib2 != path:
                logger.debug("[VISION] Datei ungültig, Sibling-Retry: %s", sib2)
                path = sib2
                ok, err = _valid_screenshot(path)
        except Exception:
            pass

    if not ok:
        # Fallback: try most recent screenshot from ring buffer if available
        try:
            from screenshots.screenshot_manager import latest as _latest
            rec = _latest()
            if rec and isinstance(rec, dict):
                alt_path = rec.get("path")
                if alt_path and alt_path != path and os.path.exists(alt_path):
                    alt_ok, _ = _valid_screenshot(alt_path)
                    if alt_ok:
                        logger.debug("[VISION] Fallback auf Ringpuffer: %s", alt_path)
                        path = alt_path
                        ok = True
        except Exception:
            pass

    if not ok:
        logger.error("[vision_summarizer] %s", err)
        _sleep_backoff()
        return None

    # Log file meta for clear diagnosis
    try:
        st = os.stat(path)
        md5 = _md5sum(path)
        logger.debug("[VISION] read file size=%dB mtime=%.0f md5=%s path=%s",
                     st.st_size, st.st_mtime, md5, path)
    except Exception as e:
        logger.error("[vision_summarizer] Konnte Datei-Metadaten nicht lesen: %s", e)
        _sleep_backoff()
        return None

    # Extra diag: stat via system tool to capture ownership/size in journal
    try:
        st_line = subprocess.check_output([
            "/usr/bin/stat", "-c", "%n %sB %U:%G", path
        ], timeout=2).decode().strip()
        logger.debug("[VISION] stat: %s | ENV SCREENSHOT_FILE=%r", st_line, os.getenv("SCREENSHOT_FILE"))
    except Exception as e:
        logger.debug("[VISION] stat failed for %r: %r | ENV=%r", path, e, os.getenv("SCREENSHOT_FILE"))

    # Call model
    try:
        raw = qwen_client.analyze_image(image_path=path)
    except Exception as e:
        logger.exception("[vision_summarizer] analyze_image() Exception: %s", e)
        _sleep_backoff()
        return None

    if raw is None:
        logger.debug("Vision-Ergebnis leer/None (Upstream nicht bereit oder Fehler).")
        _sleep_backoff()
        return None

    # Parse
    if isinstance(raw, dict):
        data = _normalize_hp_schema(raw)
        return data

    if isinstance(raw, str):
        parsed = _extract_first_json_object(raw)
        if not parsed:
            # Fallback: liefere minimalen Inhalt als details, damit der Bot posten kann
            try:
                s = raw.replace("```json", "```").replace("```", " ")
                s = " ".join(s.split())
                # allow richer fallback details; clamp later for Twitch
                MAX_FALLBACK = int(os.getenv("VISION_FALLBACK_MAX_CHARS", "420"))
                if len(s) > MAX_FALLBACK:
                    s = s[:MAX_FALLBACK].rstrip(" .,:;-") + "…"
                fallback = {"hp": None, "objects": [], "details": s}
                logger.warning("[vision_summarizer] Keine gültige JSON-Antwort. Fallback-Details verwendet. Raw (gekürzt): %s",
                               raw[:RAW_PREVIEW])
                return fallback
            except Exception:
                logger.warning("[vision_summarizer] Keine gültige JSON-Antwort. Raw (gekürzt): %s",
                               raw[:RAW_PREVIEW])
                _sleep_backoff()
                return None
        data = _normalize_hp_schema(parsed)
        return data

    logger.warning("[vision_summarizer] Unerwarteter Modell-Output-Typ: %r", type(raw))
    _sleep_backoff()
    return None


def summarize_image(image_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Backwards-compatible alias used by zephyr_bot.
    Returns normalized dict {hp, objects, details} or None.
    """
    return get_vision_comment(image_path)


def ask_image_question(image_path: str, question: str) -> Optional[str]:
    """
    Ask a free-form question about an image via the local Qwen-VL bridge.
    Returns the assistant content as a string, or None on error.
    """
    try:
        if not os.path.exists(image_path):
            logger.error("[vision_summarizer] Bild nicht gefunden: %s", image_path)
            return None

        # Build data URI using same mimetype logic as qwen_client
        import base64, mimetypes, json as _json, urllib.request as _ur

        mime, _ = mimetypes.guess_type(image_path)
        if not mime:
            ext = os.path.splitext(image_path)[1].lower()
            if ext == ".png":
                mime = "image/png"
            else:
                mime = "image/jpeg"
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        data_uri = f"data:{mime};base64,{b64}"

        # Language toggle via VISION_LANG (default: German)
        _lang = (os.getenv("VISION_LANG") or "de").strip().lower()
        _is_en = _lang.startswith("en")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": (question or ("Answer the question about the image." if _is_en else "Beantworte die Frage zum Bild."))},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            }
        ]

        payload = {
            "model": getattr(qwen_client, "QWEN_MODEL_VL", "qwen2.5-vl"),
            "messages": messages,
            "temperature": getattr(qwen_client, "QWEN_TEMPERATURE", 0.1),
            "max_tokens": getattr(qwen_client, "QWEN_MAX_TOKENS", 256),
        }

        req = _ur.Request(
            f"{getattr(qwen_client, 'QWEN_BASE', 'http://127.0.0.1:8010/v1')}/chat/completions",
            data=_json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with _ur.urlopen(req, timeout=getattr(qwen_client, "QWEN_TIMEOUT", 30.0)) as r:
            body = r.read().decode("utf-8")
            data = _json.loads(body)
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.exception("[vision_summarizer] ask_image_question() Exception: %s", e)
        return None


# -----------------------------------------------------------------------------
# CLI probe (optional)
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    res = get_vision_comment()
    print(json.dumps(res, ensure_ascii=False, indent=2))

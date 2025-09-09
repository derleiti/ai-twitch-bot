#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Zephyr Orchestrator Pipeline

Pipeline per Tick:
- Vision (Qwen-VL): returns scene_summary, entities, notable_text, confidence
- Writer (LLM cascade via llm_router): returns long_sentence and short_sentence
- Formatter: clamps to Twitch ≤500, YouTube ≤200, derives simple keywords

Exports:
- run_tick(timestamp: str, screenshot_path: str, optional_ocr_text: str|None) -> dict
  {twitch_sentence, youtube_sentence, keywords}
"""

from __future__ import annotations
import os
import json
import re
import time
import logging
from typing import Any, Dict, List, Optional, Tuple

import qwen_client

log = logging.getLogger("orchestrator")


def _extract_first_json_object(s: str) -> Optional[Dict[str, Any]]:
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        pass
    # strip codefences
    s2 = s.replace("```json", "```").replace("```", "")
    depth = 0
    start = -1
    in_str = False
    esc = False
    for i, ch in enumerate(s2):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
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
                        start = -1
    return None


def _call_vision(image_path: str, ocr_text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Call Qwen-VL with the structured vision prompt, parse JSON.

    Includes resilient image-path handling: if the exact path does not exist,
    try common sibling extensions (.jpg/.jpeg/.png) similar to the summarizer.
    """
    # Build a custom message content via qwen_client by temporarily overriding the user_text
    # We reuse qwen_client.analyze_image by monkeypatching its prompt through env (avoid invasive change)
    # but simplest is to call the same endpoint ourselves using qwen_client settings.
    try:
        import base64, mimetypes, urllib.request as _ur

        # Resolve actual image path with sibling extension fallback
        img_path = image_path
        if not os.path.exists(img_path):
            base, ext = os.path.splitext(img_path)
            ext_order = [".jpg", ".jpeg", ".png"]
            # Keep current ext first if present, then others
            if ext.lower() in ext_order:
                order = [ext.lower()] + [e for e in ext_order if e != ext.lower()]
            else:
                order = ext_order
            for e in order:
                cand = base + e
                if os.path.exists(cand):
                    img_path = cand
                    try:
                        log.debug("[vision] using sibling image: %s", img_path)
                    except Exception:
                        pass
                    break

        if not os.path.exists(img_path):
            return None

        with open(img_path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('ascii')
        mime, _ = mimetypes.guess_type(img_path)
        if not mime:
            mime = 'image/jpeg'
        data_uri = f"data:{mime};base64,{b64}"

        vis_lang = (os.getenv("VISION_LANG") or "de").strip().lower()
        if vis_lang.startswith("en"):
            system = (
                "Role: Qwen-Vision, you analyze a desktop screenshot. "
                "Return exactly JSON with scene_summary, entities, notable_text, confidence."
            )
            user = (
                "Analyze the image concisely and factually. Do not identify real people. "
                "Use OCR hints if provided; do not invent details."
            )
        else:
            system = (
                "Rolle: Qwen-Vision, du analysierst einen Desktop-Screenshot. "
                "Gib exakt JSON zurück mit scene_summary, entities, notable_text, confidence."
            )
            user = (
                "Analysiere das Bild prägnant und faktenbasiert. Keine Identifikation realer Personen. "
                "Nutze ggf. OCR-Hinweise, erfinde nichts."
            )
        if ocr_text:
            user += f"\nOCR: {ocr_text}"

        messages = [
            {"role": "system", "content": [{"type": "text", "text": system}]},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            },
        ]
        payload = {
            "model": getattr(qwen_client, "QWEN_MODEL_VL", os.getenv("QWEN_VISION_MODEL", "qwen2.5-vl")),
            "messages": messages,
            "temperature": float(os.getenv("QWEN_TEMPERATURE", "0.1")),
            "max_tokens": int(os.getenv("QWEN_MAX_TOKENS", "448")),
            # Try structured JSON if bridge supports it
            # "response_format": {"type": "json_object"},
        }
        req = _ur.Request(
            f"{getattr(qwen_client, 'QWEN_BASE', os.getenv('QWEN_BASE','http://127.0.0.1:8010/v1'))}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with _ur.urlopen(req, timeout=getattr(qwen_client, "QWEN_TIMEOUT", 30.0)) as r:
            body = r.read().decode("utf-8")
            data = json.loads(body)
            content = data["choices"][0]["message"]["content"]
    except Exception as e:
        log.warning("Vision call failed: %s", e)
        return None

    js = _extract_first_json_object(content)
    if not js:
        # Fallback: use robust summarizer and map to expected schema
        try:
            from vision_summarizer import summarize_image as _sum
            from commentary_engine import filter_objects as _filt
        except Exception:
            _sum = None
            _filt = None
        if _sum:
            basic = _sum(image_path)
            if basic:
                # scene_summary from details or join labels
                details = (basic.get("details") or "").strip()
                labels = []
                try:
                    labels = _filt(basic.get("objects") or []) if _filt else []
                except Exception:
                    labels = []
                scene = details or (", ".join(labels) if labels else "")
                # derive confidence as avg of confidences present
                confs = []
                for o in (basic.get("objects") or []):
                    try:
                        c = float(o.get("confidence")) if isinstance(o, dict) and o.get("confidence") is not None else None
                    except Exception:
                        c = None
                    if c is not None:
                        confs.append(max(0.0, min(1.0, c)))
                conf = (sum(confs) / len(confs)) if confs else 0.0
                return {
                    "scene_summary": scene,
                    "entities": labels[:6] if labels else [],
                    "notable_text": [],
                    "confidence": float(conf),
                }
        return None

    # Normalize structure
    out: Dict[str, Any] = {
        "scene_summary": str(js.get("scene_summary") or "").strip(),
        "entities": [str(x).strip() for x in (js.get("entities") or []) if str(x).strip()][:6],
        "notable_text": [str(x).strip() for x in (js.get("notable_text") or []) if str(x).strip()][:6],
        "confidence": float(js.get("confidence") or 0.0),
    }
    return out


def _call_writer(vision: Dict[str, Any], timestamp: str) -> Optional[Dict[str, str]]:
    try:
        from llm_router import run_llm_chain
    except Exception:
        run_llm_chain = None

    payload = {
        "scene_summary": vision.get("scene_summary", ""),
        "entities": vision.get("entities", []),
        "notable_text": vision.get("notable_text", []),
        "confidence": float(vision.get("confidence") or 0.0),
        "timestamp": timestamp,
    }
    comm_lang = (os.getenv("COMMENTARY_LANG") or "de").strip().lower()
    if comm_lang.startswith("en"):
        instr = (
            "Role: You write complete sentences in English based on the Qwen analysis. "
            "Return exactly JSON with long_sentence (180–400, exactly ONE sentence) and short_sentence (80–160, exactly ONE sentence). "
            "Full sentences, no bullet style, no lists, no placeholders or hashtags. "
            "Only use content from scene_summary/notable_text/entities; be cautious if confidence is low (appears to, likely)."
        )
        idle_fallback = "Brief idle moment…"
    else:
        instr = (
            "Rolle: Du schreibst komplette Sätze in Deutsch auf Basis der Qwen-Analyse. "
            "Gib exakt JSON mit long_sentence (180–400, exakt EIN Satz) und short_sentence (80–160, exakt EIN Satz) zurück. "
            "Ganze Sätze, kein Telegrammstil, keine Listen, keine Platzhalter oder Hashtags. "
            "Nur Inhalte aus scene_summary/notable_text/entities; bei geringer Sicherheit vorsichtig (scheint, vermutlich)."
        )
        idle_fallback = "Kurzer Idle-Moment…"
    prompt = instr + "\nInput:\n" + json.dumps(payload, ensure_ascii=False)

    if not run_llm_chain:
        # Bare fallback: use scene_summary
        ss = str(vision.get("scene_summary") or idle_fallback).strip()
        if not ss:
            ss = idle_fallback
        long_s = ss
        short_s = ss[:170]
        return {"long_sentence": long_s, "short_sentence": short_s}

    out = run_llm_chain(prompt)
    # Avoid posting the raw prompt if the router echoes it back
    try:
        from commentary_engine import looks_like_prompt as _looks
    except Exception:
        def _looks(x: str) -> bool:
            x = (x or "").lower()
            return any(m in x for m in ["aufgabe:", "2–4 sätze", "2-4 sätze", "json", "vision_begin", "long_sentence", "short_sentence", "rolle:", "role:"])
    js = _extract_first_json_object(out)
    if not js:
        # fallback to raw text unless it looks like a prompt; then scene_summary
        text = (out or "").strip()
        if not text or _looks(text):
            text = str(vision.get("scene_summary") or "").strip()
        if not text:
            text = idle_fallback
        return {"long_sentence": text, "short_sentence": text[:170]}
    long_s = str(js.get("long_sentence") or "").strip()
    short_s = str(js.get("short_sentence") or "").strip()
    if not long_s:
        long_s = short_s or (vision.get("scene_summary") or "Kurzer Idle-Moment…")
    if not short_s:
        short_s = long_s[:170]
    return {"long_sentence": long_s, "short_sentence": short_s}

def _to_one_sentence(s: str) -> str:
    """
    Normalize arbitrary text into ONE sentence:
    - collapse whitespace
    - replace ?! with .
    - merge multiple sentences with commas
    Ensures trailing period if not punctuation.
    """
    s = " ".join((s or "").split())
    if not s:
        return ""
    s = re.sub(r"[!?]+", ".", s)
    parts = re.split(r"(?<=[.!?])\s+", s)
    parts = [p.strip(" .,:;-") for p in parts if p.strip()]
    if not parts:
        return ""
    one = parts[0]
    if len(parts) > 1:
        one = one + ", " + ", ".join(parts[1:])
    if one and one[-1] not in ".!?…":
        one += "."
    return one


def _clamp(s: str, limit: int) -> str:
    s = " ".join((s or "").split()).strip()
    if len(s) <= limit:
        return s
    cut = s[:limit]
    sp = cut.rfind(" ")
    if sp >= 30:
        cut = cut[:sp]
    return cut.rstrip(" .,:;-") + "…"


def _format_and_keywords(long_s: str, short_s: str, ents: List[str], notes: List[str]) -> Dict[str, Any]:
    tw_raw = _to_one_sentence(long_s)
    yt_raw = _to_one_sentence(short_s)
    tw = _clamp(tw_raw, 500)
    yt = _clamp(yt_raw, 200)
    if len(tw_raw) > 500 or len(yt_raw) > 200:
        log.info("[format] clamp applied: tw_raw=%d→≤500, yt_raw=%d→≤200", len(tw_raw), len(yt_raw))
    # Simple keywords from entities + notable_text
    kws: List[str] = []
    for x in ents + notes:
        t = (x or "").strip()
        if t and t.lower() not in {k.lower() for k in kws}:
            kws.append(t)
        if len(kws) >= 6:
            break
    if len(kws) < 3:
        # fallback: take some words from sentences
        for word in (long_s or "").split():
            w = word.strip(".,:;|()[]{}!?")
            if len(w) >= 3 and w.lower() not in {k.lower() for k in kws}:
                kws.append(w)
            if len(kws) >= 6:
                break
    return {"twitch_sentence": tw, "youtube_sentence": yt, "keywords": kws[:6]}


def run_tick(timestamp: str, screenshot_path: str, optional_ocr_text: Optional[str] = None) -> Optional[Dict[str, Any]]:
    vis = _call_vision(screenshot_path, optional_ocr_text)
    if not vis:
        return None
    # Neutralize if very low confidence – the writer prompt already covers it, but we surface confidence anyway
    writer = _call_writer(vis, timestamp)
    if not writer:
        return None
    out = _format_and_keywords(writer.get("long_sentence",""), writer.get("short_sentence",""), vis.get("entities", []), vis.get("notable_text", []))
    return out

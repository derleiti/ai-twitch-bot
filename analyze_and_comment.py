#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CLI/Hook: Bild rein, Vision-Summary + LLM-Kommentar raus – als eine Nachricht.
Übergibt die vollständige Vision-Analyse (raw_full) an die LLM-Kette.
"""

from __future__ import annotations
import sys
import re

# .env laden (robust)
try:
    from dotenv import load_dotenv
    load_dotenv() or load_dotenv("/root/zephyr/.env") or load_dotenv(".env")
except Exception:
    pass

from vision_summarizer import summarize
from llm_router import ask_language_models
from commentary_engine import render_message

PROMPT_TEMPLATE = """\
Hier ist eine vollständige, unbearbeitete Vision-Analyse (vom Bildmodell):

<<<VISION_BEGIN
{vision_full}
VISION_END>>>

Aufgabe:
- Formuliere GENAU EINEN deutschen Satz (keine Liste, kein Bullet, kein Markdown), der die Szene präzise beschreibt und eine klare Handlungsempfehlung ableitet.
- Maximal 500 Zeichen.
- Nutze ausschließlich Informationen aus der Vision-Analyse; benenne Unsicherheit knapp (z. B. „wirkt“, „vermutlich“), wenn confidence niedrig ist.
- Kein Emoji, keine Hashtags, keine Platzhalter.
"""

def _to_one_sentence(s: str) -> str:
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

def _clamp(s: str, n: int) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else (s[:n].rsplit(" ", 1)[0].rstrip(" .,:;-") + "…")

def build_prompt_from_vision(vision: dict) -> str:
    full = (vision.get("raw_full") or "").strip()
    if not full:
        # Fallback: kleiner Brief, falls raw_full leer ist
        brief = vision.get("raw_excerpt") or "Keine verwertbaren Details vorhanden."
        return PROMPT_TEMPLATE.format(vision_full=brief).strip()
    return PROMPT_TEMPLATE.format(vision_full=full).strip()

def main(argv):
    if len(argv) < 2:
        print("Usage: analyze_and_comment.py <image_path_or_url> [salt]")
        sys.exit(1)
    image = argv[1]
    salt = argv[2] if len(argv) >= 3 else ""
    vision = summarize(image)
    prompt = build_prompt_from_vision(vision)
    llm_text = ask_language_models(prompt)  # nutzt BACKEND_ORDER und *_API_BASE/KEY/MODEL
    msg = render_message(vision, llm_text, salt=salt)
    final = _clamp(_to_one_sentence(msg), 500)
    print(final)

if __name__ == "__main__":
    main(sys.argv)

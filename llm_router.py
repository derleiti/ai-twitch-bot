#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
import requests
from typing import Callable, List

log = logging.getLogger("llm_router")

# Output length tuning
try:
    LLM_MAX_OUTPUT_CHARS = int(os.getenv("LLM_MAX_OUTPUT_CHARS", "420"))
except Exception:
    LLM_MAX_OUTPUT_CHARS = 420

# Umgebungsvariablen
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
MISTRAL_KEY = os.getenv("MISTRAL_API_KEY")
# Prefer OLLAMA_URL (as used elsewhere), fallback to legacy OLLAMA_BASE
OLLAMA_BASE = os.getenv("OLLAMA_URL") or os.getenv("OLLAMA_BASE") or "http://127.0.0.1:11434"
OLLAMA_MODEL = os.getenv("OLLAMA_TEXT_MODEL") or os.getenv("OLLAMA_MODEL") or "gpt-oss:latest"

def _shorten(s: str, limit: int | None = None) -> str:
    """Collapse whitespace and clamp length, but keep full sentence(s) instead of a single line."""
    if limit is None:
        limit = LLM_MAX_OUTPUT_CHARS
    try:
        s = " ".join((s or "").split())
    except Exception:
        s = str(s or "")
    if not s:
        return s
    if len(s) <= limit:
        return s
    cut = s[:limit]
    sp = cut.rfind(" ")
    if sp >= 30:
        cut = cut[:sp]
    return cut.rstrip(" .,:;-") + "…"

def _gemini(prompt: str) -> str | None:
    if not GEMINI_KEY:
        return None
    try:
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel(os.getenv("GEMINI_MODEL","gemini-1.5-flash"))
        resp = model.generate_content(prompt)
        text = resp.text or ""
        return _shorten(text)
    except Exception as e:
        log.warning("Gemini failover: %s", e)
        return None

def _mistral(prompt: str) -> str | None:
    if not MISTRAL_KEY:
        return None
    try:
        from mistralai import Mistral  # type: ignore
        client = Mistral(api_key=MISTRAL_KEY)
        model = os.getenv("MISTRAL_MODEL","mistral-small-latest")
        r = client.chat.complete(
            model=model,
            messages=[{"role":"user","content":prompt}],
            temperature=0.2,
            max_tokens=120,
        )
        text = r.choices[0].message.content
        return _shorten(text)
    except Exception as e:
        log.warning("Mistral failover: %s", e)
        return None

def _ollama(prompt: str) -> str | None:
    try:
        url = f"{OLLAMA_BASE.rstrip('/')}/api/generate"
        payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        text = data.get("response","")
        return _shorten(text)
    except Exception as e:
        log.warning("Ollama failover: %s", e)
        return None

def run_llm_chain(prompt: str) -> str:
    """
    Kaskade basierend auf AI_ORDER (oder BACKEND_ORDER):
      - "first" (Default): erster erfolgreiche Provider gewinnt (Failover)
      - "hybrid": versuche alle in Reihenfolge und wähle die inhaltlich reichste (längste) Antwort
    Fallback: gekürzter Prompt.
    """
    order = os.getenv("AI_ORDER") or os.getenv("BACKEND_ORDER") or "gemini,mistral,gpt-oss"
    mode = (os.getenv("AI_MODE") or "first").strip().lower()
    seq: List[str] = [x.strip().lower() for x in order.split(",") if x.strip()]
    # Map provider keys to callables
    mapping: dict[str, Callable[[str], str | None]] = {
        "gemini": _gemini,
        "mistral": _mistral,
        "gpt-oss": _ollama,
        "ollama": _ollama,
    }
    fns: List[Callable[[str], str | None]] = [mapping[k] for k in seq if k in mapping]
    if not fns:
        fns = [_gemini, _mistral, _ollama]

    results: List[str] = []
    for fn in fns:
        try:
            out = fn(prompt)
        except Exception as e:
            log.warning("LLM provider error: %s", e)
            out = None
        if out:
            if mode != "hybrid":
                return out
            results.append(out)

    if results:
        # pick the longest non-empty answer as a proxy for richness
        return max(results, key=lambda s: len(s))

    # letzter Notanker:
    return _shorten(prompt)

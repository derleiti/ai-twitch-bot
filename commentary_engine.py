# -*- coding: utf-8 -*-
import os
import json
import requests
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Primär: OpenAI-kompatibel (vLLM/TGI/etc.)
LLM_API_BASE = os.getenv("LLM_API_BASE", "").strip()
LLM_API_KEY  = os.getenv("LLM_API_KEY", "no-key-required")
LLM_MODEL    = os.getenv("LLM_MODEL", "gpt-oss-20b")

# Fallback: Ollama (lokal)
OLLAMA_URL        = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_TEXT_MODEL = os.getenv("OLLAMA_TEXT_MODEL", "gpt-oss:latest")

SYS = (
  "You are GameCommentator v2. Blend on-screen summary with structured game_state to produce:\n"
  "- short_chat: 1–2 knackige Sätze für Twitch (<=180 Zeichen, familientauglich, kein Backseating, kein Spoiler).\n"
  "- long_call: 1–3 Sätze (~<=300 Zeichen) mit Situation, Risiko & sinnvoller nächster Schritt.\n"
  "Schreibe auf Deutsch, locker & positiv.\n"
  "Keine Vermutungen – wenn Info fehlt, schreibe 'unbekannt'.\n"
  "Wenn game_state fehlt, nutze nur die Vision-Zusammenfassung."
)

PROMPT_TMPL = """\
<vision_summary>
{vision_json}
</vision_summary>

<game_state_json>
{game_state}
</game_state_json>

Erzeuge JSON (nur JSON!):
{{"short_chat": "...", "long_call": "..."}}
"""

def _clip(s, n):
    return (s or "")[:n]

def _via_openai_compatible(vision_json: Dict[str,Any], game_state: Dict[str,Any]) -> Dict[str,str]:
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    user = PROMPT_TMPL.format(
        vision_json=json.dumps(vision_json, ensure_ascii=False),
        game_state=json.dumps(game_state, ensure_ascii=False)
    )
    body = {
        "model": LLM_MODEL,
        "temperature": 0.2,
        "messages": [
            {"role":"system","content":SYS},
            {"role":"user","content":user}
        ]
    }
    r = requests.post(f"{LLM_API_BASE}/chat/completions", headers=headers, json=body, timeout=60)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"].strip()
    try:
        out = json.loads(content)
    except Exception:
        out = {"short_chat": content, "long_call": content}
    return {"short_chat": _clip(out.get("short_chat",""), 180),
            "long_call":  _clip(out.get("long_call",""), 300)}

def _via_ollama(vision_json: Dict[str,Any], game_state: Dict[str,Any]) -> Dict[str,str]:
    user = PROMPT_TMPL.format(
        vision_json=json.dumps(vision_json, ensure_ascii=False),
        game_state=json.dumps(game_state, ensure_ascii=False)
    )
    payload = {
        "model": OLLAMA_TEXT_MODEL,
        "stream": False,
        "options": {"temperature": 0.2},
        "messages": [
            {"role":"system","content":SYS},
            {"role":"user","content":user}
        ],
    }
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=120)
    if r.status_code == 404:
        # Automatischer Fallback auf gpt-oss, falls anderes Textmodell nicht vorhanden
        payload["model"] = "gpt-oss:latest"
        r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=120)
    r.raise_for_status()
    content = r.json().get("message", {}).get("content", "").strip()
    try:
        out = json.loads(content)
    except Exception:
        out = {"short_chat": content, "long_call": content}
    return {"short_chat": _clip(out.get("short_chat",""), 180),
            "long_call":  _clip(out.get("long_call",""), 300)}

def make_comment(vision_json: Dict[str,Any], game_state: Dict[str,Any]) -> Dict[str,str]:
    # 1) Wenn OpenAI-kompatibles Backend konfiguriert ist, versuch es
    if LLM_API_BASE:
        try:
            return _via_openai_compatible(vision_json, game_state)
        except Exception:
            pass
    # 2) Fallback: Ollama lokal
    return _via_ollama(vision_json, game_state)

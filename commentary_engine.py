#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import socket
import re
import time
import json
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)-12s] [%(levelname)-5s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("commentary_engine")

POST_PREFIX = os.getenv("POST_PREFIX", "🎯 Vision")
SHOW_HOST_IN_PREFIX = (os.getenv("SHOW_HOST_IN_PREFIX", "true").lower() == "true")
VISION_HOST_LABEL = os.getenv("VISION_HOST_LABEL") or socket.gethostname()
try:
    from screenshots.screenshot_manager import SOURCE_LABEL as _SRC_LABEL
except Exception:
    _SRC_LABEL = os.getenv("VISION_SOURCE_LABEL", "screen@unknown")

def _build_prefix() -> str:
    base = POST_PREFIX
    if SHOW_HOST_IN_PREFIX:
        return f"{base} [{VISION_HOST_LABEL}|{_SRC_LABEL}]"
    return base
TWITCH_MAX_LEN = int(os.getenv("TWITCH_MAX_MESSAGE_LEN", "500"))
SEP = " · "

# Commentary language (de|en)
_COMM_LANG_RAW = (os.getenv("COMMENTARY_LANG") or "de").strip().lower()
COMM_LANG = "en" if _COMM_LANG_RAW.startswith("en") else "de"
IS_EN = COMM_LANG == "en"
NO_RELEVANT_MSG = "No relevant objects detected" if IS_EN else "Keine relevanten Objekte erkannt"
LBL_EVENT = "Event" if IS_EN else "Ereignis"
LBL_OBJECTS = "Objects" if IS_EN else "Objekte"
LBL_DETAILS = "Details" if IS_EN else "Details"

# Dedupe: gleiche Kernevents in kurzem Zeitfenster unterdrücken
DEDUPE_WINDOW_SEC = int(os.getenv("COMMENT_SIGNATURE_WINDOW", "30"))
_last_signature_ts: Dict[str, float] = {}
_last_emit_ts: float = 0.0

ENDINGS = (".", "!", "?", "…")

# Regex-Wächter für Codefences und Roh-JSON-Zeilen
_FENCE_RE = re.compile(r"```[\s\S]*?```", re.M)
_LEADING_JSON_RE = re.compile(r"^\s*[{[].*[\]}]\s*$", re.S)


def _labels_from_objects(objects: List[Dict[str, Any]]) -> List[str]:
    # Reuse the filtering logic: blocklist + confidence ≥0.80, top-3
    return filter_objects(objects)


def sanitize_text(text: Optional[str]) -> Tuple[str, Dict[str, bool]]:
    """
    Entfernt Markdown-Codeblöcke, Roh-JSON-Fragmente und Stacktraces.
    Kollabiert Whitespace und normalisiert zu einer Zeile.

    Returns (sanitized_text, flags)
    flags: {"removed_codeblock":bool, "removed_json":bool, "removed_stack":bool}
    """
    flags = {"removed_codeblock": False, "removed_json": False, "removed_stack": False}
    if not text:
        return "", flags

    s = str(text)

    # Entferne ```...``` Codeblöcke (auch mit Sprache wie ```json)
    if "```" in s:
        s_new = re.sub(r"```[\s\S]*?```", " ", s)
        if s_new != s:
            flags["removed_codeblock"] = True
            s = s_new
        # Falls block ungeöffnet blieb, entfernen ab erstem ``` bis Ende
        if "```" in s:
            flags["removed_codeblock"] = True
            s = s.split("```", 1)[0]

    # Entferne offensichtliche Stacktraces/Traceback Blöcke
    s_new = re.sub(r"Traceback \(most recent call last\):[\s\S]+?(?=\n\S|$)", " ", s)
    if s_new != s:
        flags["removed_stack"] = True
        s = s_new

    # Entferne eingebettete JSON-Objekte (heuristisch): {...} mit Doppelpunkten
    def _strip_json_blocks(text_in: str) -> Tuple[str, bool]:
        removed = False
        # Mehrfach, falls mehrere Blöcke
        pattern = re.compile(r"\{[^{}]*:[^{}]*\}")
        last = None
        s_loc = text_in
        for _ in range(10):  # begrenze Aufwand
            s2 = pattern.sub(" ", s_loc)
            if s2 == s_loc:
                break
            removed = True
            s_loc = s2
        return s_loc, removed

    s, removed_json = _strip_json_blocks(s)
    if removed_json:
        flags["removed_json"] = True

    # Inline-Backticks entfernen
    s = s.replace("`", " ")

    # Whitespace normalisieren (Doppelleerzeichen, Zeilenumbrüche)
    s = re.sub(r"\s+", " ", s).strip()
    return s, flags


_BLOCKLIST_LABELS = {
    "chatgpt",
    "neuer chat",
    "markdown code",
    "5 thinking",
}


def filter_objects(objects: List[Dict[str, Any]]) -> List[str]:
    """
    - Nur Labels mit confidence >= 0.80
    - Blockliste generischer Labels (inkl. Regex „Nachgedacht“)
    - Top-3, dedupliziert (casefold)
    """
    candidates: List[Tuple[str, float]] = []
    for it in (objects or []):
        if isinstance(it, dict):
            label = str(it.get("label") or "").strip()
            try:
                conf = float(it.get("confidence")) if it.get("confidence") is not None else None
            except Exception:
                conf = None
        elif isinstance(it, str):
            label = it.strip()
            conf = None
        else:
            continue

        if not label:
            continue

        low = label.casefold()
        # Blockliste + Regex „Nachgedacht“
        if any(b in low for b in _BLOCKLIST_LABELS) or re.search(r"(?i)nachgedacht", label):
            continue

        if conf is None or conf < 0.80:
            continue
        candidates.append((label, conf))

    # Sortiere nach confidence absteigend
    candidates.sort(key=lambda x: (x[1], x[0].casefold()), reverse=True)

    # Dedupe in Einfügereihenfolge (case-insensitiv)
    out: List[str] = []
    seen = set()
    for label, _ in candidates:
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(label)
        if len(out) >= 3:
            break
    return out


def detect_event(log_text: str) -> Dict[str, Any]:
    """
    Erkennung von Ereignissen aus Log-ähnlichem Text.
    Liefert u.a. {event, route, port, details_fragments: List[str]}.
    """
    text = log_text or ""
    out: Dict[str, Any] = {"event": None, "route": None, "port": None, "details_fragments": []}

    # Nightbot/Systemzeilen ignorieren
    if re.search(r"(?i)\bnightbot\b", text):
        out["ignore"] = True
        return out

    # JOIN / CAP ACK
    m_join = re.search(r"JOIN\s+#(\w+)", text)
    cap_ack = bool(re.search(r"CAP\s+\*\s+ACK", text))
    if m_join:
        chan = m_join.group(1)
        out["event"] = f"Twitch IRC verbunden (JOIN #{chan})"
        if cap_ack:
            out["details_fragments"].append("CAP ACK aktiv")
        return out

    # Channel bereit (ROOMSTATE oder Numeric 366/376)
    if re.search(r"\bROOMSTATE\b|\b366\b|\b376\b", text):
        out["event"] = "Channel bereit"
        return out

    # HTTP 200 POST /v1/…
    m_api = re.search(r'"POST\s+(/v1/[^\s\"]+)[^"]*"\s+200\b', text)
    if m_api:
        route = m_api.group(1)
        out["event"] = f"API 200 OK ({route})"
        out["route"] = route
        # Qwen Sampler-Parameter in Details
        m_samp = re.search(r"\[qwen-vl\].*?temp=([\d.]+).*?top_p=([\d.]+)", text, flags=re.IGNORECASE)
        if m_samp:
            tval, pval = m_samp.group(1), m_samp.group(2)
            out["details_fragments"].append(f"Qwen-VL temp={tval}, top_p={pval}")
        return out

    # Uvicorn running on ...:PORT
    m_uv = re.search(r"Uvicorn running on http://[^:]+:(\d+)", text)
    if m_uv:
        port = m_uv.group(1)
        out["event"] = f"Dienst gestartet (:{port})"
        out["port"] = port
        return out

    # Qwen-VL Sampler alleine (ohne API 200)
    m_samp = re.search(r"\[qwen-vl\].*?temp=([\d.]+).*?top_p=([\d.]+)", text, flags=re.IGNORECASE)
    if m_samp:
        tval, pval = m_samp.group(1), m_samp.group(2)
        out["event"] = "Sampler aktiv"
        out["details_fragments"].append(f"Qwen-VL temp={tval}, top_p={pval}")
        return out

    # Kein spezifisches Event erkannt
    out["event"] = "Status aktualisiert"
    return out


def make_signature(event: Optional[str], route: Optional[str], port: Optional[str]) -> str:
    base = f"{event or ''}|{route or ''}|{port or ''}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:10]


def should_post_now() -> bool:
    # Hook für Zeitfenster/Cooldown/Triggers – hier immer True
    return True


def _clamp_len(s: str, max_len: int) -> str:
    s = (s or "").replace("\n", " ").strip()
    if len(s) <= max_len:
        return s
    cut = s[:max_len]
    sp = cut.rfind(" ")
    if sp >= 30:
        cut = cut[:sp]
    cut = cut.rstrip(" .,:;-") + "…"
    return cut[:max_len]


def prepare_for_twitch(text: str, *, salt: str = "") -> str:
    """
    Normalisiert Endzeichen, entfernt Zeilenumbrüche und begrenzt auf Twitch-Maximalgröße.
    Hängt KEINEN Punkt an, wenn schon .,!,?,… oder '·' am Ende steht.
    """
    out = (text or "")

    # Letzte Schranke: Codefences entfernen, reine JSON-Zeilen entschärfen
    if "```" in out:
        out = _FENCE_RE.sub(" ", out)
    if _LEADING_JSON_RE.match(out.strip()):
        out = "Inhalt bereinigt."

    out = out.replace("\n", " ").rstrip()

    # Kein Endzeichen anhängen, wenn schon eins da ist oder auf '·' endet
    if not (out.endswith("·") or out.endswith("· ") or any(out.endswith(e) for e in ENDINGS)):
        out = out + "."

    return _clamp_len(out, TWITCH_MAX_LEN)


# --- Writer: ONE-SENTENCE generator with robust fallbacks ---
def _to_one_sentence_local(s: str) -> str:
    try:
        # Reuse orchestrator helpers if available
        from orchestrator import _to_one_sentence as _tos
        return _tos(s)
    except Exception:
        s = " ".join((s or "").split())
        if not s:
            return ""
        s = re.sub(r"[!?]+", ".", s)
        parts = re.split(r"(?<=[.!?])\s+", s)
        parts = [p.strip(" .,:;-") for p in parts if p.strip()]
        one = parts[0] if parts else ""
        if len(parts) > 1:
            one = one + ", " + ", ".join(parts[1:])
        if one and one[-1] not in ".!?…":
            one += "."
        return one


def _clamp_local(s: str, n: int) -> str:
    try:
        from orchestrator import _clamp as _cl
        return _cl(s, n)
    except Exception:
        s = " ".join((s or "").split()).strip()
        if len(s) <= n:
            return s
        cut = s[:n]
        sp = cut.rfind(" ")
        if sp >= 30:
            cut = cut[:sp]
        return cut.rstrip(" .,:;-") + "…"


def looks_like_prompt(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    markers = [
        "aufgabe:",
        "2–4 sätze", "2-4 sätze",
        "vision_begin",
        "```",
        "return exactly json", "gib exakt json",
        "long_sentence", "short_sentence",
        "rolle:", "role:",
        # Our writer prompt phrasing (DE/EN)
        "schreibe genau einen satz",
        "write a clear, detailed short description",
        # Heuristics: looks like instruction with embedded JSON details
        "details:", "objekte:",
    ]
    if any(m in t for m in markers):
        return True
    # Stronger pattern: 'details: {' suggests echoed instruction content
    try:
        import re as _re
        if _re.search(r"details\s*:\s*\{", t):
            return True
    except Exception:
        pass
    return False


def _qwen_fallback_one_sentence(vision: Dict[str, Any]) -> str:
    # Use existing vision dict; prefer details, otherwise derive from objects
    raw = (vision or {}).get("details") or ""
    # If raw looks like JSON (nested or not), ignore it and derive from labels
    try:
        import re as _re
        if ("{" in raw and "}" in raw) or _re.search(r"\"\w+\"\s*:\s*", raw):
            raw = ""
    except Exception:
        pass
    # Sanitize to drop codefences/JSON blocks/stack traces
    txt, _flags = sanitize_text(raw)
    if not txt:
        labels = []
        try:
            labels = filter_objects(vision.get("objects") or [])
        except Exception:
            labels = []
        if labels:
            if IS_EN:
                txt = f"Visible: {', '.join(labels)}"
            else:
                txt = f"Sichtbar: {', '.join(labels)}"
        else:
            txt = os.getenv("FALLBACK_DEFAULT_SENTENCE_DE", "Kurzer Blick auf den Bildschirm: Szene wird ausgewertet und zusammengefasst.")
    return _clamp_local(_to_one_sentence_local(txt), 500)


def generate_one_sentence(vision: Dict[str, Any]) -> str:
    """
    Robust writer chain:
    - try llm_router; if output looks like prompt or empty, raise to fallback
    - fallback to Qwen-vision-derived one sentence
    - final fallback to configured default sentence
    Always returns 1 German sentence (≤ 500 chars).
    """
    # Attempt writer chain via llm_router
    text: str | None = None
    try:
        try:
            from llm_router import run_llm_chain as _llm
        except Exception:
            _llm = None
        if _llm:
            # Build concise DE instruction to avoid echoing
            labels = []
            try:
                labels = filter_objects(vision.get("objects") or [])
            except Exception:
                labels = []
            details = (vision.get("details") or "")
            prompt = (
                "Schreibe genau EINEN Satz (Deutsch) zur Szene, max. 300 Zeichen, kein Markdown. "
                "Nutze nur sichtbare Elemente/Handlungen. "
                f"Objekte: {', '.join(labels) if labels else '(keine)'}; Details: {details[:600]}"
            )
            cand = _llm(prompt)
            if cand and not looks_like_prompt(cand):
                text = cand
            else:
                raise RuntimeError("writer-returned-prompt-or-empty")
        else:
            raise RuntimeError("writer-missing")
    except Exception:
        if os.getenv("FALLBACK_USE_QWEN_SUMMARY_ON_WRITER_FAIL", "true").lower() == "true":
            log.info("[writer] fallback: qwen")
            text = _qwen_fallback_one_sentence(vision)
        else:
            text = os.getenv(
                "FALLBACK_DEFAULT_SENTENCE_DE",
                "Kurzer Blick auf den Bildschirm: Szene wird ausgewertet und zusammengefasst."
            )
            log.info("[writer] fallback: default")

    # One-sentence guarantee and clamp
    text = _to_one_sentence_local(text or "")
    text = _clamp_local(text, 500)
    return text


def make_comment(vision: Dict[str, Any], *, salt: str = "") -> Optional[str]:
    """
    Baut eine Twitch-taugliche Nachricht:
    "🎯 Vision · Ereignis: <status> · Objekte: a, b · Details: <satz>"

    - Entfernt Codeblöcke/JSON/Stacktraces
    - Filtert generische Objekte, nur Top-3 ab 0.80
    - Ereignis-Erkennung aus Logtext (JOIN, CAP ACK, API 200, Uvicorn, ROOMSTATE/366/376, Sampler)
    - Dedupe: gleiche event|route|port innerhalb 30s unterdrücken
    """
    try:
        objects = vision.get("objects") or []
        raw_details = vision.get("details") or ""

        # Sanitize
        clean_details, flags = sanitize_text(raw_details)

        # Objekte filtern
        filtered_labels = filter_objects(objects)

        # Ereignis erkennen
        ev = detect_event(clean_details)
        if ev.get("ignore"):
            return None

        event_title = ev.get("event") or "Status aktualisiert"
        # Signature + Dedupe
        sig = make_signature(event_title, ev.get("route"), ev.get("port"))
        now = time.time()
        last = _last_signature_ts.get(sig, 0.0)
        if now - last < DEDUPE_WINDOW_SEC:
            log.debug("Dedupe: gleiche Signatur %s in %.1fs – unterdrückt", sig, now - last)
            return None
        _last_signature_ts[sig] = now

        # Details bestimmen
        details_frags: List[str] = list(ev.get("details_fragments") or [])
        detail_text: Optional[str] = None
        if details_frags:
            detail_text = ", ".join(details_frags)
        else:
            # Bei generischem Status bevorzugt die vollen (bereinigten) Details übernehmen.
            if event_title == "Status aktualisiert":
                if flags.get("removed_codeblock"):
                    detail_text = "Eingabe bereinigt (Codeblock entfernt)"
                elif not filtered_labels and not clean_details:
                    # No relevant objects and no details
                    detail_text = NO_RELEVANT_MSG
                else:
                    # Übernehme vollständige bereinigte Details (werden erst in prepare_for_twitch auf 500 gekürzt)
                    if clean_details:
                        detail_text = clean_details

        # De-Priorisierung: Nur selten posten, wenn (a) kein Host-Match und (b) generischer Status
        host_filter = os.getenv("VISION_HOST_FILTER", "").strip()
        cross_host_cooldown = int(os.getenv("CROSS_HOST_DEPRIORIZE_SEC", "120"))
        no_relevant_cooldown = int(os.getenv("NORELEVANT_MIN_INTERVAL_SEC", "90"))
        now = time.time()
        global _last_emit_ts

        if event_title == "Status aktualisiert":
            # Cross-Host: falls Filter gesetzt und Source/Host nicht matchen, nur alle X Sekunden zulassen
            if host_filter and (host_filter not in _SRC_LABEL) and (host_filter not in VISION_HOST_LABEL):
                if now - _last_emit_ts < cross_host_cooldown:
                    log.debug("Cross-Host de-priorize: letzte Sendung vor %.1fs – übersprungen", now - _last_emit_ts)
                    return None

            # "Keine relevanten Objekte" nur gelegentlich posten, um Rauschen zu senken
            if detail_text == NO_RELEVANT_MSG:
                if now - _last_emit_ts < no_relevant_cooldown:
                    log.debug("No-relevant gating: letzte Sendung vor %.1fs – übersprungen", now - _last_emit_ts)
                    return None

        # Optional: LLM-gestützte Kurzbeschreibung (deutlich, nicht "zu klein")
        use_llm = (os.getenv("VISION_COMMENT_USE_LLM", "true").lower() == "true")
        if use_llm:
            try:
                from llm_router import run_llm_chain as _llm
            except Exception:
                _llm = None
            if _llm:
                try:
                    labels_str = ", ".join(filtered_labels) if filtered_labels else "(keine)"
                    if IS_EN:
                        prompt = (
                            "Write a clear, detailed short description of the screenshot in English. "
                            "Name visible elements (windows, chat, terminal, UI), recognizable actions, and the likely context. "
                            "2–4 sentences, no Markdown, max 430 characters. "
                            f"Objects: {labels_str}. Details (sanitized): {clean_details[:1200]}"
                        )
                    else:
                        prompt = (
                            "Formuliere eine klare, detailreiche Kurzbeschreibung des Screenshots auf Deutsch. "
                            "Nenne sichtbare Elemente (Fenster, Chat, Terminal, UI), erkennbare Aktionen und den vermutlichen Kontext. "
                            "2–4 Sätze, ohne Markdown, max. 430 Zeichen. "
                            f"Objekte: {labels_str}. Details (bereinigt): {clean_details[:1200]}"
                        )
                    llm_text = _llm(prompt)
                    if llm_text and not looks_like_prompt(llm_text):
                        # Nutze LLM-Ergebnis als Details, aber niemals Roh-Prompt
                        detail_text = llm_text
                except Exception:
                    pass

        # Nachricht bauen
        parts: List[str] = [f"{_build_prefix()}", f"{LBL_EVENT}: {event_title}"]
        if filtered_labels:
            parts.append(f"{LBL_OBJECTS}: {', '.join(filtered_labels)}")
        if detail_text:
            parts.append(f"{LBL_DETAILS}: {detail_text}")

        msg = SEP.join(parts)
        prepared = prepare_for_twitch(msg, salt=salt)
        # Debug als Einzeile und gekürzt, kein Roh-JSON
        try:
            log.debug("Vision prepared: %s", (prepared or "")[:200])
        except Exception:
            pass
        if prepared:
            _last_emit_ts = now
        return prepared

    except Exception:
        log.exception("Fehler in make_comment")
        return None

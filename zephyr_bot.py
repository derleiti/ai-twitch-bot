#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zephyr Multi-Platform Bot
- Twitch & YouTube Integration
- Vision Summarizer (Qwen/OpenAI-kompatibel)
"""

import os
import sys
import time
import logging
from typing import Optional

try:
    # .env automatisch laden, wenn vorhanden
    from dotenv import load_dotenv
    from pathlib import Path
    _root = Path(__file__).resolve().parent
    _env_path = _root / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except Exception:
    pass

from vision_summarizer import summarize_image, ask_image_question
import orchestrator
from commentary_engine import make_comment, should_post_now, prepare_for_twitch, generate_one_sentence
from anti_flood import AntiFlood
from twitch_client import TwitchClient
from youtube_client import YouTubeClient
from screenshots.screenshot_manager import ingest, list_recent, get_by_sid, latest, count as shots_count
import bot_health
import os
import re

# -----------------------------------------
# Setup Logging
# -----------------------------------------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)-12s] [%(levelname)-5s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("MAIN_BOT")

# -----------------------------------------
# Konfiguration
# -----------------------------------------
SCREENSHOT_FILE = os.getenv(
    "SCREENSHOT_FILE", "/root/zephyr/screenshots/current_screenshot.jpg"
)
POST_SALT = os.getenv("POST_SALT", ".")
INTERVAL = int(os.getenv("SCREENSHOT_ANALYSIS_INTERVAL", "10"))
INTERVAL_JITTER = float(os.getenv("TICK_JITTER_SEC", "1.0"))
# Für 10s-Posting-Ziel sinnvoll senken (per .env überschreibbar)
SHORT_CHAT_MIN_INTERVAL = int(os.getenv("SHORT_CHAT_MIN_INTERVAL", "8"))
CHAT_GLOBAL_COOLDOWN_SEC = int(os.getenv("CHAT_GLOBAL_COOLDOWN_SEC", "120"))

ENABLE_TWITCH = os.getenv("ENABLE_TWITCH", "true").lower() == "true"
ENABLE_YOUTUBE = os.getenv("ENABLE_YOUTUBE", "true").lower() == "true"
# Suppress automatic Twitch output (vision posts) but still connect for commands
TWITCH_SILENT_AUTO = os.getenv("TWITCH_SILENT_AUTO", "false").lower() == "true"
ORCHESTRATOR_ENABLED = os.getenv("ORCHESTRATOR_ENABLED", "true").lower() == "true"

# Random reply settings (disabled by default)
RAND_REPLY_ENABLED = os.getenv("TWITCH_RANDOM_REPLY", "false").lower() == "true"
try:
    RAND_REPLY_RATE = float(os.getenv("TWITCH_RANDOM_REPLY_RATE", "0.10"))  # 10% chance
except Exception:
    RAND_REPLY_RATE = 0.10
try:
    RAND_REPLY_MIN_GAP = int(os.getenv("TWITCH_RANDOM_REPLY_MIN_GAP_SEC", "90"))
except Exception:
    RAND_REPLY_MIN_GAP = 90
RAND_REPLY_IGNORE = [s.strip().lower() for s in os.getenv(
    "TWITCH_RANDOM_REPLY_IGNORE_USERS",
    "nightbot,streamelements,moobot,anotherttvviewer"
).split(",") if s.strip()]

# -----------------------------------------
# AntiFlood
# -----------------------------------------
ANTI_FLOOD = AntiFlood()

# Optional: globaler Zugriff für Chat-Handler
TWITCH_CLIENT: Optional[TwitchClient] = None
# Alias-Name, damit Handler auch 'twitch' nutzen kann
twitch: Optional[TwitchClient] = None
_last_rand_reply_ts: float = 0.0
_startup_vision_done: bool = False

# Startup vision env flags
AUTO_VISION_ON_START = os.getenv("AUTO_VISION_ON_START", "true").lower() != "false"
try:
    STARTUP_VISION_DELAY_SEC = int(os.getenv("STARTUP_VISION_DELAY_SEC", "3"))
except Exception:
    STARTUP_VISION_DELAY_SEC = 3
AUTO_VISION_IGNORE_LIVESTATUS = os.getenv("AUTO_VISION_IGNORE_LIVESTATUS", "true").lower() == "true"
try:
    STARTUP_VISION_MAX_WAIT_SEC = int(os.getenv("STARTUP_VISION_MAX_WAIT_SEC", "25"))
except Exception:
    STARTUP_VISION_MAX_WAIT_SEC = 25


def get_help_message() -> str:
    return (
        "Befehle: !links, !shots [n], !shot <latest|sid>, !askshot <latest|sid> <frage>, "
        "!bild (Analyse), !witz (kurzer Witz), !health, !budget"
    )


def _labels_for_log(vision) -> str:
    objs = vision.get("objects") or []
    labels = []
    for o in objs:
        if isinstance(o, dict) and "label" in o:
            labels.append(o["label"])
        elif isinstance(o, str):
            labels.append(o)
    return ", ".join(labels) if labels else "n/a"


# -----------------------------------------
# Vision → Kommentar → Posting
# -----------------------------------------
def get_vision_comment(image_path: str) -> Optional[str]:
    """
    Ruft den Vision-Summarizer auf und erzeugt Kommentar.
    """
    logger.debug("[DIAGNOSE] Betrete get_vision_comment für Bild: %s", image_path)

    vision = summarize_image(image_path)
    if not vision:
        logger.debug("Vision-Ergebnis leer/None (Backoff, unverändert oder Fehler).")
        return None

    # Erzeuge Short-Chat Kommentar
    comment = make_comment(vision, salt=POST_SALT)

    # Debug-Zusammenfassung fürs Log
    full_text = (
        f"🎯 Vision-Analyse "
        f"HP: {vision.get('hp')} "
        f"Objekte: {_labels_for_log(vision)} "
        f"Details: {str(vision.get('details') or '(keine)').replace('\n', ' ')}"
    )
    safe = full_text
    if len(safe) > 240:
        safe = safe[:240].rstrip(" .,:;") + "…"
    logger.debug("[DIAGNOSE] Vision Summary: %s", safe)
    # Avoid noise: don't post generic no-object messages
    try:
        if comment and comment.strip().lower().startswith("keine relevanten objekte erkannt"):
            logger.debug("Vision: keine relevanten Objekte — kein Public-Post.")
            return None
    except Exception:
        pass
    return comment


def schedule_startup_vision():
    global _startup_vision_done
    if _startup_vision_done:
        return
    if not AUTO_VISION_ON_START:
        logger.info("[startup_vision] disabled via AUTO_VISION_ON_START=false")
        return
    if os.getenv("TWITCH_SILENT_AUTO", "false").lower() == "true":
        logger.info("[startup_vision] SKIP: TWITCH_SILENT_AUTO=true")
        return
    try:
        import threading
        logger.info("[startup_vision] scheduling in %ss", STARTUP_VISION_DELAY_SEC)
        def _runner():
            try:
                safe_post_startup_vision()
            except Exception as e:
                logger.warning("[startup_vision] error: %s", e)
        t = threading.Timer(STARTUP_VISION_DELAY_SEC, _runner)
        t.daemon = True
        t.start()
    except Exception as e:
        logger.warning("[startup_vision] schedule failed: %s", e)


def safe_post_startup_vision():
    global _startup_vision_done
    if _startup_vision_done:
        return
    deadline = time.time() + max(3, STARTUP_VISION_MAX_WAIT_SEC)
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        vis = None
        try:
            vis = summarize_image(SCREENSHOT_FILE)
        except Exception as e:
            logger.warning("[startup_vision] summarize failed: %s", e)
        if vis:
            try:
                text = generate_one_sentence(vis)
                if twitch:
                    twitch.enqueue(prepare_for_twitch(text), bucket="startup_vision", priority=True)
                    logger.info("[startup_vision] posted")
                else:
                    logger.info("[startup_vision] skip: twitch not enabled")
            except Exception as e:
                logger.warning("[startup_vision] send failed: %s", e)
            finally:
                _startup_vision_done = True
            return
        # Not yet available – small wait and retry
        time.sleep(2.0)
    logger.warning("[startup_vision] no vision available within %ss – skip", STARTUP_VISION_MAX_WAIT_SEC)
    _startup_vision_done = True


def handle_chat_message(user, is_mod, text):
    """Einfacher Chat-Handler für Screenshot-Kommandos."""
    t = (text or "").strip()

    # bot info / hilfe
    if re.match(r"^!info\b", t, re.I):
        msg = get_help_message()
        if twitch:
            twitch.say(prepare_for_twitch(msg), bucket="command")
        return

    # quick links
    if re.match(r"^!links\b", t, re.I):
        url = os.getenv("LINKS_URL", "https://linktr.ee/derleiti")
        if twitch:
            # explizit als Command-Bucket senden (bypass falscher Heuristik bei 'Links ·')
            twitch.say(prepare_for_twitch(f"Links · {url}"), bucket="command")
        return

    # kurzanalyse des aktuellen screenshots
    if re.match(r"^!bild\b", t, re.I):
        try:
            vis = summarize_image(SCREENSHOT_FILE)
            if vis:
                msg = make_comment(vis) or "🎯 Analyse erstellt"
            else:
                msg = "⚠️ Keine Analyse verfügbar"
            if TWITCH_CLIENT:
                TWITCH_CLIENT.say(prepare_for_twitch(msg), bucket="command")
        except Exception:
            if TWITCH_CLIENT:
                TWITCH_CLIENT.say("⚠️ Vision fehlgeschlagen.", bucket="system")
        return

    # kleiner witz
    if re.match(r"^!witz\b", t, re.I):
        reply = None
        # Optional via LLM
        try:
            from llm_router import run_llm_chain as _llm
        except Exception:
            _llm = None
        if _llm:
            try:
                prompt = (
                    "Erzähle einen sehr kurzen, harmlosen Witz auf Deutsch. "
                    "Eine Zeile, max. 120 Zeichen, ohne Markdown."
                )
                reply = _llm(prompt)
            except Exception:
                reply = None
        if not reply:
            jokes = [
                "Warum hat die KI eine Brille? Damit sie besser lernt!",
                "Ich wollte gestern joggen… aber meine Couch hatte besseren Empfang.",
                "Was macht ein Informatiker im Fitnessstudio? Arrays."
            ]
            try:
                import random as _r
                reply = _r.choice(jokes)
            except Exception:
                reply = jokes[0]
        if TWITCH_CLIENT:
            TWITCH_CLIENT.say(prepare_for_twitch(reply), bucket="command")
        return

    # mod-only: budget status
    m = re.match(r"^!(\w+)\b", t, re.I)
    if m and m.group(1).lower() == os.getenv("BUDGET_CMD","budget").lower():
        require_mod = (os.getenv("BUDGET_REQUIRE_MOD","true").lower() != "false")
        if require_mod and not is_mod:
            return  # still & silent
        try:
            used, limit, left = (twitch.budget_state() if twitch else (None,None,None))
            bs = twitch.bucket_states_compact() if twitch else None
            line = []
            if used is not None:
                line.append(f"budget: {used}/{limit} ({left}s)")
            if bs:
                line.append(f"buckets: {bs}")
            msg = " · ".join(line) if line else "budget: n/a"
            if twitch:
                twitch.say(prepare_for_twitch(msg), bucket="command")
        except Exception:
            if twitch:
                twitch.say(prepare_for_twitch("budget: n/a"), bucket="command")
        return

    # Liste der letzten Shots
    m = re.match(r"^!shots(?:\s+(\d+))?$", t, re.I)
    if m:
        n = int(m.group(1) or 5)
        n = max(1, min(n, 10))
        recs = list_recent(n)
        if not recs:
            if TWITCH_CLIENT:
                TWITCH_CLIENT.say("📁 Keine gespeicherten Screenshots.", bucket="command")
            return
        def time_str(ts):
            return time.strftime("%H:%M:%S", time.localtime(ts))
        lines = [f"sid:{r['sid']} · {time_str(r['ts'])} · {r['source']} · {r['name']}" for r in recs]
        if TWITCH_CLIENT:
            TWITCH_CLIENT.say(prepare_for_twitch(" | ".join(lines)), bucket="command")
        return

    # Kurz-Vision eines Shots
    m = re.match(r"^!shot\s+(latest|\d+)$", t, re.I)
    if m:
        sel = m.group(1).lower()
        rec = latest() if sel == "latest" else get_by_sid(int(sel))
        if not rec:
            if TWITCH_CLIENT:
                TWITCH_CLIENT.say("❓ Screenshot nicht gefunden.", bucket="command")
            return
        try:
            vis = summarize_image(rec["path"])
            msg = make_comment(vis) if vis else f"🎯 {rec['name']}"
            if TWITCH_CLIENT:
                TWITCH_CLIENT.say(prepare_for_twitch(msg), bucket="command")
        except Exception:
            if TWITCH_CLIENT:
                TWITCH_CLIENT.say("⚠️ Vision fehlgeschlagen.", bucket="system")
        return

    # Gezielt fragen
    m = re.match(r"^!askshot\s+(latest|\d+)\s+(.+)$", t, re.I)
    if m:
        sel, q = m.group(1).lower(), m.group(2).strip()
        rec = latest() if sel == "latest" else get_by_sid(int(sel))
        if not rec:
            if TWITCH_CLIENT:
                TWITCH_CLIENT.say("❓ Screenshot nicht gefunden.", bucket="command")
            return
        try:
            ans = ask_image_question(rec["path"], q)
            if TWITCH_CLIENT:
                TWITCH_CLIENT.say(prepare_for_twitch(f"🔎 {ans}"), bucket="command")
        except Exception:
            if TWITCH_CLIENT:
                TWITCH_CLIENT.say("⚠️ Analyse fehlgeschlagen.", bucket="system")
        return

    # Health summary
    if re.match(r"^!health\b", t, re.I):
        host = os.getenv("VISION_HOST_LABEL") or os.uname().nodename
        source = os.getenv("VISION_SOURCE_LABEL", "screen@unknown")
        parts = [f"♥ health [{host}|{source}]"]
        verbose = ("verbose" in t.lower())

        # twitch connection (best-effort)
        try:
            status = "OK" if twitch and getattr(twitch, "_connected", False) else "ERR"
        except Exception:
            status = "ERR"
        parts.append(f"twitch: {status}")

        # irc rtt (optional)
        if os.getenv("HEALTH_INCLUDE_IRC","true").lower() != "false":
            try:
                rtt = twitch.ping(int(os.getenv("HEALTH_IRC_TIMEOUT_MS","800"))) if twitch else None
                if rtt is not None:
                    parts.append(f"irc: {rtt}ms")
                else:
                    parts.append("irc: n/a")
            except Exception:
                parts.append("irc: n/a")

        # qwen (optional)
        if bot_health.INC_QWEN:
            qok, qms, qerr = bot_health.check_qwen(
                os.getenv("QWEN_BASE","http://127.0.0.1:8010"),
                os.getenv("QWEN_MODEL","qwen-vl"),
                int(os.getenv("HEALTH_TIMEOUT_MS","1500"))
            )
            parts.append(bot_health.fmt_check("qwen", qok, qms, qerr, show_err=verbose))

        # auth (optional)
        if bot_health.INC_AUTH:
            aok, ams, aerr = bot_health.check_auth(
                os.getenv("AUTH_BASE_URL","http://127.0.0.1:8088"),
                int(os.getenv("HEALTH_TIMEOUT_MS","1500"))
            )
            parts.append(bot_health.fmt_check("auth", aok, ams, aerr, show_err=verbose))

        # screenshots count + last post age
        try:
            parts.append(f"shots: {shots_count()}")
        except Exception:
            parts.append("shots: n/a")
        try:
            age = twitch.last_post_age_seconds() if twitch else None
            if age is not None:
                parts.append(f"last: {age}s")
        except Exception:
            pass
        try:
            rx = twitch.last_rx_age_seconds() if twitch else None
            if rx is not None:
                parts.append(f"rx: {rx}s")
        except Exception:
            pass
        try:
            used, limit, left = (twitch.budget_state() if twitch else (None, None, None))
            if used is not None:
                parts.append(f"budget: {used}/{limit} ({left}s)")
        except Exception:
            pass

        if TWITCH_CLIENT:
            TWITCH_CLIENT.say(prepare_for_twitch(" · ".join(parts)), bucket="command")
        return

    # --- Random lightweight replies to regular chat lines ---
    try:
        if not RAND_REPLY_ENABLED:
            return
        if not t or t.startswith("!"):
            return  # ignore commands/empties
        sender = (user or "").strip().lower()
        if not sender or sender in RAND_REPLY_IGNORE:
            return
        # avoid self-replies
        self_name = (os.getenv("TWITCH_USERNAME", "") or os.getenv("BOT_USERNAME", "")).strip().lower()
        if self_name and sender == self_name:
            return
        # probability gate
        import random as _random
        if _random.random() > max(0.0, min(1.0, RAND_REPLY_RATE)):
            return
        # cooldown gate
        global _last_rand_reply_ts
        now = time.time()
        if (now - _last_rand_reply_ts) < RAND_REPLY_MIN_GAP:
            return
        # generate concise reply using LLM router (fallback-safe)
        try:
            from llm_router import run_llm_chain as _llm
        except Exception:
            _llm = None
        prompt = (
            "Antworte im Twitch-Chat kurz, freundlich und themenbezogen in DE. "
            "Maximal 1 Satz, höchstens 120 Zeichen, kein Markdown. "
            f"Nachricht von @{user}: \"{t}\""
        )
        reply = None
        if _llm:
            try:
                reply = _llm(prompt)
            except Exception:
                reply = None
        if not reply:
            # simple echo fallback
            reply = f"@{user} verstanden! 😊"
        msg = f"@{user} {reply}" if not reply.startswith(f"@{user}") else reply
        if twitch:
            twitch.say(prepare_for_twitch(msg), bucket="command")
            _last_rand_reply_ts = now
    except Exception:
        # never break the chat loop due to rand-replies
        pass


# -----------------------------------------
# Haupt-Loop
# -----------------------------------------
def main():
    logger.info("========================================")
    logger.info("🤖 Zephyr Bot - Final Edition")
    logger.info("▶  PID: %s", os.getpid())

    global TWITCH_CLIENT, twitch
    twitch = TwitchClient() if ENABLE_TWITCH else None
    youtube = YouTubeClient() if ENABLE_YOUTUBE else None
    TWITCH_CLIENT = twitch

    if twitch:
        # Chat-Befehle auswerten
        twitch.on_message = handle_chat_message
        # Schedule auto-vision when IRC ready (USERSTATE/ROOMSTATE or end of MOTD)
        try:
            twitch.on_ready = schedule_startup_vision
        except Exception:
            pass
        twitch.connect()

    # Periodic help/commands announcement
    help_enabled = os.getenv("TWITCH_HELP_ENABLED", "true").lower() == "true"
    try:
        help_interval = int(os.getenv("TWITCH_HELP_INTERVAL_SEC", "300"))
    except Exception:
        help_interval = 300
    help_msg = os.getenv("TWITCH_HELP_MESSAGE") or get_help_message()
    last_help_ts: float = 0.0
    if youtube:
        youtube.connect()

    logger.info("Bot gestartet und betriebsbereit.")

    try:
        last_sent_ts: float = 0.0
        while True:
            # Periodic commands/help line every N seconds
            if help_enabled and twitch:
                now_ts = time.time()
                if (now_ts - last_help_ts) >= max(60, help_interval):
                    try:
                        twitch.say(prepare_for_twitch(help_msg), bucket="command")
                        last_help_ts = now_ts
                    except Exception:
                        pass
            if not should_post_now():
                time.sleep(INTERVAL)
                continue

            # Screenshot in den Ringpuffer aufnehmen (optional best effort)
            try:
                from screenshots.screenshot_manager import ingest as _ingest
                _ingest(SCREENSHOT_FILE)
            except Exception:
                pass

            if ORCHESTRATOR_ENABLED:
                ts = time.strftime("%Y-%m-%dT%H:%M:%S%z")
                out = orchestrator.run_tick(ts, SCREENSHOT_FILE, optional_ocr_text=None)
                if not out:
                    # no output this tick
                    time.sleep(INTERVAL)
                    continue
                tw_msg = out.get("twitch_sentence") or ""
                yt_msg = out.get("youtube_sentence") or tw_msg[:200]
                # AntiFlood (use twitch sentence)
                if not ANTI_FLOOD.allow(tw_msg, min_interval=SHORT_CHAT_MIN_INTERVAL, salt=POST_SALT):
                    logger.info(
                        "[vision→twitch] DROP durch AntiFlood: min_interval=%ss (Text gehasht mit salt)",
                        SHORT_CHAT_MIN_INTERVAL,
                    )
                    time.sleep(INTERVAL)
                    continue
                now = time.time()
                if (now - last_sent_ts) < CHAT_GLOBAL_COOLDOWN_SEC:
                    logger.debug("Global Cooldown: noch %.1fs – übersprungen", CHAT_GLOBAL_COOLDOWN_SEC - (now - last_sent_ts))
                    time.sleep(INTERVAL)
                    continue
                if twitch and not TWITCH_SILENT_AUTO:
                    try:
                        twitch.enqueue(tw_msg, bucket="vision")
                    except Exception as e:
                        logger.warning("[vision→twitch] SEND-Error: %s", e)
                        # retry once after backoff 1.5x
                        time.sleep(max(1.0, INTERVAL * 1.5))
                        try:
                            twitch.enqueue(tw_msg, bucket="vision")
                        except Exception:
                            pass
                elif twitch and TWITCH_SILENT_AUTO:
                    logger.info("[vision] SKIP: TWITCH_SILENT_AUTO=true")
                if youtube:
                    try:
                        youtube.post(yt_msg)
                    except Exception:
                        time.sleep(max(1.0, INTERVAL * 1.5))
                        try:
                            youtube.post(yt_msg)
                        except Exception:
                            pass
                last_sent_ts = time.time()
                # jittered sleep
                try:
                    import random as _r
                    dt = INTERVAL + _r.uniform(-INTERVAL_JITTER, INTERVAL_JITTER)
                    time.sleep(max(1.0, dt))
                except Exception:
                    time.sleep(INTERVAL)
                continue

            # Legacy path
            comment = get_vision_comment(SCREENSHOT_FILE)
            if not comment:
                time.sleep(INTERVAL)
                continue
            if not ANTI_FLOOD.allow(comment, min_interval=SHORT_CHAT_MIN_INTERVAL, salt=POST_SALT):
                logger.info(
                    "[vision→twitch] DROP durch AntiFlood: min_interval=%ss (Text gehasht mit salt)",
                    SHORT_CHAT_MIN_INTERVAL,
                )
                time.sleep(INTERVAL)
                continue
            short_msg = prepare_for_twitch(comment, salt=POST_SALT)
            now = time.time()
            if (now - last_sent_ts) < CHAT_GLOBAL_COOLDOWN_SEC:
                logger.debug("Global Cooldown: noch %.1fs – übersprungen", CHAT_GLOBAL_COOLDOWN_SEC - (now - last_sent_ts))
                time.sleep(INTERVAL)
                continue
            if twitch and not TWITCH_SILENT_AUTO:
                twitch.enqueue(short_msg, bucket="vision")
            else:
                if TWITCH_SILENT_AUTO:
                    logger.info("[vision] SKIP: TWITCH_SILENT_AUTO=true")
            if youtube:
                youtube.post(short_msg)
            last_sent_ts = time.time()
            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        logger.info("Beende Zephyr Bot (KeyboardInterrupt)…")
        sys.exit(0)


if __name__ == "__main__":
    main()

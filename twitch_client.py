#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import ssl
import socket
import threading
from collections import deque
import logging
import re

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)-12s] [%(levelname)-5s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("TwitchClient")


class TwitchClient:
    """
    Minimaler Twitch-IRC Client (TLS) für das Senden von Chat-Nachrichten.
    Erfordert in .env:
      - TWITCH_USERNAME
      - TWITCH_OAUTH_TOKEN (Format: oauth:xxxxxxxxxxxxxxxxxxxx)
      - TWITCH_CHANNEL (ohne oder mit '#', wird normalisiert)
    Optional:
      - TWITCH_IRC_HOST (default irc.chat.twitch.tv)
      - TWITCH_IRC_PORT (default 6697 TLS)
    """

    def __init__(self):
        # Unterstütze neue und alte Variablennamen aus .env
        chan = os.getenv("TWITCH_CHANNEL") or os.getenv("CHANNEL") or ""
        # Fallback: Wenn python-dotenv die Zeile "CHANNEL=#name" als Kommentar ignoriert hat,
        # versuche, den Raw-Wert direkt aus der .env zu lesen (nur falls nichts gesetzt ist).
        if not chan:
            try:
                from pathlib import Path
                env_path = Path(__file__).resolve().parent / ".env"
                if env_path.exists():
                    for line in env_path.read_text(encoding="utf-8").splitlines():
                        if not line or line.lstrip().startswith("#"):
                            continue
                        if line.startswith("CHANNEL=") and not os.getenv("TWITCH_CHANNEL"):
                            raw = line.split("=", 1)[1].strip()
                            if (raw.startswith("\"") and raw.endswith("\"")) or (raw.startswith("'") and raw.endswith("'")):
                                raw = raw[1:-1]
                            chan = raw
                            break
            except Exception:
                pass
        if not chan:
            chan = "#derleiti"
        user = os.getenv("TWITCH_USERNAME") or os.getenv("BOT_USERNAME") or ""
        oauth = os.getenv("TWITCH_OAUTH_TOKEN") or os.getenv("OAUTH_TOKEN") or ""

        self.channel = self._normalize_channel(chan)
        self.username = user
        self.oauth = oauth
        self.host = os.getenv("TWITCH_IRC_HOST", "irc.chat.twitch.tv")
        self.port = int(os.getenv("TWITCH_IRC_PORT", "6697"))
        self.max_len = int(os.getenv("TWITCH_MAX_MESSAGE_LEN", "500"))
        # Control greeting behavior (default: send once when connected)
        try:
            self._send_hello_enabled = (os.getenv("TWITCH_SEND_HELLO", "true").lower() == "true")
        except Exception:
            self._send_hello_enabled = True
        # Configurable hello text (default requested by user)
        try:
            self._hello_text = (
                os.getenv("TWITCH_HELLO_TEXT")
                or os.getenv("HELLO_TEXT")
                or "zephyrt bot online · Befehle: !links, !shots, !shot, !askshot, !bild, !witz, !health, !budget"
            )
        except Exception:
            self._hello_text = "zephyrt bot online · Befehle: !links, !shots, !shot, !askshot, !bild, !witz, !health, !budget"

        self._sock: socket.socket | None = None
        self._file = None  # text-mode reader
        self._connected = False
        self._rx_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._hello_sent = False
        self.on_message = None  # callback(user:str, is_mod:bool, text:str)
        self.on_ready = None    # callback() once when JOIN complete (366/376)
        # --- Health metrics ---
        self._last_sent_ts: float | None = None  # monotonic
        self._last_rx_ts: float | None = None    # monotonic (any server line)
        self._waiting_ping: bool = False
        self._ping_sent_ts: float | None = None
        self._ping_event = threading.Event()
        self._last_rtt_ms: int | None = None
        # --- Budget ---
        self._budget_enabled = (os.getenv("POST_BUDGET_ENABLED","true").lower() != "false")
        try:
            self._budget_window = int(os.getenv("POST_BUDGET_WINDOW_SEC","600"))
            self._budget_limit  = int(os.getenv("POST_BUDGET_MAX_MSGS","6"))
            self._budget_silent = (os.getenv("POST_BUDGET_SILENT","true").lower() == "true")
            self._budget_notice_cd = int(os.getenv("POST_BUDGET_NOTICE_COOLDOWN_SEC","60"))
        except Exception:
            self._budget_window, self._budget_limit = 600, 6
            self._budget_silent, self._budget_notice_cd = True, 60
        self._budget_times = deque()   # monotonic() timestamps erfolgreicher Sends
        self._budget_last_notice_ts: float | None = None
        # --- Bucket Budgets ---
        self._allow_priority = (os.getenv("POST_BUDGET_ALLOW_PRIORITY","true").lower() == "true")
        buckets = [b.strip() for b in os.getenv("POST_BUDGET_BUCKETS","vision,command,system,startup_vision,default").split(",") if b.strip()]
        self._bucket_cfg = {}
        for b in buckets:
            key = b.upper()
            win = int(os.getenv(f"POST_BUDGET_{key}_WINDOW_SEC", os.getenv("POST_BUDGET_DEFAULT_WINDOW_SEC","600")))
            lim = int(os.getenv(f"POST_BUDGET_{key}_MAX_MSGS",   os.getenv("POST_BUDGET_DEFAULT_MAX_MSGS","6")))
            self._bucket_cfg[b] = (win, lim)
        self._bucket_cfg.setdefault("default", (int(os.getenv("POST_BUDGET_DEFAULT_WINDOW_SEC","600")),
                                                int(os.getenv("POST_BUDGET_DEFAULT_MAX_MSGS","6"))))
        # Sensible defaults for startup_vision if not configured
        if "startup_vision" in buckets and "startup_vision" not in self._bucket_cfg:
            self._bucket_cfg["startup_vision"] = (30, 2)
        self._bucket_times_map: dict[str, deque] = {b: deque() for b in self._bucket_cfg}
        self._bucket_notice_cd = max(10, self._budget_notice_cd)
        self._bucket_last_notice_ts: dict[str, float | None] = {b: None for b in self._bucket_cfg}

    @staticmethod
    def _normalize_channel(ch: str) -> str:
        ch = (ch or "").strip()
        if not ch:
            return ch
        if not ch.startswith("#"):
            ch = f"#{ch}"
        return ch

    def _ensure_creds(self):
        if not self.username:
            raise RuntimeError("TWITCH_USERNAME fehlt in .env")
        if not self.oauth or not self.oauth.startswith("oauth:"):
            raise RuntimeError("TWITCH_OAUTH_TOKEN fehlt oder hat nicht das Format 'oauth:…'")
        if not self.channel:
            raise RuntimeError("TWITCH_CHANNEL fehlt in .env")

    def _reader_loop(self):
        try:
            while self._connected and self._file:
                try:
                    line = self._file.readline()
                except (TimeoutError, socket.timeout):
                    # Kein Traffic – weiter warten
                    continue
                if not line:
                    break
                line = line.rstrip("\r\n")
                # mark last RX for liveness/age
                try:
                    self._last_rx_ts = time.monotonic()
                except Exception:
                    pass
                if line.startswith("PING"):
                    self._raw_send("PONG :tmi.twitch.tv")
                    log.debug("PONG gesendet")
                # If measuring RTT, any server traffic after PING counts
                if self._waiting_ping and self._ping_sent_ts is not None:
                    try:
                        rtt = int((time.monotonic() - self._ping_sent_ts) * 1000)
                        self._last_rtt_ms = rtt
                    except Exception:
                        self._last_rtt_ms = None
                    self._waiting_ping = False
                    try:
                        self._ping_event.set()
                    except Exception:
                        pass
                # READY-Signal (Ende MOTD oder End of NAMES) → einmalige Begrüßung
                if (" 366 " in line or " 376 " in line):
                    # Fire on_ready exactly once
                    if callable(self.on_ready) and not getattr(self, "_ready_fired", False):
                        try:
                            self.on_ready()
                        except Exception as e:
                            log.debug("on_ready handler error: %s", e)
                        self._ready_fired = True
                if self._send_hello_enabled and (not self._hello_sent) and (" 366 " in line or " 376 " in line):
                    try:
                        # Bypass budgets and ensure visibility on startup
                        self.enqueue(self._hello_text, bucket="system", priority=True)
                        self._hello_sent = True
                    except Exception as e:
                        log.debug("Hello-Sendung fehlgeschlagen: %s", e)
                # Debug-Logs auf trace-level; highlight NOTICEs (e.g., rate limits, restrictions)
                if " NOTICE " in line:
                    log.warning("NOTICE: %s", line)
                else:
                    log.debug("< %s", line)

                # PRIVMSG verarbeiten (mit optionalen IRCv3 Tags)
                try:
                    if " PRIVMSG " in line:
                        tags = {}
                        prefix_and_rest = line
                        if line.startswith("@"):  # IRCv3 tags
                            tag_str, prefix_and_rest = line.split(" ", 1)
                            for kv in tag_str[1:].split(";"):
                                if "=" in kv:
                                    k, v = kv.split("=", 1)
                                    tags[k] = v
                        m = re.search(r"^(?::([^!]+)![^ ]+ )?PRIVMSG #[^ ]+ :(.+)$", prefix_and_rest)
                        if m:
                            user = m.group(1) or tags.get("display-name") or "?"
                            text = m.group(2)
                            is_mod = False
                            b = tags.get("badges", "")
                            if tags.get("mod") == "1" or ("moderator/" in b):
                                is_mod = True
                            if callable(self.on_message):
                                try:
                                    self.on_message(user, is_mod, text)
                                except Exception as e:
                                    log.debug("on_message handler error: %s", e)
                except Exception:
                    # Parsing ist best-effort
                    pass
        except Exception as e:
            log.debug("Reader-Loop beendet: %s", e)
        finally:
            self._connected = False

    def _raw_send(self, data: str):
        if not self._sock:
            return
        try:
            msg = (data + "\r\n").encode("utf-8")
            with self._lock:
                self._sock.sendall(msg)
            # Sanitize secrets in logs (never print oauth tokens)
            to_log = data
            try:
                if to_log.upper().startswith("PASS "):
                    # redact anything after "oauth:"
                    to_log = re.sub(r"(?i)(PASS\s+oauth:)[^\s]+", r"\1********", to_log)
            except Exception:
                to_log = "PASS oauth:********" if data.upper().startswith("PASS ") else data
            log.debug("> %s", to_log)
        except Exception as e:
            log.error("Senden fehlgeschlagen: %s", e)
            self._connected = False

    def connect(self):
        self._ensure_creds()
        log.info("Verbinde mit Twitch IRC als %s zu %s", self.username, self.channel)
        self._hello_sent = False

        base_sock = socket.create_connection((self.host, self.port), timeout=10)
        context = ssl.create_default_context()
        self._sock = context.wrap_socket(base_sock, server_hostname=self.host)
        self._file = self._sock.makefile("r", encoding="utf-8", newline="\n", buffering=1)

        # Nach erfolgreichem Handshake: Blocking-Mode & Keepalive
        try:
            self._sock.settimeout(None)  # blockierendes Lesen (kein 10s-Timeout)
        except Exception:
            pass
        try:
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            # Linux-Defaults schärfen (best effort, nicht überall verfügbar)
            if hasattr(socket, "IPPROTO_TCP"):
                if hasattr(socket, "TCP_KEEPIDLE"):
                    self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
                if hasattr(socket, "TCP_KEEPINTVL"):
                    self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 30)
                if hasattr(socket, "TCP_KEEPCNT"):
                    self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
        except Exception:
            # Keepalive Tuning optional; ignoriere Fehler
            pass

        # Login-Sequenz
        self._raw_send(f"PASS {self.oauth}")
        self._raw_send(f"NICK {self.username}")
        self._raw_send("CAP REQ :twitch.tv/tags twitch.tv/commands")
        self._raw_send(f"JOIN {self.channel}")

        self._connected = True
        # Reader-Thread für PING/PONG
        self._rx_thread = threading.Thread(target=self._reader_loop, name="twitch-rx", daemon=True)
        self._rx_thread.start()
        log.info("Twitch IRC verbunden.")

    def _clamp(self, text: str) -> str:
        s = (text or "").replace("\n", " ").strip()
        if len(s) <= self.max_len:
            return s
        # Kürzen auf Wortgrenze <= max_len, ggf. mit …
        cut = s[: self.max_len]
        if len(s) > self.max_len:
            # versuche letzte Leerstelle zu finden
            sp = cut.rfind(" ")
            if sp >= 30:  # nur sinnvoll kürzen, wenn genug Puffer
                cut = cut[:sp]
            cut = cut.rstrip(" .,:;-") + "…"
            # Sicherheit: nicht über max_len hinaus
            cut = cut[: self.max_len]
        return cut

    def enqueue(self, text: str, bucket: str | None = None, priority: bool = False):
        if not self._connected:
            try:
                self.connect()
            except Exception as e:
                log.error("Twitch-Verbindung fehlgeschlagen: %s", e)
                return
        # Bucket bestimmen (Heuristik, wenn nicht explizit übergeben)
        if bucket is None:
            bucket = self._classify_bucket(text)
        if not hasattr(self, "_bucket_cfg") or bucket not in self._bucket_cfg:
            bucket = "default"

        # Budget-Gates (global + bucket), Priority kann umgehen
        if not priority:
            # global
            if self._budget_enabled and not self._budget_allow():
                # Sichtbares Logging, damit Drops nachvollziehbar sind
                used, limit, left = self.budget_state()
                log.info(
                    "[twitch] DROP global-budget: used=%s/%s, window_left=%ss (Text verworfen)",
                    used, limit, left,
                )
                if not self._budget_silent and self._budget_notice_ok():
                    notice = "⏳ budget: limit erreicht – einige Nachrichten werden gedrosselt"
                    self._raw_send(f"PRIVMSG {self.channel} :{self._clamp(notice)}")
                    try:
                        self._budget_last_notice_ts = time.monotonic()
                    except Exception:
                        pass
                return
            # bucket
            if not self._bucket_allow(bucket):
                # kompakten Bucketzustand loggen und optional Hinweis senden
                bs = self.bucket_states_compact()
                if self._bucket_notice_ok(bucket):
                    if not self._budget_silent:
                        notice = f"⏳ budget[{bucket}]: limit erreicht – gedrosselt"
                        self._raw_send(f"PRIVMSG {self.channel} :{self._clamp(notice)}")
                    try:
                        self._bucket_last_notice_ts[bucket] = time.monotonic()
                    except Exception:
                        pass
                    log.info("[twitch] DROP bucket '%s': %s (Text verworfen)", bucket, bs or "?")
                return

        # Send and account against budget
        self._send_now(text, bucket=bucket)
        try:
            nowm = time.monotonic()
            self._budget_times.append(nowm)
            self._budget_prune()
            bt = self._bucket_times_map.get(bucket) if hasattr(self, "_bucket_times_map") else None
            if bt is not None:
                bt.append(nowm)
                self._bucket_prune(bucket)
        except Exception:
            pass

    def send_hello(self):
        self.enqueue(self._hello_text, bucket="system", priority=True)

    def _send_now(self, text: str, bucket: str | None = None):
        msg = self._clamp(text)
        self._raw_send(f"PRIVMSG {self.channel} :{msg}")
        try:
            self._last_sent_ts = time.monotonic()
        except Exception:
            pass
        if bucket == "startup_vision":
            log.info("[twitch] startup_vision sent (%d Zeichen)", len(msg))
        else:
            log.info("Gesendet (%d Zeichen): %s", len(msg), msg)

    def send_text(self, text: str):
        # Route through enqueue to apply budgets and buckets
        self.enqueue(text)

    def send_chunked(self, text: str, pause_sec: float = 1.8):
        s = (text or "").replace("\n", " ").strip()
        limit = self.max_len
        while s:
            part = s[:limit]
            sp = part.rfind(" ")
            if len(s) > limit and sp >= 30:
                part = part[:sp]
            self.send_text(part)
            s = s[len(part):].lstrip()
            if s:
                time.sleep(pause_sec)

    # --- tiny convenience helpers ---
    def alert(self, text: str):
        """High-priority system alert (bypasses budgets if allowed)."""
        return self.enqueue(text, bucket="system", priority=True)

    def say(self, text: str, bucket: str | None = None):
        """Explicit bucketed send (defaults to heuristic if bucket None)."""
        return self.enqueue(text, bucket=bucket, priority=False)

    # --- Health helpers ---
    def ping(self, timeout_ms: int = 800) -> int | None:
        """Best-effort RTT: send PING and measure time to next server line."""
        if not self._connected:
            return None
        # rate-limit: reuse recent RTT if last ping was too recent
        try:
            min_gap = int(os.getenv("HEALTH_IRC_MIN_GAP_S", "5"))
        except Exception:
            min_gap = 5
        now = time.monotonic()
        if self._ping_sent_ts is not None and (now - self._ping_sent_ts) < min_gap:
            return self._last_rtt_ms
        try:
            self._ping_event.clear()
        except Exception:
            pass
        self._waiting_ping = True
        self._ping_sent_ts = now
        try:
            self._raw_send("PING :zephyr")
        except Exception:
            self._waiting_ping = False
            return None
        ok = False
        try:
            ok = self._ping_event.wait(timeout_ms / 1000)
        except Exception:
            ok = False
        self._waiting_ping = False
        return self._last_rtt_ms if ok else None

    def last_post_age_seconds(self) -> int | None:
        try:
            if self._last_sent_ts is None:
                return None
            return int(time.monotonic() - self._last_sent_ts)
        except Exception:
            return None

    def last_rx_age_seconds(self) -> int | None:
        try:
            if self._last_rx_ts is None:
                return None
            return int(time.monotonic() - self._last_rx_ts)
        except Exception:
            return None

    # --- Budget intern/Status ---
    def _budget_prune(self):
        """Alte Timestamps ausserhalb des Fensters entfernen."""
        try:
            now = time.monotonic()
            win = self._budget_window
            while self._budget_times and (now - self._budget_times[0]) > win:
                self._budget_times.popleft()
        except Exception:
            pass

    def _budget_allow(self) -> bool:
        """True = senden erlaubt, False = gedrosselt."""
        if not self._budget_enabled:
            return True
        self._budget_prune()
        return len(self._budget_times) < self._budget_limit

    def _budget_notice_ok(self) -> bool:
        """Begrenzt Hinweis-Spam, wenn SILENT=false."""
        try:
            now = time.monotonic()
            if self._budget_last_notice_ts is None:
                return True
            return (now - self._budget_last_notice_ts) >= self._budget_notice_cd
        except Exception:
            return False

    def budget_state(self):
        """(used, limit, seconds_left_in_window) für !health."""
        try:
            self._budget_prune()
            used = len(self._budget_times)
            if not self._budget_times:
                return used, self._budget_limit, self._budget_window
            oldest = self._budget_times[0]
            left = max(0, int(self._budget_window - (time.monotonic() - oldest)))
            return used, self._budget_limit, left
        except Exception:
            return None, None, None

    # --- Bucket helpers ---
    def _classify_bucket(self, text: str) -> str:
        try:
            t = (text or "").strip().lower()
        except Exception:
            return "default"
        if t.startswith("🎯") or t.startswith("vision ") or " vision " in t:
            return "vision"
        if t.startswith("♥") or t.startswith("links ") or t.startswith("health ") or t.startswith("ok ") or t.startswith("err "):
            return "command"
        if "error" in t or "warn" in t or "failed" in t:
            return "system"
        return "default"

    def _bucket_prune(self, bucket: str):
        try:
            win, _ = self._bucket_cfg.get(bucket, self._bucket_cfg.get("default", (600, 6)))
            now = time.monotonic()
            dq = self._bucket_times_map.setdefault(bucket, deque())
            while dq and (now - dq[0]) > win:
                dq.popleft()
        except Exception:
            pass

    def _bucket_allow(self, bucket: str) -> bool:
        try:
            self._bucket_prune(bucket)
            _, lim = self._bucket_cfg.get(bucket, self._bucket_cfg.get("default", (600, 6)))
            dq = self._bucket_times_map.setdefault(bucket, deque())
            return len(dq) < lim
        except Exception:
            return True

    def _bucket_notice_ok(self, bucket: str) -> bool:
        try:
            now = time.monotonic()
            last = self._bucket_last_notice_ts.get(bucket)
            if last is None:
                return True
            return (now - last) >= self._bucket_notice_cd
        except Exception:
            return False

    def bucket_states_compact(self) -> str | None:
        """Kurzform: v 1/4, c 0/6, s 0/3"""
        try:
            parts = []
            keymap = {"vision": "v", "command": "c", "system": "s"}
            for b in ("vision", "command", "system"):
                if b not in getattr(self, "_bucket_cfg", {}):
                    continue
                self._bucket_prune(b)
                used = len(self._bucket_times_map.get(b, ()))
                _, lim = self._bucket_cfg[b]
                parts.append(f"{keymap.get(b, b[0])} {used}/{lim}")
            return ", ".join(parts) if parts else None
        except Exception:
            return None

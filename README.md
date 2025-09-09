# AI-Twitch-Bot 🎮🤖

Ein intelligenter Twitch-Chatbot mit Bildanalyse, Spielkommentar, Ollama-Integration und Realtime-Interaktion.

---

## 🚀 Features

- 📡 **Twitch Chatbot (IRC)**  
  Liest Nachrichten im Livestream-Chat und antwortet kontextbezogen.

- 🧠 **KI-Integration mit Ollama (lokale Modelle)**  
  Nutzt lokale LLMs zur Generierung von Texten, Spielkommentaren und Antworten.

- 🖼️ **Bildanalyse mit Vision-Modell (LLaVA, CLIP etc.)**  
  Analysiert Screenshots aus dem Stream und erkennt Spielszenen oder Objekte.

- 🎙️ **Live-Kommentare**  
  Kommentiert automatisch laufende Spielszenen mit Zephyr-Stil-Texten.

- 🔁 **Automatischer Reload via `entr` beim Live-Coding**  
  Neustart des Bots bei jeder Codeänderung – perfekt für schnelles Dev-Feedback.

- 🧩 **Modulares Python-System**  
  Strukturierter Code mit Threads, Events, Logs, Game-State-Management.

- 🔐 **.env-basierte Konfiguration**  
  Alle Zugangsdaten, Tokens und API-Keys in einer `.env` Datei.

---

## 📦 Installation

```bash
git clone https://github.com/derleiti/ai-twitch-bot.git
cd ai-twitch-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
## Auth / SSO (Google + WordPress) Quickstart
1. `pip install -r requirements.txt`
2. Set in `.env`: `SITE_URL`, `AUTH_BASE_URL=http://localhost:8088`, `JWT_SECRET` (32+), `JWT_ISS`, `JWT_AUD`.
   - Google: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
   - WordPress (optional): `WP_WELL_KNOWN` (+ `WP_CLIENT_ID`, `WP_CLIENT_SECRET`)
   - Local HTTP: set `COOKIE_SECURE=false` (or use HTTPS)
3. Run: `uvicorn auth_service:app --host 0.0.0.0 --port 8088`
4. Login flow: open `/auth/login/google` → complete → `GET /auth/me` returns `{email, roles}`.

### Link Twitch account
- Create code:
  `curl -sX POST $AUTH_BASE_URL/api/link/code -H 'content-type: application/json' -d '{"twitch_username":"YOUR_NAME"}'`
  → returns `{code,url}`
- While logged in (cookie set), open the URL to link.
- Internals: stores provider=`twitch`, provider_sub=`<twitch_username>`.

## Screenshot Archive & Vision Q&A
- Configure `.env`:
  `SCREENSHOT_DIR=/root/zephyr/screenshots`
  `SCREENSHOT_MAX=100`
  `VISION_SOURCE_LABEL=screen@workstation`
- Bot commands:
  - `!shots [n]` → list recent `sid · HH:MM:SS · source · filename`
  - `!shot (latest|sid)` → short vision summary
  - `!askshot (latest|sid) <question>` → targeted, one-paragraph answer (links/shortcut symbols, etc.)
- Outputs are single-line, sanitized, ≤ 500 chars.

### Test the ring buffer
Run `pytest -q tests/test_screenshot_ringbuffer.py` — it seeds > MAX items, asserts only the newest MAX remain and dedupe works.


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


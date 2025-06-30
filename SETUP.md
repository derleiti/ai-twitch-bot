# Zephyr Multi-Platform Bot - Setup Anleitung

Ein intelligenter Chatbot für **Twitch** und **YouTube** mit KI-Bildanalyse und automatischen Kommentaren.

## 🚀 Features

- **Multi-Platform**: Unterstützt Twitch IRC und YouTube Live Chat gleichzeitig
- **KI-Integration**: Nutzt lokale Ollama-Modelle (Zephyr/Mixtral + LLaVA)
- **Bildanalyse**: Automatische Screenshot-Analyse und Kommentierung
- **Chat-Interaktion**: Beantwortet Fragen und reagiert auf Befehle
- **Automatisierung**: Regelmäßige Witze, Spielkommentare und Szenenanalyse
- **Systemd-Integration**: Autostart beim Booten

---

## 📋 Voraussetzungen

### System
- **Linux-Server** (Ubuntu 20.04+ empfohlen)
- **Python 3.8+**
- **4GB+ RAM** (für Ollama-Modelle)
- **Internetverbindung**

### APIs und Accounts
- **Twitch-Account** mit Bot-Username
- **YouTube-Kanal** mit aktivem Live-Stream
- **YouTube Data API v3 Key**
- **Ollama** installiert und konfiguriert

---

## 🛠️ Installation

### 1. Repository klonen

```bash
git clone https://github.com/derleiti/ai-twitch-bot.git zephyr
cd zephyr
```

### 2. Ollama installieren

```bash
# Ollama installieren
curl -fsSL https://ollama.ai/install.sh | sh

# Modelle herunterladen
ollama pull zephyr      # Chat-Modell
ollama pull llava       # Vision-Modell

# Ollama als Service starten
sudo systemctl enable ollama
sudo systemctl start ollama
```

### 3. Python-Abhängigkeiten

```bash
# Virtuelle Umgebung erstellen
python3 -m venv venv
source venv/bin/activate

# Abhängigkeiten installieren
pip install requests python-dotenv
```

### 4. Konfiguration erstellen

```bash
# .env-Datei erstellen
cp .env.example .env
nano .env
```

**Beispiel .env-Datei:**
```bash
# === Bot-Grundkonfiguration ===
BOT_NAME=zephyr
DEBUG_LEVEL=1

# === Platform-Aktivierung ===
ENABLE_TWITCH=true
ENABLE_YOUTUBE=true

# === Twitch-Konfiguration ===
BOT_USERNAME=dein_bot_username
OAUTH_TOKEN=oauth:dein_twitch_oauth_token
CHANNEL=#dein_twitch_kanal

# === YouTube-Konfiguration ===
YOUTUBE_API_KEY=dein_youtube_api_key
YOUTUBE_CHANNEL_ID=deine_youtube_channel_id

# === Ollama-Konfiguration ===
OLLAMA_MODEL=zephyr
VISION_MODEL=llava
```

---

## 🔑 API-Keys beschaffen

### Twitch OAuth Token
1. Gehe zu [twitchapps.com/tmi/](https://twitchapps.com/tmi/)
2. Autorisiere mit deinem Bot-Account
3. Kopiere den `oauth:...` Token in die `.env`

### YouTube API Key
1. Gehe zur [Google Cloud Console](https://console.developers.google.com/)
2. Erstelle ein neues Projekt oder wähle ein bestehendes
3. Aktiviere die **YouTube Data API v3**
4. Erstelle einen API-Key unter "Anmeldedaten"
5. Kopiere den Key in die `.env`

### YouTube Channel ID finden
1. Gehe zu [commentpicker.com/youtube-channel-id.php](https://commentpicker.com/youtube-channel-id.php)
2. Gib deine YouTube-Kanal-URL ein
3. Kopiere die Channel-ID in die `.env`

---

## 🧪 Testen der Konfiguration

### 1. Ollama-Server testen
```bash
curl http://localhost:11434/api/version
```

### 2. YouTube-Verbindung testen
```bash
python3 test_youtube.py
```

### 3. Kompletter Bot-Test
```bash
python3 multi_platform_bot.py
```

---

## 🚀 Bot starten

### Manueller Start
```bash
# Ausführbar machen
chmod +x start-multi-bot.sh

# Bot starten
./start-multi-bot.sh
```

### Als Systemd-Service
```bash
# Service erstellen (wird vom Startskript angeboten)
./start-multi-bot.sh

# Service manuell steuern
sudo systemctl start zephyr-multi-bot
sudo systemctl enable zephyr-multi-bot  # Autostart
sudo systemctl status zephyr-multi-bot
```

---

## 📊 Überwachung und Logs

### Log-Dateien
```bash
# Multi-Platform-Bot Logs
tail -f /root/zephyr/multi-platform-bot.log

# YouTube-spezifische Logs  
tail -f /root/zephyr/youtube-chat.log

# Screenshot-Watcher Logs
tail -f /root/zephyr/screenshot-watcher.log

# Alle Logs gleichzeitig
tail -f /root/zephyr/*.log
```

### Status prüfen
```bash
# Systemd-Service Status
systemctl status zephyr-multi-bot

# Prozesse anzeigen
ps aux | grep -E "(multi_platform_bot|youtube_chat|watch_screenshots)"

# PID-Datei prüfen
cat /root/zephyr/multi-platform-bot.pid
```

---

## 🎮 Verfügbare Chat-Befehle

| Befehl | Beschreibung |
|--------|--------------|
| `!witz` | Erzählt einen zufälligen Witz |
| `!info` | Zeigt aktuelle Spielinformationen |
| `!stats` | Zeigt Spielstatistiken (Tode, Level, etc.) |
| `!bild` / `!scene` | Kommentiert den aktuellen Screenshot |
| `!spiel NAME` | Setzt das aktuelle Spiel |
| `!ort NAME` | Setzt den aktuellen Ort im Spiel |
| `!tod` | Erhöht den Todeszähler |
| `!level X` | Setzt das aktuelle Level |
| `!frag zephyr ...` | Stellt eine direkte Frage an den Bot |
| `!hilfe` | Zeigt diese Befehlsliste |

---

## ⚙️ Erweiterte Konfiguration

### Timing anpassen
```bash
# In .env-Datei
AUTO_JOKE_INTERVAL=180          # Witze alle 3 Minuten
AUTO_COMMENT_INTERVAL=240       # Spielkommentare alle 4 Minuten
AUTO_SCENE_COMMENT_INTERVAL=300 # Bildkommentare alle 5 Minuten
COMMAND_REMINDER_INTERVAL=600   # Befehlserinnerungen alle 10 Minuten
```

### Screenshot-Watcher
```bash
# Screenshots-Verzeichnis erstellen
mkdir -p /root/zephyr/screenshots

# Screenshots automatisch mit ffmpeg erstellen (optional)
# Alle 30 Sekunden einen Screenshot machen:
watch -n 30 'ffmpeg -y -f x11grab -video_size 1920x1080 -i :0.0 -vframes 1 /root/zephyr/screenshots/screen_$(date +%s).jpg'
```

### Ollama-Modelle verwalten
```bash
# Verfügbare Modelle anzeigen
ollama list

# Neues Modell installieren
ollama pull mixtral     # Alternatives Chat-Modell

# Modell in .env ändern
OLLAMA_MODEL=mixtral
```

---

## 🔧 Problembehandlung

### Bot startet nicht
1. **Prüfe .env-Datei**: Alle erforderlichen Variablen gesetzt?
2. **Ollama läuft**: `systemctl status ollama`
3. **Ports frei**: `netstat -tlnp | grep 11434`
4. **Logs prüfen**: `tail -f /root/zephyr/multi-platform-bot.log`

### YouTube-Chat funktioniert nicht
1. **API-Key testen**: `python3 test_youtube.py`
2. **Live-Stream aktiv**: Muss laufen für Chat-Zugriff
3. **Quota-Limits**: YouTube API hat tägliche Limits
4. **Berechtigungen**: API-Key braucht YouTube Data API v3 Zugriff

### Twitch-Verbindung bricht ab
1. **OAuth-Token prüfen**: Token noch gültig?
2. **Rate-Limiting**: Nicht zu viele Nachrichten senden
3. **Netzwerk**: Firewall blockiert IRC-Ports?

### Bildanalyse funktioniert nicht
1. **LLaVA-Modell**: `ollama pull llava`
2. **Screenshots vorhanden**: Dateien in `/root/zephyr/screenshots/`?
3. **Speicher**: Ausreichend RAM für Vision-Modell?

### Hohe CPU/RAM-Nutzung
1. **Modell-Größe**: Kleinere Modelle verwenden (z.B. `phi3` statt `zephyr`)
2. **Intervalle**: Längere Zeitabstände zwischen automatischen Aktionen
3. **Screenshot-Anzahl**: `MAX_SCREENSHOTS` in der Konfiguration reduzieren

---

## 🔄 Updates und Wartung

### Bot aktualisieren
```bash
cd /root/zephyr
git pull origin main

# Service neu starten
sudo systemctl restart zephyr-multi-bot
```

### Log-Rotation einrichten
```bash
# Logrotate-Konfiguration erstellen
sudo nano /etc/logrotate.d/zephyr-bot

# Inhalt:
/root/zephyr/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    postrotate
        systemctl reload zephyr-multi-bot
    endscript
}
```

### Backup erstellen
```bash
# Konfiguration und Spielstand sichern
tar -czf zephyr-backup-$(date +%Y%m%d).tar.gz \
    /root/zephyr/.env \
    /root/zephyr/game_state.json \
    /root/zephyr/*.log
```

---

## 📞 Support

- **GitHub Issues**: [Repository Issues](https://github.com/derleiti/ai-twitch-bot/issues)
- **Dokumentation**: Diese Datei und Code-Kommentare
- **Logs**: Immer zuerst die Log-Dateien prüfen

---

## 📄 Lizenz

MIT License - siehe [LICENSE](LICENSE) Datei für Details.

---

## 🤝 Beitragen

Pull Requests und Issues sind willkommen! Bitte:

1. Fork das Repository
2. Erstelle einen Feature-Branch
3. Committe deine Änderungen  
4. Erstelle einen Pull Request

---

## 🔮 Roadmap

- [ ] **Discord-Integration**
- [ ] **Twitch Predictions/Polls Integration**
- [ ] **YouTube Super Chat Support**
- [ ] **Machine Learning für personalisierte Antworten**
- [ ] **Web-Dashboard zur Bot-Steuerung**
- [ ] **Multi-Language Support**
- [ ] **Voice-to-Text Integration**

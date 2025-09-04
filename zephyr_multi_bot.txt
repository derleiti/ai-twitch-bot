#!/usr/bin/env python3
"""
Zephyr Multi-Platform Bot v2.0
Vollständig integrierter Twitch + YouTube Bot mit LLaVA Bildanalyse
"""

import os
import sys
import time
import socket
import threading
import json
import re
import requests
import base64
import hashlib
import signal
import random
from datetime import datetime
from collections import deque
from dotenv import load_dotenv

# Lade Umgebungsvariablen
load_dotenv()

# === KONFIGURATION ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")
GAME_STATE_FILE = os.path.join(BASE_DIR, "game_state.json")
PID_FILE = os.path.join(BASE_DIR, "zephyr_multi_bot.pid")
VISION_CACHE_FILE = os.path.join(BASE_DIR, "latest_vision.txt")

# Erstelle Verzeichnisse
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# Bot-Konfiguration
BOT_NAME = os.getenv("BOT_NAME", "zephyr")
ENABLE_TWITCH = os.getenv("ENABLE_TWITCH", "true").lower() == "true"
ENABLE_YOUTUBE = os.getenv("ENABLE_YOUTUBE", "true").lower() == "true"
ENABLE_VISION = os.getenv("ENABLE_VISION", "true").lower() == "true"

# Twitch-Konfiguration
TWITCH_SERVER = "irc.chat.twitch.tv"
TWITCH_PORT = 6667
TWITCH_NICKNAME = os.getenv("BOT_USERNAME", "")
TWITCH_TOKEN = os.getenv("OAUTH_TOKEN", "")
TWITCH_CHANNEL = os.getenv("CHANNEL", "")

# YouTube-Konfiguration
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "")
YOUTUBE_BOT_NAME = os.getenv("YOUTUBE_BOT_NAME", "ZephyrBot")

# Ollama-Konfiguration
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "zephyr")
VISION_MODEL = os.getenv("VISION_MODEL", "llava")

# Timing-Konfiguration
SCREENSHOT_ANALYSIS_INTERVAL = int(os.getenv("SCREENSHOT_ANALYSIS_INTERVAL", "30"))
JOKE_INTERVAL = int(os.getenv("JOKE_INTERVAL", "300"))
YOUTUBE_POLLING_INTERVAL = int(os.getenv("YOUTUBE_POLLING_INTERVAL", "10"))
TWITCH_RECONNECT_DELAY = int(os.getenv("TWITCH_RECONNECT_DELAY", "30"))

# === LOGGING ===
def setup_logging():
    """Setup Logging-System"""
    global main_log, twitch_log, youtube_log, vision_log
    
    main_log = os.path.join(LOG_DIR, "main.log")
    twitch_log = os.path.join(LOG_DIR, "twitch.log")
    youtube_log = os.path.join(LOG_DIR, "youtube.log")
    vision_log = os.path.join(LOG_DIR, "vision.log")
    
    # Erstelle Log-Dateien falls nicht vorhanden
    for log_file in [main_log, twitch_log, youtube_log, vision_log]:
        if not os.path.exists(log_file):
            with open(log_file, 'w') as f:
                f.write(f"# Log started at {datetime.now()}\n")

def log_message(message, level="INFO", category="MAIN"):
    """Zentrale Logging-Funktion"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"[{timestamp}] [{level}] [{category}] {message}"
    
    print(formatted_message)
    
    # Wähle Log-Datei basierend auf Kategorie
    log_file = main_log
    if category == "TWITCH":
        log_file = twitch_log
    elif category == "YOUTUBE":
        log_file = youtube_log
    elif category == "VISION":
        log_file = vision_log
    
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{formatted_message}\n")
    except Exception as e:
        print(f"Logging-Fehler: {e}")

# === LLAVA BILDANALYSE ===
class LLaVAAnalyzer:
    def __init__(self, game_state_manager):
        self.seen_files = set()
        self.max_cache_size = 100
        self.game_state_manager = game_state_manager
    
    def get_file_hash(self, file_path):
        """Erstelle Hash für Datei"""
        try:
            mtime = os.path.getmtime(file_path)
            file_size = os.path.getsize(file_path)
            hash_str = f"{file_path}_{mtime}_{file_size}"
            return hashlib.md5(hash_str.encode()).hexdigest()
        except Exception:
            return hashlib.md5(file_path.encode()).hexdigest()
    
    def get_latest_screenshot(self):
        """Finde neuesten Screenshot"""
        try:
            screenshots = [
                os.path.join(SCREENSHOTS_DIR, f)
                for f in os.listdir(SCREENSHOTS_DIR)
                if f.lower().endswith(('.png', '.jpg', '.jpeg'))
            ]
            
            if not screenshots:
                return None
            
            # Sortiere nach Änderungszeit
            screenshots.sort(key=os.path.getmtime, reverse=True)
            return screenshots[0]
        except Exception as e:
            log_message(f"Fehler beim Finden von Screenshots: {e}", "ERROR", "VISION")
            return None
    
    def analyze_image(self, image_path):
        """Analysiere Bild mit LLaVA - detaillierte Beschreibung"""
        try:
            with open(image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
            
            # Hole aktuellen Spielstand für Kontext
            game_state = self.game_state_manager.state
            game_name = game_state.get("game", "Unbekannt")
            mood = game_state.get("mood", "Neutral")
            
            # Detaillierter Prompt für genaue Bildbeschreibung
            prompt = f"""Beschreibe GENAU was auf diesem Bildschirm zu sehen ist. 
Konzentriere dich auf:
- Was ist der Hauptinhalt (Spiel, Programm, Website)?
- Welche UI-Elemente sind sichtbar (Menüs, Buttons, HUD)?
- Welche Texte oder Zahlen sind erkennbar?
- Was passiert gerade in der Szene?
- Welche Farben dominieren?

Kontext: Es wird gerade "{game_name}" gespielt, Stimmung: {mood}.

Beschreibe in 3-4 Sätzen präzise was zu sehen ist, NICHT was es bedeutet."""
            
            payload = {
                "model": VISION_MODEL,
                "prompt": prompt,
                "images": [img_b64],
                "stream": False,
                "options": {
                    "temperature": 0.3,  # Niedrigere Temperatur für präzisere Beschreibungen
                    "num_predict": 250
                }
            }
            
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                description = result.get("response", "").strip()
                
                if description:
                    # Speichere Beschreibung für Cache
                    with open(VISION_CACHE_FILE, "w", encoding="utf-8") as f:
                        f.write(description)
                    
                    log_message(f"LLaVA-Analyse erfolgreich: {len(description)} Zeichen", "INFO", "VISION")
                    return description
            
            log_message(f"LLaVA-Fehler: Status {response.status_code}", "ERROR", "VISION")
            return None
            
        except Exception as e:
            log_message(f"Fehler bei LLaVA-Analyse: {e}", "ERROR", "VISION")
            return None
    
    def summarize_llava_response(self, description):
        """Fasse LLaVA-Response zusammen mit Fokus auf Details"""
        if not description:
            return "Keine Bildbeschreibung verfügbar"
        
        # Hole Spielstand für Kontext
        game_state = self.game_state_manager.state
        game_name = game_state.get("game", "Unbekannt")
        
        # Extrahiere die wichtigsten Details
        sentences = re.split(r'[.!?]+', description.strip())
        
        # Priorisiere Sätze mit konkreten Details
        detail_keywords = ['zeigt', 'sichtbar', 'erkennt', 'sieht', 'befindet', 'steht', 'läuft', 'öffnet']
        detailed_sentences = []
        
        for sentence in sentences:
            if any(keyword in sentence.lower() for keyword in detail_keywords):
                detailed_sentences.append(sentence.strip())
        
        # Nehme die ersten 2 detaillierten Sätze oder normale Sätze
        if detailed_sentences:
            summary = '. '.join(detailed_sentences[:2])
        else:
            summary = '. '.join(sentences[:2])
        
        summary = summary.strip()
        if not summary.endswith('.'):
            summary += '.'
        
        # Füge spezifischen Tag basierend auf erkanntem Inhalt hinzu
        tags = {
            "spiel": f"🎮 {game_name}",
            "game": f"🎮 {game_name}", 
            "menu": "📋 Menü",
            "menü": "📋 Menü",
            "code": "💻 Code",
            "browser": "🌐 Browser",
            "terminal": "⌨️ Terminal",
            "desktop": "🖥️ Desktop",
            "kampf": "⚔️ Kampf",
            "battle": "⚔️ Kampf",
            "inventory": "🎒 Inventar",
            "inventar": "🎒 Inventar",
            "dialog": "💬 Dialog",
            "karte": "🗺️ Karte",
            "map": "🗺️ Karte"
        }
        
        tag = "📸 Screenshot"
        description_lower = description.lower()
        for keyword, emoji in tags.items():
            if keyword in description_lower:
                tag = emoji
                break
        
        return f"{tag} {summary}"
    
    def check_for_new_screenshot(self):
        """Prüfe auf neue Screenshots"""
        screenshot = self.get_latest_screenshot()
        if not screenshot:
            return None
        
        file_hash = self.get_file_hash(screenshot)
        if file_hash in self.seen_files:
            return None
        
        self.seen_files.add(file_hash)
        
        # Cache-Management
        if len(self.seen_files) > self.max_cache_size:
            # Entferne älteste Einträge
            self.seen_files = set(list(self.seen_files)[-self.max_cache_size:])
        
        return screenshot

# === GAME STATE ===
class GameStateManager:
    def __init__(self):
        self.state = self.load_game_state()
    
    def load_game_state(self):
        """Lade Spielstand"""
        try:
            if os.path.exists(GAME_STATE_FILE):
                with open(GAME_STATE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # Erstelle Standard-Spielstand
                default_state = {
                    "game": "Unbekannt",
                    "mood": "Neutral",
                    "player_status": "aktiv"
                }
                self.save_game_state(default_state)
                return default_state
        except Exception as e:
            log_message(f"Fehler beim Laden des Spielstands: {e}", "ERROR", "MAIN")
            return {"game": "Unbekannt", "mood": "Neutral", "player_status": "aktiv"}
    
    def save_game_state(self, state):
        """Speichere Spielstand"""
        try:
            with open(GAME_STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            self.state = state
        except Exception as e:
            log_message(f"Fehler beim Speichern des Spielstands: {e}", "ERROR", "MAIN")
    
    def update_game(self, game_name):
        """Update Spielname"""
        self.state["game"] = game_name
        self.save_game_state(self.state)
        log_message(f"Spiel geändert zu: {game_name}", "INFO", "MAIN")
    
    def update_mood(self, mood):
        """Update Stimmung"""
        self.state["mood"] = mood
        self.save_game_state(self.state)
        log_message(f"Stimmung geändert zu: {mood}", "INFO", "MAIN")
    
    def get_context_string(self):
        """Hole Kontext-String für Chat"""
        return f"[{self.state.get('game', 'Unbekannt')} | {self.state.get('mood', 'Neutral')}]"

# === TWITCH CLIENT ===
class TwitchClient:
    def __init__(self, message_callback):
        self.message_callback = message_callback
        self.sock = None
        self.running = False
        self.connected = False
        self.thread = None
        self.last_ping_time = 0
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
    
    def start(self):
        """Starte Twitch-Client"""
        if not ENABLE_TWITCH or not TWITCH_NICKNAME or not TWITCH_TOKEN:
            log_message("Twitch deaktiviert oder unvollständige Konfiguration", "WARNING", "TWITCH")
            return False
        
        self.running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()
        return True
    
    def _run(self):
        """Hauptloop für Twitch mit verbessertem Reconnect"""
        while self.running:
            try:
                if self._connect():
                    self.reconnect_attempts = 0  # Reset bei erfolgreicher Verbindung
                    self._listen()
                else:
                    self.reconnect_attempts += 1
                    if self.reconnect_attempts >= self.max_reconnect_attempts:
                        log_message("Max Reconnect-Versuche erreicht, gebe auf", "ERROR", "TWITCH")
                        self.running = False
                        break
                    
                    wait_time = min(TWITCH_RECONNECT_DELAY * self.reconnect_attempts, 300)  # Max 5 Minuten
                    log_message(f"Warte {wait_time}s vor Reconnect-Versuch {self.reconnect_attempts}", "INFO", "TWITCH")
                    time.sleep(wait_time)
                    
            except Exception as e:
                log_message(f"Twitch-Verbindungsfehler: {e}", "ERROR", "TWITCH")
                self.connected = False
                time.sleep(TWITCH_RECONNECT_DELAY)
    
    def _connect(self):
        """Verbinde zu Twitch IRC mit besserem Error Handling"""
        try:
            # Schließe alte Verbindung falls vorhanden
            if self.sock:
                try:
                    self.sock.close()
                except:
                    pass
                self.sock = None
            
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            
            log_message(f"Verbinde zu Twitch IRC ({TWITCH_SERVER}:{TWITCH_PORT})...", "INFO", "TWITCH")
            self.sock.connect((TWITCH_SERVER, TWITCH_PORT))
            
            # Authentifizierung
            self.sock.send(f"PASS {TWITCH_TOKEN}\r\n".encode('utf-8'))
            self.sock.send(f"NICK {TWITCH_NICKNAME}\r\n".encode('utf-8'))
            
            # Warte auf Willkommensnachricht
            auth_success = False
            start_time = time.time()
            
            while time.time() - start_time < 15:  # 15 Sekunden Timeout
                try:
                    response = self.sock.recv(2048).decode('utf-8', errors='ignore')
                    log_message(f"Auth Response: {response.strip()}", "DEBUG", "TWITCH")
                    
                    if "Welcome, GLHF!" in response or ":tmi.twitch.tv 001" in response:
                        auth_success = True
                        break
                    elif "Login authentication failed" in response:
                        log_message("Twitch Login fehlgeschlagen - prüfe OAuth Token", "ERROR", "TWITCH")
                        return False
                except socket.timeout:
                    continue
            
            if not auth_success:
                log_message("Twitch Authentifizierung Timeout", "ERROR", "TWITCH")
                return False
            
            # Capabilities
            self.sock.send("CAP REQ :twitch.tv/membership\r\n".encode('utf-8'))
            self.sock.send("CAP REQ :twitch.tv/tags\r\n".encode('utf-8'))
            self.sock.send("CAP REQ :twitch.tv/commands\r\n".encode('utf-8'))
            
            # Channel beitreten
            time.sleep(1)  # Kurze Pause vor Join
            self.sock.send(f"JOIN {TWITCH_CHANNEL}\r\n".encode('utf-8'))
            
            # Warte auf Join-Bestätigung
            join_success = False
            start_time = time.time()
            
            while time.time() - start_time < 10:
                try:
                    response = self.sock.recv(2048).decode('utf-8', errors='ignore')
                    if f":{TWITCH_NICKNAME}!{TWITCH_NICKNAME}@{TWITCH_NICKNAME}.tmi.twitch.tv JOIN {TWITCH_CHANNEL}" in response:
                        join_success = True
                        break
                    elif "msg_channel_suspended" in response:
                        log_message(f"Channel {TWITCH_CHANNEL} ist suspended", "ERROR", "TWITCH")
                        return False
                except socket.timeout:
                    continue
            
            if join_success:
                self.connected = True
                self.last_ping_time = time.time()
                log_message(f"Erfolgreich mit Twitch verbunden: {TWITCH_CHANNEL}", "INFO", "TWITCH")
                
                # Begrüßung
                time.sleep(2)  # Warte kurz vor erster Nachricht
                self.send_message(f"👋 {BOT_NAME} ist online! Befehle: !witz, !bild, !info, !spiel NAME, !stimmung MOOD")
                return True
            else:
                log_message("Channel-Join fehlgeschlagen", "ERROR", "TWITCH")
                return False
                
        except socket.error as e:
            log_message(f"Socket-Fehler bei Twitch-Verbindung: {e}", "ERROR", "TWITCH")
            self.connected = False
            return False
        except Exception as e:
            log_message(f"Unerwarteter Fehler bei Twitch-Verbindung: {e}", "ERROR", "TWITCH")
            self.connected = False
            return False
    
    def _listen(self):
        """Höre auf Nachrichten mit verbessertem Error Handling"""
        buffer = ""
        
        while self.running and self.connected:
            try:
                # Socket Timeout für regelmäßige Ping-Checks
                self.sock.settimeout(1.0)
                
                try:
                    data = self.sock.recv(2048).decode('utf-8', errors='ignore')
                    if not data:
                        log_message("Twitch-Verbindung geschlossen (keine Daten)", "WARNING", "TWITCH")
                        self.connected = False
                        break
                    
                    buffer += data
                    lines = buffer.split('\r\n')
                    buffer = lines[-1]  # Behalte unvollständige Zeile
                    
                    for line in lines[:-1]:
                        if not line:
                            continue
                        
                        # PING/PONG
                        if line.startswith('PING'):
                            self.sock.send(f"PONG{line[4:]}\r\n".encode('utf-8'))
                            log_message("PING beantwortet", "DEBUG", "TWITCH")
                            continue
                        
                        # Chat-Nachrichten
                        if 'PRIVMSG' in line:
                            self._handle_message(line)
                    
                    # Update Ping-Zeit bei erfolgreicher Kommunikation
                    self.last_ping_time = time.time()
                    
                except socket.timeout:
                    # Prüfe ob wir einen PING senden sollten
                    if time.time() - self.last_ping_time > 30:
                        self.sock.send("PING :tmi.twitch.tv\r\n".encode('utf-8'))
                        self.last_ping_time = time.time()
                    continue
                    
            except (socket.error, ConnectionResetError, BrokenPipeError) as e:
                log_message(f"Twitch-Verbindung verloren: {e}", "ERROR", "TWITCH")
                self.connected = False
                break
            except Exception as e:
                log_message(f"Unerwarteter Fehler beim Twitch-Listen: {e}", "ERROR", "TWITCH")
                self.connected = False
                break
    
    def _handle_message(self, line):
        """Verarbeite Chat-Nachricht"""
        try:
            # Extrahiere Username
            match = re.search(r':([^!]+)!', line)
            if not match:
                return
            
            username = match.group(1)
            
            # Extrahiere Nachricht
            if 'PRIVMSG' in line:
                message = line.split('PRIVMSG', 1)[1].split(':', 1)[1].strip()
                
                # Ignoriere eigene Nachrichten
                if username.lower() == BOT_NAME.lower():
                    return
                
                log_message(f"{username}: {message}", "INFO", "TWITCH")
                
                # Callback aufrufen
                if self.message_callback:
                    self.message_callback("twitch", username, message)
                    
        except Exception as e:
            log_message(f"Fehler beim Verarbeiten der Twitch-Nachricht: {e}", "ERROR", "TWITCH")
    
    def send_message(self, message):
        """Sende Nachricht mit Error Handling"""
        if not self.connected or not self.sock:
            log_message("Kann nicht senden - nicht verbunden", "WARNING", "TWITCH")
            return False
        
        try:
            # Begrenze Nachrichtenlänge (Twitch IRC Limit)
            if len(message) > 450:
                message = message[:447] + "..."
            
            self.sock.send(f"PRIVMSG {TWITCH_CHANNEL} :{message}\r\n".encode('utf-8'))
            log_message(f"Gesendet: {message}", "INFO", "TWITCH")
            return True
        except (socket.error, BrokenPipeError) as e:
            log_message(f"Fehler beim Senden (Verbindung verloren): {e}", "ERROR", "TWITCH")
            self.connected = False
            return False
        except Exception as e:
            log_message(f"Unerwarteter Fehler beim Senden: {e}", "ERROR", "TWITCH")
            return False
    
    def stop(self):
        """Stoppe Twitch-Client"""
        self.running = False
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        log_message("Twitch-Client gestoppt", "INFO", "TWITCH")

# === YOUTUBE CLIENT ===
class YouTubeClient:
    def __init__(self, message_callback):
        self.message_callback = message_callback
        self.running = False
        self.thread = None
        self.live_video_id = None
        self.live_chat_id = None
        self.next_page_token = None
        self.seen_message_ids = set()
    
    def start(self):
        """Starte YouTube-Client"""
        if not ENABLE_YOUTUBE or not YOUTUBE_API_KEY or not YOUTUBE_CHANNEL_ID:
            log_message("YouTube deaktiviert oder unvollständige Konfiguration", "WARNING", "YOUTUBE")
            return False
        
        self.running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()
        return True
    
    def _run(self):
        """Hauptloop für YouTube"""
        while self.running:
            try:
                if not self.live_chat_id:
                    self._find_live_stream()
                
                if self.live_chat_id:
                    self._read_messages()
                
                time.sleep(YOUTUBE_POLLING_INTERVAL)
                
            except Exception as e:
                log_message(f"YouTube-Fehler: {e}", "ERROR", "YOUTUBE")
                time.sleep(30)
    
    def _find_live_stream(self):
        """Finde Live-Stream"""
        try:
            params = {
                "part": "id,snippet",
                "channelId": YOUTUBE_CHANNEL_ID,
                "eventType": "live",
                "type": "video",
                "key": YOUTUBE_API_KEY,
                "maxResults": 1
            }
            
            response = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("items"):
                    video = data["items"][0]
                    self.live_video_id = video["id"]["videoId"]
                    
                    # Hole Chat-ID
                    self._get_chat_id()
                    
        except Exception as e:
            log_message(f"Fehler beim Finden des Live-Streams: {e}", "ERROR", "YOUTUBE")
    
    def _get_chat_id(self):
        """Hole Chat-ID"""
        try:
            params = {
                "part": "liveStreamingDetails",
                "id": self.live_video_id,
                "key": YOUTUBE_API_KEY
            }
            
            response = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("items"):
                    video = data["items"][0]
                    live_details = video.get("liveStreamingDetails", {})
                    self.live_chat_id = live_details.get("activeLiveChatId")
                    
                    if self.live_chat_id:
                        log_message(f"YouTube Live Chat gefunden", "INFO", "YOUTUBE")
                        
        except Exception as e:
            log_message(f"Fehler beim Holen der Chat-ID: {e}", "ERROR", "YOUTUBE")
    
    def _read_messages(self):
        """Lese Chat-Nachrichten"""
        try:
            params = {
                "liveChatId": self.live_chat_id,
                "part": "id,snippet,authorDetails",
                "key": YOUTUBE_API_KEY,
                "maxResults": 50
            }
            
            if self.next_page_token:
                params["pageToken"] = self.next_page_token
            
            response = requests.get(
                "https://www.googleapis.com/youtube/v3/liveChat/messages",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.next_page_token = data.get("nextPageToken")
                
                for item in data.get("items", []):
                    self._process_message(item)
                    
            elif response.status_code == 404:
                log_message("Live Chat nicht mehr aktiv", "WARNING", "YOUTUBE")
                self.live_chat_id = None
                
        except Exception as e:
            log_message(f"Fehler beim Lesen der YouTube-Nachrichten: {e}", "ERROR", "YOUTUBE")
    
    def _process_message(self, item):
        """Verarbeite einzelne Nachricht"""
        try:
            message_id = item.get("id", "")
            if message_id in self.seen_message_ids:
                return
            
            self.seen_message_ids.add(message_id)
            
            # Cache-Management
            if len(self.seen_message_ids) > 1000:
                self.seen_message_ids = set(list(self.seen_message_ids)[-500:])
            
            snippet = item.get("snippet", {})
            author_details = item.get("authorDetails", {})
            
            username = author_details.get("displayName", "Unknown")
            message = snippet.get("displayMessage", "")
            
            # Filtere Bot-Nachrichten
            if username.lower() == YOUTUBE_BOT_NAME.lower():
                return
            
            # Filtere leere Nachrichten
            if not message.strip():
                return
            
            log_message(f"{username}: {message}", "INFO", "YOUTUBE")
            
            # Callback aufrufen
            if self.message_callback:
                self.message_callback("youtube", username, message)
                
        except Exception as e:
            log_message(f"Fehler beim Verarbeiten der YouTube-Nachricht: {e}", "ERROR", "YOUTUBE")
    
    def send_message(self, message):
        """Sende Nachricht (Simulation)"""
        # YouTube API benötigt OAuth2 für das Senden von Nachrichten
        # Hier nur Simulation
        log_message(f"YouTube Nachricht (simuliert): {message}", "INFO", "YOUTUBE")
        return True
    
    def stop(self):
        """Stoppe YouTube-Client"""
        self.running = False

# === OLLAMA CLIENT ===
class OllamaClient:
    def __init__(self):
        self.base_url = OLLAMA_BASE_URL
        self.model = OLLAMA_MODEL
    
    def generate_response(self, prompt):
        """Generiere Antwort mit Ollama"""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 200
                }
            }
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                log_message(f"Ollama-Fehler: Status {response.status_code}", "ERROR", "MAIN")
                return None
                
        except Exception as e:
            log_message(f"Fehler bei Ollama-Anfrage: {e}", "ERROR", "MAIN")
            return None
    
    def generate_joke(self):
        """Generiere Witz"""
        prompt = "Erzähle einen kurzen, lustigen Gaming-Witz. Maximal 2 Sätze."
        return self.generate_response(prompt)
    
    def answer_question(self, question):
        """Beantworte Frage"""
        prompt = f"Beantworte diese Frage kurz und hilfreich: {question}"
        return self.generate_response(prompt)

# === HAUPTBOT ===
class ZephyrMultiBot:
    def __init__(self):
        self.running = False
        self.twitch_client = None
        self.youtube_client = None
        self.game_state = GameStateManager()
        self.llava_analyzer = LLaVAAnalyzer(self.game_state)
        self.ollama_client = OllamaClient()
        
        # Fallback-Witze
        self.fallback_jokes = [
            "Warum können Skelette so schlecht lügen? Man sieht ihnen durch die Rippen!",
            "Was ist rot und schlecht für die Zähne? Ein Ziegelstein.",
            "Wie nennt man einen Cowboy ohne Pferd? Sattelschlepper.",
            "Warum ging der Gamer zum Arzt? Er hatte einen Bug!",
            "Was sagt ein großer Stift zum kleinen Stift? Wachs-mal-stift!"
        ]
        
        # Timers
        self.last_joke_time = 0
        self.last_screenshot_time = 0
        
        # Setup
        setup_logging()
        self.create_pid_file()
        self.setup_signal_handlers()
        
        log_message("Zephyr Multi-Bot v2.0 initialisiert", "INFO", "MAIN")
    
    def create_pid_file(self):
        """Erstelle PID-Datei"""
        try:
            with open(PID_FILE, 'w') as f:
                f.write(str(os.getpid()))
            log_message(f"PID-Datei erstellt: {os.getpid()}", "INFO", "MAIN")
        except Exception as e:
            log_message(f"Fehler beim Erstellen der PID-Datei: {e}", "ERROR", "MAIN")
    
    def remove_pid_file(self):
        """Entferne PID-Datei"""
        try:
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
                log_message("PID-Datei entfernt", "INFO", "MAIN")
        except Exception as e:
            log_message(f"Fehler beim Entfernen der PID-Datei: {e}", "ERROR", "MAIN")
    
    def setup_signal_handlers(self):
        """Setup Signal-Handler"""
        def signal_handler(signum, frame):
            log_message(f"Signal {signum} empfangen, beende Bot...", "INFO", "MAIN")
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def message_handler(self, platform, username, message):
        """Zentrale Nachrichtenverarbeitung"""
        try:
            # Befehle verarbeiten
            if message.lower() == "!witz":
                self.send_joke(platform)
            elif message.lower() == "!bild":
                self.send_image_analysis(platform)
            elif message.lower() == "!info":
                self.send_info(platform)
            elif message.lower().startswith("!spiel "):
                game_name = message[7:].strip()
                self.game_state.update_game(game_name)
                self.send_to_platform(platform, f"🎮 Spiel geändert zu: {game_name}")
            elif message.lower().startswith("!stimmung "):
                mood = message[10:].strip()
                self.game_state.update_mood(mood)
                self.send_to_platform(platform, f"🎭 Stimmung geändert zu: {mood}")
            elif message.lower().startswith("!frag "):
                question = message[6:].strip()
                self.answer_question(platform, username, question)
            elif BOT_NAME.lower() in message.lower():
                self.respond_to_mention(platform, username, message)
                
        except Exception as e:
            log_message(f"Fehler bei Nachrichtenverarbeitung: {e}", "ERROR", "MAIN")
    
    def send_joke(self, platform):
        """Sende Witz"""
        try:
            joke = self.ollama_client.generate_joke()
            if not joke:
                joke = random.choice(self.fallback_jokes)
            
            message = f"🎭 {joke}"
            self.send_to_platform(platform, message)
            
        except Exception as e:
            log_message(f"Fehler beim Senden des Witzes: {e}", "ERROR", "MAIN")
    
    def send_image_analysis(self, platform):
        """Sende Bildanalyse"""
        try:
            screenshot = self.llava_analyzer.get_latest_screenshot()
            if not screenshot:
                self.send_to_platform(platform, "👁️ Kein Screenshot zum Analysieren gefunden.")
                return
            
            description = self.llava_analyzer.analyze_image(screenshot)
            if description:
                summary = self.llava_analyzer.summarize_llava_response(description)
                context = self.game_state.get_context_string()
                message = f"{summary} {context}"
                self.send_to_platform(platform, message)
            else:
                self.send_to_platform(platform, "👁️ Bildanalyse fehlgeschlagen.")
                
        except Exception as e:
            log_message(f"Fehler bei Bildanalyse: {e}", "ERROR", "MAIN")
    
    def send_info(self, platform):
        """Sende Info"""
        try:
            context = self.game_state.get_context_string()
            message = f"ℹ️ Status: {context} | Befehle: !witz, !bild, !spiel NAME, !stimmung MOOD"
            self.send_to_platform(platform, message)
        except Exception as e:
            log_message(f"Fehler beim Senden der Info: {e}", "ERROR", "MAIN")
    
    def answer_question(self, platform, username, question):
        """Beantworte Frage"""
        try:
            answer = self.ollama_client.answer_question(question)
            if answer:
                message = f"@{username} {answer}"
                self.send_to_platform(platform, message)
            else:
                message = f"@{username} Entschuldige, ich konnte keine Antwort finden."
                self.send_to_platform(platform, message)
        except Exception as e:
            log_message(f"Fehler beim Beantworten der Frage: {e}", "ERROR", "MAIN")
    
    def respond_to_mention(self, platform, username, message):
        """Reagiere auf Erwähnung"""
        try:
            if "?" in message:
                question = message.replace(BOT_NAME, "").strip()
                self.answer_question(platform, username, question)
            else:
                greetings = [
                    f"Hi @{username}! 👋",
                    f"Hallo @{username}! Was kann ich für dich tun?",
                    f"Hey @{username}! Befehle: !witz, !bild, !info, !spiel, !stimmung"
                ]
                message = random.choice(greetings)
                self.send_to_platform(platform, message)
        except Exception as e:
            log_message(f"Fehler bei Erwähnung: {e}", "ERROR", "MAIN")
    
    def send_to_platform(self, platform, message):
        """Sende Nachricht an Platform"""
        try:
            if platform == "twitch" and self.twitch_client:
                self.twitch_client.send_message(message)
            elif platform == "youtube" and self.youtube_client:
                self.youtube_client.send_message(message)
        except Exception as e:
            log_message(f"Fehler beim Senden an {platform}: {e}", "ERROR", "MAIN")
    
    def auto_screenshot_analysis(self):
        """Automatische Screenshot-Analyse"""
        while self.running:
            try:
                current_time = time.time()
                
                if current_time - self.last_screenshot_time >= SCREENSHOT_ANALYSIS_INTERVAL:
                    screenshot = self.llava_analyzer.check_for_new_screenshot()
                    
                    if screenshot:
                        log_message(f"Neuer Screenshot gefunden: {screenshot}", "INFO", "VISION")
                        
                        description = self.llava_analyzer.analyze_image(screenshot)
                        if description:
                            summary = self.llava_analyzer.summarize_llava_response(description)
                            context = self.game_state.get_context_string()
                            message = f"{summary} {context}"
                            
                            # Sende an alle aktiven Platformen
                            if self.twitch_client and self.twitch_client.connected:
                                self.twitch_client.send_message(message)
                            if self.youtube_client:
                                self.youtube_client.send_message(message)
                    
                    self.last_screenshot_time = current_time
                
                time.sleep(5)  # Kurze Pause zwischen Checks
                
            except Exception as e:
                log_message(f"Fehler bei automatischer Screenshot-Analyse: {e}", "ERROR", "VISION")
                time.sleep(10)
    
    def auto_jokes(self):
        """Automatische Witze"""
        while self.running:
            try:
                current_time = time.time()
                
                if current_time - self.last_joke_time >= JOKE_INTERVAL:
                    joke = self.ollama_client.generate_joke()
                    if not joke:
                        joke = random.choice(self.fallback_jokes)
                    
                    message = f"🎭 {joke}"
                    
                    # Sende an alle aktiven Platformen
                    if self.twitch_client and self.twitch_client.connected:
                        self.twitch_client.send_message(message)
                    if self.youtube_client:
                        self.youtube_client.send_message(message)
                    
                    self.last_joke_time = current_time
                
                time.sleep(30)  # Check alle 30 Sekunden
                
            except Exception as e:
                log_message(f"Fehler bei automatischen Witzen: {e}", "ERROR", "MAIN")
                time.sleep(30)
    
    def status_monitor(self):
        """Überwacht Status der Komponenten"""
        while self.running:
            try:
                # Status-Log alle 5 Minuten
                status_parts = []
                
                if self.twitch_client:
                    twitch_status = "✅ Verbunden" if self.twitch_client.connected else "❌ Getrennt"
                    status_parts.append(f"Twitch: {twitch_status}")
                
                if self.youtube_client:
                    youtube_status = "✅ Aktiv" if self.youtube_client.live_chat_id else "❌ Kein Stream"
                    status_parts.append(f"YouTube: {youtube_status}")
                
                status_parts.append(f"Spiel: {self.game_state.state.get('game', 'Unbekannt')}")
                status_parts.append(f"Stimmung: {self.game_state.state.get('mood', 'Neutral')}")
                
                log_message(" | ".join(status_parts), "INFO", "MAIN")
                
                time.sleep(300)  # 5 Minuten
                
            except Exception as e:
                log_message(f"Fehler im Status-Monitor: {e}", "ERROR", "MAIN")
                time.sleep(60)
    
    def start(self):
        """Starte Bot"""
        try:
            log_message("Starte Zephyr Multi-Bot v2.0...", "INFO", "MAIN")
            self.running = True
            
            # Prüfe Ollama-Verfügbarkeit
            try:
                response = requests.get(f"{OLLAMA_BASE_URL}/api/version", timeout=5)
                if response.status_code == 200:
                    log_message("Ollama-Server erreichbar", "INFO", "MAIN")
                else:
                    log_message("Ollama-Server nicht erreichbar - einige Features deaktiviert", "WARNING", "MAIN")
            except:
                log_message("Ollama-Server nicht erreichbar - einige Features deaktiviert", "WARNING", "MAIN")
            
            # Starte Clients
            if ENABLE_TWITCH:
                self.twitch_client = TwitchClient(self.message_handler)
                self.twitch_client.start()
                log_message("Twitch-Client gestartet", "INFO", "MAIN")
            
            if ENABLE_YOUTUBE:
                self.youtube_client = YouTubeClient(self.message_handler)
                self.youtube_client.start()
                log_message("YouTube-Client gestartet", "INFO", "MAIN")
            
            # Starte Background-Threads
            if ENABLE_VISION:
                screenshot_thread = threading.Thread(target=self.auto_screenshot_analysis)
                screenshot_thread.daemon = True
                screenshot_thread.start()
                log_message("Screenshot-Analyse gestartet", "INFO", "VISION")
            
            joke_thread = threading.Thread(target=self.auto_jokes)
            joke_thread.daemon = True
            joke_thread.start()
            log_message("Automatische Witze gestartet", "INFO", "MAIN")
            
            status_thread = threading.Thread(target=self.status_monitor)
            status_thread.daemon = True
            status_thread.start()
            log_message("Status-Monitor gestartet", "INFO", "MAIN")
            
            log_message("Bot erfolgreich gestartet", "INFO", "MAIN")
            return True
            
        except Exception as e:
            log_message(f"Fehler beim Starten: {e}", "ERROR", "MAIN")
            return False
    
    def stop(self):
        """Stoppe Bot"""
        try:
            log_message("Stoppe Zephyr Multi-Bot...", "INFO", "MAIN")
            self.running = False
            
            if self.twitch_client:
                self.twitch_client.stop()
            if self.youtube_client:
                self.youtube_client.stop()
            
            self.remove_pid_file()
            log_message("Bot gestoppt", "INFO", "MAIN")
            
        except Exception as e:
            log_message(f"Fehler beim Stoppen: {e}", "ERROR", "MAIN")
    
    def run(self):
        """Hauptschleife"""
        if not self.start():
            log_message("Bot konnte nicht gestartet werden", "ERROR", "MAIN")
            return
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            log_message("Bot durch Benutzer beendet", "INFO", "MAIN")
        finally:
            self.stop()

# === MAIN ===
def main():
    """Hauptfunktion"""
    print("🤖 Zephyr Multi-Platform Bot v2.0")
    print("=" * 40)
    
    bot = ZephyrMultiBot()
    bot.run()

if __name__ == "__main__":
    main()

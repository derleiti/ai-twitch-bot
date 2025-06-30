#!/usr/bin/env python3
# multi_platform_bot.py - Multi-Platform Twitch + YouTube Bot mit Ollama-Integration

import subprocess
import socket
import time
import random
import threading
import requests
import os
import json
import traceback
import re
import base64
from datetime import datetime
from collections import Counter, defaultdict
from dotenv import load_dotenv

# Importiere YouTube Chat Reader
try:
    from youtube_chat_reader import start_youtube_chat_reader, stop_youtube_chat_reader, get_status as get_youtube_status, test_youtube_connection
    YOUTUBE_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ YouTube Chat Reader nicht verfügbar: {e}")
    YOUTUBE_AVAILABLE = False

# Lade Umgebungsvariablen aus .env Datei
load_dotenv()

# === Konfiguration ===
# Twitch IRC Konfiguration
SERVER = "irc.chat.twitch.tv"
PORT = 6667
NICKNAME = os.getenv("BOT_USERNAME", "")       # Dein Bot-Benutzername
TOKEN = os.getenv("OAUTH_TOKEN", "")           # OAuth Token: https://twitchapps.com/tmi/
CHANNEL = os.getenv("CHANNEL", "")             # Kanal, dem der Bot beitreten soll
BOT_NAME = os.getenv("BOT_NAME", "zephyr")     # Anzeigename des Bots im Chat

# Multi-Platform Settings
ENABLE_TWITCH = os.getenv("ENABLE_TWITCH", "true").lower() == "true"
ENABLE_YOUTUBE = os.getenv("ENABLE_YOUTUBE", "true").lower() == "true" and YOUTUBE_AVAILABLE

# Prüfung der kritischen Umgebungsvariablen
missing_vars = []
if ENABLE_TWITCH and (not NICKNAME or not TOKEN or not CHANNEL):
    missing_vars.extend(["BOT_USERNAME", "OAUTH_TOKEN", "CHANNEL"])

if ENABLE_YOUTUBE and not YOUTUBE_AVAILABLE:
    print("⚠️ YouTube aktiviert, aber youtube_chat_reader.py nicht verfügbar")

if missing_vars:
    print(f"⚠️ Kritische Umgebungsvariablen fehlen: {', '.join(missing_vars)}")
    print("Bitte .env-Datei prüfen")

# Ollama-Konfiguration
OLLAMA_API_VERSION = os.getenv("OLLAMA_API_VERSION", "legacy")
OLLAMA_ENDPOINTS = {
    "legacy": {
        "generate": os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate"),
        "chat": os.getenv("OLLAMA_CHAT_URL", "http://localhost:11434/api/chat")
    },
    "v1": {
        "generate": os.getenv("OLLAMA_URL_V1", "http://localhost:11434/v1/generate"),
        "chat": os.getenv("OLLAMA_CHAT_URL_V1", "http://localhost:11434/v1/chat/completions")
    }
}

# Modelle
MODEL = os.getenv("OLLAMA_MODEL", "mixtral:8x7b")
VISION_MODEL = os.getenv("VISION_MODEL", "llava:latest")

# Pfade und Dateien
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if not os.path.exists(BASE_DIR):
    BASE_DIR = os.path.expanduser("~/zephyr")
    os.makedirs(BASE_DIR, exist_ok=True)
    print(f"BASE_DIR nicht gefunden, verwende: {BASE_DIR}")

LOG_FILE = os.path.join(BASE_DIR, "multi-platform-bot.log")
GAME_STATE_FILE = os.path.join(BASE_DIR, "game_state.json")
PID_FILE = os.path.join(BASE_DIR, "multi-platform-bot.pid")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")
VISION_CACHE_FILE = os.path.join(BASE_DIR, "latest_vision.txt")

# Timing-Konfiguration
AUTO_JOKE_INTERVAL = int(os.getenv("AUTO_JOKE_INTERVAL", "180"))
AUTO_COMMENT_INTERVAL = int(os.getenv("AUTO_COMMENT_INTERVAL", "240"))
AUTO_SCENE_COMMENT_INTERVAL = int(os.getenv("AUTO_SCENE_COMMENT_INTERVAL", "300"))
COMMAND_REMINDER_INTERVAL = int(os.getenv("COMMAND_REMINDER_INTERVAL", "600"))
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "60"))
RECONNECT_DELAY = int(os.getenv("RECONNECT_DELAY", "10"))
PING_INTERVAL = int(os.getenv("PING_INTERVAL", "30"))
SOCKET_TIMEOUT = int(os.getenv("SOCKET_TIMEOUT", "15"))
OLLAMA_RETRY_COUNT = int(os.getenv("OLLAMA_RETRY_COUNT", "3"))

# Debug-Level (0=minimal, 1=normal, 2=ausführlich)
DEBUG_LEVEL = int(os.getenv("DEBUG_LEVEL", "1"))

# === Vordefinierte Text-Antworten ===
WITZE = [
    "Warum können Skelette so schlecht lügen? Man sieht ihnen durch die Rippen!",
    "Was ist rot und schlecht für die Zähne? Ein Ziegelstein.",
    "Wie nennt man einen Cowboy ohne Pferd? Sattelschlepper.",
    "Warum sollte man nie Poker mit einem Zauberer spielen? Weil er Asse im Ärmel hat!",
    "Kommt ein Pferd in die Bar. Fragt der Barkeeper: 'Warum so ein langes Gesicht?'",
    "Was sagt ein Bauer, wenn er sein Traktor verloren hat? 'Wo ist mein Traktor?'",
    "Wie nennt man einen dicken Vegetarier? Biotonne.",
    "Wie nennt man einen Boomerang, der nicht zurückkommt? Stock.",
    "Was ist braun, klebrig und läuft durch die Wüste? Ein Karamel.",
    "Warum hat der Mathematiker seine Frau verlassen? Sie hat etwas mit X gemacht.",
    "Was ist grün und steht vor der Tür? Ein Klopfsalat!",
    "Was sitzt auf dem Baum und schreit 'Aha'? Ein Uhu mit Sprachfehler!",
    "Was ist schwarz-weiß und kommt nicht vom Fleck? Eine Zeitung!",
    "Was macht ein Pirat beim Camping? Er schlägt sein Segel auf!",
    "Treffen sich zwei Jäger im Wald. Beide tot.",
    "Was ist ein Keks unter einem Baum? Ein schattiges Plätzchen!",
    "Was passiert, wenn man Cola und Bier gleichzeitig trinkt? Man colabiert.",
    "Warum können Seeräuber schlecht mit Kreisen rechnen? Weil sie Pi raten."
]

GAME_KOMMENTARE = [
    "Dieser Boss sieht gefährlich aus! Pass auf die Angriffe auf!",
    "Nice! Das war ein guter Move!",
    "Oh, knapp vorbei! Beim nächsten Mal klappt's bestimmt.",
    "Die Grafik in diesem Spiel ist wirklich beeindruckend!",
    "Hast du schon alle Geheimnisse in diesem Level gefunden?",
    "Ich würde an deiner Stelle nach Heilung suchen, deine HP sind ziemlich niedrig.",
    "Diese Gegner-KI ist ziemlich schlau!",
    "Perfektes Timing bei diesem Sprung!",
    "Vielleicht solltest du deine Ausrüstung upgraden?"
]

SCENE_KOMMENTARE = [
    "Die Grafik sieht wirklich fantastisch aus!",
    "Die Farben und Texturen in dieser Szene sind unglaublich detailliert!",
    "Diese Landschaft ist einfach atemberaubend gestaltet!",
    "Der Charakter-Look ist echt cool - tolle Details!",
    "Die Lichtstimmung in dieser Szene ist wirklich beeindruckend!",
    "Dieser Ort im Spiel ist wunderschön designt!",
    "Die Umgebung wirkt so realistisch, fast als wäre man selbst dort!",
    "Die Animationen sind super flüssig!",
    "Das Interface ist wirklich übersichtlich gestaltet!",
    "Die Atmosphäre hier ist fantastisch eingefangen!"
]

CODE_KOMMENTARE = [
    "Wow, das ist ein eleganter Code!",
    "Diese Funktion sieht effizienter aus als mein Algorithmus!",
    "Ich sehe da einen möglichen Bug in Zeile 42! Nur Spaß!",
    "Schicker Code! Hast du an Fehlerbehandlung gedacht?",
    "Clean Code at its finest!",
    "Die Variablennamen sind sehr aussagekräftig!",
    "Mit mehr Kommentaren wäre der Code noch besser lesbar!",
    "Dieser Code ist so gut strukturiert, da wird selbst Linus neidisch!",
    "Programmieren ist wie Zauberei, und du bist definitiv ein Meister!",
    "Ich sehe da einige clevere Optimierungen!"
]

WEB_KOMMENTARE = [
    "Diese Website hat ein tolles Design!",
    "Das Interface sieht sehr benutzerfreundlich aus!",
    "Die Farbkombination dieser Seite ist echt ansprechend!",
    "Interessanter Content auf dieser Webseite!",
    "Diese Seite lädt schneller als ich rechnen kann!",
    "Schickes Web-Design - responsive und modern!",
    "Die Navigation ist wirklich gut durchdacht!",
    "Das nenne ich mal eine übersichtliche Webseite!",
    "Die Schriftart passt perfekt zum Stil der Seite!",
    "Diese Website sieht auf jedem Gerät gut aus!"
]

TERMINAL_KOMMENTARE = [
    "Ah, der gute alte Terminal - wo echte Techies sich zu Hause fühlen!",
    "Wer braucht schon GUIs, wenn man Kommandozeilen hat?",
    "Grüne Schrift auf schwarzem Hintergrund - klassisch und zeitlos!",
    "Mit diesen Befehlen bist du schneller als jede Maus!",
    "Ich fühle mich wie in 'Matrix', wenn ich dir beim Tippen zusehe!",
    "Bash, Zsh oder Fish? Egal, Hauptsache Terminal-Power!",
    "Das ist echtes Computing - direkt auf Maschinenebene!",
    "Ein echter Hacker braucht nur eine Kommandozeile und einen Kaffee!",
    "Elegant, effizient und ohne Schnickschnack - so muss IT sein!",
    "Das Terminal lügt nie - im Gegensatz zu manchen UIs!"
]

DOKUMENT_KOMMENTARE = [
    "Dieses Dokument ist sehr gut strukturiert!",
    "Die Formatierung macht das Lesen angenehm!",
    "Interessante Informationen in diesem Text!",
    "Diese Präsentation hat wirklich Stil!",
    "Die Grafiken im Dokument sind sehr aussagekräftig!",
    "Elegant formatiert und leicht zu lesen - top!",
    "Die Gliederung dieses Dokuments ist vorbildlich!",
    "Inhaltlich tiefgründig und optisch ansprechend!",
    "Diese Tabelle fasst die Daten perfekt zusammen!",
    "Ein Dokument, das Klarheit schafft - sehr gut!"
]

BEGRÜSSUNGEN = [
    "Willkommen im Stream, {user}! Schön, dass du da bist!",
    "Hey {user}! Willkommen! Was hältst du bisher vom Stream?",
    "Hallo {user}! Danke, dass du vorbeischaust!",
    "Willkommen an Bord, {user}! Mach es dir gemütlich.",
    "Hi {user}! Schön, dich im Chat zu sehen!",
    "Grüß dich, {user}! Genieße den Stream!",
    "Hallo {user}! Perfektes Timing, du bist genau zum besten Teil gekommen!",
    "Willkommen, {user}! Der Chat ist mit dir noch besser!",
    "Da ist ja {user}! Schön, dass du den Weg zu uns gefunden hast!",
    "Hey {user}! Tolles Timing, wir haben gerade erst angefangen!"
]

COMMAND_REMINDERS = [
    "📋 Verfügbare Befehle: !witz, !info, !stats, !hilfe, !bild, !spiel NAME, !ort NAME, !tod, !level X, !frag zephyr ...",
    "👋 Neu hier? Mit !witz bekommst du einen zufälligen Witz von mir!",
    "🎮 Verwende !info für aktuelle Spielinfos oder !stats für Statistiken.",
    "❓ Du hast eine Frage? Benutze !frag zephyr gefolgt von deiner Frage!",
    "🖼️ Mit !bild oder !scene kommentiere ich das aktuelle Bild im Stream.",
    "🤔 Brauchst du Hilfe? Tippe !hilfe für eine Liste aller Befehle!"
]

# === Status-Variablen ===
running = True
twitch_connected = False
youtube_connected = False
youtube_active = False
twitch_sock = None
known_viewers = set()
game_state = {}
last_ping_time = 0
last_scene_comment_time = 0
reconnect_lock = threading.Lock()

# === Logging-Funktionen ===
def log(message, level=1, platform="MULTI"):
    """Loggt eine Nachricht in die Konsole und die Log-Datei"""
    if level > DEBUG_LEVEL:
        return
        
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"[{platform}] [{timestamp}] {message}"
    print(formatted_message)
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{formatted_message}\n")
    except Exception as e:
        print(f"[{platform}] [{timestamp}] Fehler beim Loggen: {e}")

def log_error(message, exception=None, platform="MULTI"):
    """Loggt eine Fehlermeldung mit optionalem Exception-Traceback"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"[{platform}] [{timestamp}] ERROR: {message}"
    print(formatted_message)
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{formatted_message}\n")
            if exception:
                f.write(f"[{platform}] [{timestamp}] Exception: {str(exception)}\n")
                if DEBUG_LEVEL >= 2:
                    f.write(f"[{platform}] [{timestamp}] {traceback.format_exc()}\n")
    except Exception as e:
        print(f"[{platform}] [{timestamp}] Fehler beim Loggen: {e}")

# === PID-Datei-Funktionen ===
def create_pid_file():
    """Erstellt eine PID-Datei für den laufenden Prozess"""
    try:
        pid = os.getpid()
        with open(PID_FILE, 'w') as f:
            f.write(str(pid))
        log(f"PID-Datei erstellt: {pid}")
    except Exception as e:
        log_error("Fehler beim Erstellen der PID-Datei", e)

def remove_pid_file():
    """Entfernt die PID-Datei beim Beenden des Prozesses"""
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
            log("PID-Datei entfernt")
    except Exception as e:
        log_error("Fehler beim Entfernen der PID-Datei", e)

# === Spielstand-Funktionen ===
def load_game_state():
    """Lädt den aktuellen Spielstand aus der JSON-Datei"""
    global game_state
    try:
        if os.path.exists(GAME_STATE_FILE):
            with open(GAME_STATE_FILE, 'r', encoding="utf-8") as f:
                game_state = json.load(f)
                log(f"Spielstand geladen: {game_state}", level=2)
        else:
            game_state = {
                "spiel": "Oblivion Remastered",
                "ort": "Kvatch",
                "tode": 0,
                "level": 1,
                "spielzeit": "00:00:00"
            }
            save_game_state()
    except Exception as e:
        log_error("Fehler beim Laden des Spielstands", e)
        game_state = {
            "spiel": "Oblivion Remastered",
            "ort": "Kvatch",
            "tode": 0,
            "level": 1,
            "spielzeit": "00:00:00"
        }

def save_game_state():
    """Speichert den aktuellen Spielstand in der JSON-Datei"""
    try:
        with open(GAME_STATE_FILE, 'w', encoding="utf-8") as f:
            json.dump(game_state, f, indent=2)
            log("Spielstand gespeichert", level=2)
    except Exception as e:
        log_error("Fehler beim Speichern des Spielstands", e)

# === Bildverarbeitungsfunktionen ===
def get_latest_screenshot():
    """Findet den neuesten Screenshot im Screenshots-Verzeichnis"""
    if not os.path.exists(SCREENSHOTS_DIR):
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        log(f"Screenshots-Verzeichnis erstellt: {SCREENSHOTS_DIR}")
        return None
    
    screenshots = sorted([
        os.path.join(SCREENSHOTS_DIR, f)
        for f in os.listdir(SCREENSHOTS_DIR)
        if f.lower().endswith(('.png', '.jpg', '.jpeg'))
    ], key=os.path.getmtime, reverse=True)
    
    if not screenshots:
        log("Keine Screenshots gefunden")
        return None
        
    log(f"Neuester Screenshot gefunden: {screenshots[0]}", level=2)
    return screenshots[0]

def analyze_image_with_llava(image_path):
    """Analysiert ein Bild mit LLaVA und gibt die Beschreibung zurück"""
    if not os.path.exists(image_path):
        log_error(f"Bild existiert nicht: {image_path}")
        return None
        
    try:
        log(f"Analysiere Bild mit LLaVA: {image_path}", level=1)
        
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        
        payload = {
            "model": VISION_MODEL,
            "prompt": "Beschreibe möglichst genau, was auf dem Bild zu sehen ist.",
            "images": [img_b64],
            "stream": False
        }
        
        if OLLAMA_API_VERSION == "v1":
            try:
                messages = [
                    {"role": "system", "content": "Du beschreibst Bilder detailliert und präzise."},
                    {"role": "user", "content": [
                        {"type": "text", "text": "Beschreibe möglichst genau, was auf dem Bild zu sehen ist."},
                        {"type": "image", "image": img_b64}
                    ]}
                ]
                
                v1_payload = {
                    "model": VISION_MODEL,
                    "messages": messages,
                    "stream": False
                }
                
                response = requests.post(
                    OLLAMA_ENDPOINTS["v1"]["chat"],
                    json=v1_payload,
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    description = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    log(f"LLaVA v1 API-Beschreibung erhalten ({len(description)} Zeichen)", level=1)
                    
                    with open(VISION_CACHE_FILE, "w", encoding="utf-8") as f:
                        f.write(description)
                    log(f"Beschreibung in {VISION_CACHE_FILE} gespeichert", level=2)
                    
                    return description
            except Exception as e:
                log_error(f"Fehler bei LLaVA v1 API-Anfrage: {e}", e)
        
        response = requests.post(
            "http://localhost:11434/api/generate", 
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            description = response.json().get("response", "").strip()
            log(f"LLaVA Legacy-API-Beschreibung erhalten ({len(description)} Zeichen)", level=1)
            
            try:
                with open(VISION_CACHE_FILE, "w", encoding="utf-8") as f:
                    f.write(description)
                log(f"Beschreibung in {VISION_CACHE_FILE} gespeichert", level=2)
            except Exception as e:
                log_error(f"Fehler beim Speichern der Beschreibung: {e}", e)
                
            return description
        else:
            log_error(f"Fehler bei LLaVA-API: {response.status_code}")
            return None
            
    except Exception as e:
        log_error(f"Fehler bei Bildanalyse: {e}", e)
        return None

def identify_content_type(description):
    """Identifiziert den Typ des Inhalts basierend auf der Beschreibung"""
    if not description:
        return "allgemein"
        
    description_lower = description.lower()
    
    code_keywords = ["code", "programming", "programmier", "entwicklungsumgebung", "editor", 
                    "code editor", "entwickler", "python", "javascript", "java", "c++", "html", 
                    "css", "ide", "visual studio", "intellij", "github", "git", "repository"]
    
    browser_keywords = ["browser", "website", "webpage", "web page", "web-site", "webseite", 
                       "firefox", "chrome", "edge", "safari", "internet explorer", "url", 
                       "http", "https", "web browser", "online", "internet"]
    
    game_keywords = ["game", "gaming", "playing", "spiel", "videospiel", "spielen", "videogame", 
                     "game character", "player", "level", "quest", "npc", "character", "console", 
                     "playstation", "xbox", "nintendo", "mission", "achievement"]
    
    terminal_keywords = ["terminal", "console", "konsole", "command line", "kommandozeile", "shell", 
                        "bash", "ubuntu", "linux", "powershell", "cmd", "command prompt", "ssh", 
                        "unix", "cli", "befehlszeile", "terminal emulator"]
    
    document_keywords = ["document", "dokument", "text", "word", "textdatei", "spreadsheet", 
                        "tabelle", "präsentation", "excel", "powerpoint", "pdf", "doc", "docx", 
                        "brief", "artikel", "bericht", "report", "paper", "formular"]
    
    code_count = sum(1 for keyword in code_keywords if keyword in description_lower)
    browser_count = sum(1 for keyword in browser_keywords if keyword in description_lower)
    game_count = sum(1 for keyword in game_keywords if keyword in description_lower)
    terminal_count = sum(1 for keyword in terminal_keywords if keyword in description_lower)
    document_count = sum(1 for keyword in document_keywords if keyword in description_lower)
    
    counts = {
        "code": code_count,
        "browser": browser_count,
        "game": game_count,
        "terminal": terminal_count,
        "document": document_count
    }
    
    max_category = max(counts.items(), key=lambda x: x[1])
    
    if max_category[1] > 0:
        return max_category[0]
    
    return "allgemein"

def generate_content_comment(content_type, description):
    """Generiert einen Kommentar basierend auf dem Content-Typ und der Beschreibung"""
    
    prompts = {
        "code": f"""Ein KI-Vision-Modell hat auf einem Screenshot Code oder eine Programmierumgebung erkannt:
\"{description}\"

Formuliere als Twitch-Bot {BOT_NAME} eine witzige, knackige Antwort über diesen Code oder diese Programmierumgebung.
Mach einen coolen, lockeren Spruch, der für Programmierer witzig ist. Maximal 2 Sätze. Deutsch.""",

        "browser": f"""Ein KI-Vision-Modell hat auf einem Screenshot einen Browser oder eine Website erkannt:
\"{description}\"

Formuliere als Twitch-Bot {BOT_NAME} eine witzige, knackige Antwort über diesen Webinhalt.
Mach einen coolen, lockeren Spruch über das, was im Browser zu sehen ist. Maximal 2 Sätze. Deutsch.""",

        "game": f"""Ein KI-Vision-Modell hat auf einem Screenshot ein Videospiel erkannt:
\"{description}\"

Formuliere als Twitch-Bot {BOT_NAME} eine witzige, knackige Twitch-Antwort zum aktuellen Spielgeschehen.
Sprich wie ein Gamer und sei unterhaltsam. Maximal 2 Sätze. Deutsch.""",

        "terminal": f"""Ein KI-Vision-Modell hat auf einem Screenshot ein Terminal oder eine Konsole erkannt:
\"{description}\"

Formuliere als Twitch-Bot {BOT_NAME} eine witzige, knackige Antwort über diese Terminal-Session.
Mach einen coolen Spruch für Linux/Shell-Enthusiasten. Maximal 2 Sätze. Deutsch.""",

        "document": f"""Ein KI-Vision-Modell hat auf einem Screenshot ein Textdokument erkannt:
\"{description}\"

Formuliere als Twitch-Bot {BOT_NAME} eine witzige, knackige Antwort über dieses Dokument.
Sei kreativ und unterhaltsam bezüglich des Textinhalts. Maximal 2 Sätze. Deutsch.""",

        "allgemein": f"""Ein KI-Vision-Modell hat Folgendes auf einem Screenshot erkannt:
\"{description}\"

Formuliere als Chat-Bot {BOT_NAME} eine knackige, witzige Twitch-Antwort zum aktuellen Inhalt.
Sei unterhaltsam und originell. Maximal 2 Sätze. Deutsch."""
    }
    
    prompt = prompts.get(content_type, prompts["allgemein"])
    comment = get_response_from_ollama(prompt)
    
    fallback_comments = {
        "code": CODE_KOMMENTARE,
        "browser": WEB_KOMMENTARE,
        "game": GAME_KOMMENTARE,
        "terminal": TERMINAL_KOMMENTARE,
        "document": DOKUMENT_KOMMENTARE,
        "allgemein": SCENE_KOMMENTARE
    }
    
    if not comment:
        comment = random.choice(fallback_comments.get(content_type, SCENE_KOMMENTARE))
        log(f"Verwende Fallback-Kommentar für {content_type}: {comment}", level=1)
    
    return comment

# === Ollama-Funktionen ===
def get_response_from_ollama(prompt, retries=OLLAMA_RETRY_COUNT):
    """Sendet eine Anfrage an den Ollama-Server und gibt die Antwort zurück"""
    log(f"Sende an Ollama: {prompt[:50]}...", level=1)
    
    for attempt in range(retries):
        try:
            if OLLAMA_API_VERSION == "v1":
                try:
                    response = requests.post(
                        OLLAMA_ENDPOINTS["v1"]["chat"],
                        json={
                            "model": MODEL,
                            "messages": [
                                {"role": "system", "content": f"Du bist ein hilfreicher Twitch-Bot namens {BOT_NAME}. Antworte immer auf Deutsch, kurz und prägnant."},
                                {"role": "user", "content": prompt}
                            ],
                            "stream": False
                        },
                        timeout=OLLAMA_TIMEOUT
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        text = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                        if text:
                            log(f"Antwort von Ollama V1 API erhalten: {text[:50]}...", level=1)
                            return text
                except Exception as e:
                    log_error(f"Fehler bei V1 API-Anfrage, versuche Legacy: {str(e)}", e)
            
            try:
                response = requests.post(
                    OLLAMA_ENDPOINTS["legacy"]["chat"],
                    json={
                        "model": MODEL,
                        "messages": [
                            {"role": "system", "content": f"Du bist ein hilfreicher Twitch-Bot namens {BOT_NAME}. Antworte immer auf Deutsch, kurz und prägnant."},
                            {"role": "user", "content": prompt}
                        ],
                        "stream": False
                    },
                    timeout=OLLAMA_TIMEOUT
                )
                
                if response.status_code == 200:
                    result = response.json()
                    text = result.get("message", {}).get("content", "").strip()
                    if text:
                        log(f"Antwort von Ollama Chat API erhalten: {text[:50]}...", level=1)
                        return text
            except Exception as e:
                log_error(f"Fehler bei Chat API-Anfrage, versuche Generate: {str(e)}", e)
                
            response = requests.post(
                OLLAMA_ENDPOINTS["legacy"]["generate"],
                json={
                    "model": MODEL,
                    "prompt": prompt,
                    "system": f"Du bist ein hilfreicher Twitch-Bot namens {BOT_NAME}. Antworte immer auf Deutsch, kurz und prägnant.",
                    "stream": False
                },
                timeout=OLLAMA_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result.get("response", "").strip()
                if text:
                    log(f"Antwort von Ollama Generate API erhalten: {text[:50]}...", level=1)
                    return text
                    
            log_error(f"Fehler bei Ollama-Anfrage (Versuch {attempt+1}/{retries}): Status {response.status_code}")
            
            if attempt < retries - 1:
                wait_time = 2 * (attempt + 1)
                log(f"Warte {wait_time}s vor nächstem Versuch...", level=2)
                time.sleep(wait_time)
                
        except Exception as e:
            log_error(f"Ausnahme bei Ollama-Anfrage (Versuch {attempt+1}/{retries})", e)
            if attempt < retries - 1:
                wait_time = 2 * (attempt + 1)
                time.sleep(wait_time)
    
    return None

def check_ollama_server():
    """Überprüft, ob der Ollama-Server erreichbar ist"""
    try:
        response = requests.get("http://localhost:11434/api/version", timeout=5)
        if response.status_code == 200:
            version_info = response.json()
            return True, version_info.get("version", "unbekannt")
            
        response = requests.get("http://localhost:11434/", timeout=5)
        if response.status_code == 200:
            return True, "unbekannt"
            
        return False, None
    except Exception as e:
        log_error(f"Ollama-Server nicht erreichbar: {e}", e)
        return False, None

# === Multi-Platform Nachrichtenfunktionen ===
def send_message_to_platforms(message, exclude_platform=None):
    """Sendet eine Nachricht an alle aktiven Plattformen"""
    sent_count = 0
    
    if ENABLE_TWITCH and twitch_connected and exclude_platform != "twitch":
        if send_twitch_message(message):
            sent_count += 1
    
    # YouTube-Senden würde hier implementiert werden, wenn die API das unterstützt
    # Aktuell unterstützt die YouTube API v3 kein Senden von Live-Chat-Nachrichten
    # Das wäre nur mit speziellen Berechtigungen und YouTube Partner-Status möglich
    
    return sent_count > 0

def send_twitch_message(message):
    """Sendet eine Nachricht an den Twitch-Chat"""
    global twitch_connected
    
    if not twitch_connected:
        log("Nicht verbunden beim Senden der Nachricht", platform="TWITCH")
        return False
    
    try:
        twitch_sock.send(f"PRIVMSG {CHANNEL} :{message}\r\n".encode('utf-8'))
        log(f"Nachricht gesendet: {message[:50]}...", platform="TWITCH")
        return True
    except Exception as e:
        log_error("Fehler beim Senden der Nachricht", e, platform="TWITCH")
        twitch_connected = False
        return False

def process_message_unified(user, message, platform):
    """Verarbeitet eine empfangene Chat-Nachricht von beliebiger Plattform"""
    platform_emoji = "💬" if platform == "twitch" else "🔴" if platform == "youtube" else "💭"
    log(f"{platform_emoji} [{platform.upper()}] {user}: {message}")
    
    # Ignoriere Bot-eigene Nachrichten
    if user.lower() == BOT_NAME.lower():
        log(f"Eigene Nachricht ignoriert: {message}", platform=platform.upper())
        return
    
    # Prüfen, ob es ein neuer Zuschauer ist
    viewer_key = f"{user}_{platform}"
    if viewer_key not in known_viewers and not user.lower().endswith('bot'):
        known_viewers.add(viewer_key)
        threading.Thread(target=lambda: greeting_worker(user, platform)).start()
    
    # Befehle verarbeiten
    if message.lower() == "!witz":
        threading.Thread(target=lambda: joke_worker(platform)).start()
    
    elif message.lower() == "!info":
        send_info(platform)
    
    elif message.lower() == "!stats":
        send_stats(platform)
    
    elif message.lower() == "!hilfe" or message.lower() == "!help":
        send_help(platform)
    
    elif message.lower() == "!bild" or message.lower() == "!scene":
        threading.Thread(target=lambda: scene_comment_worker(platform)).start()
    
    elif message.lower().startswith("!spiel "):
        game_name = message[7:].strip()
        if game_name:
            update_game(game_name, user, platform)
    
    elif message.lower().startswith("!ort "):
        location = message[5:].strip()
        if location:
            update_location(location, user, platform)
    
    elif message.lower() == "!tod":
        increment_deaths(user, platform)
    
    elif message.lower().startswith("!level "):
        try:
            new_level = int(message[7:].strip())
            update_level(new_level, user, platform)
        except ValueError:
            send_platform_message(f"@{user} Bitte gib eine gültige Levelnummer an!", platform)
    
    elif message.lower().startswith("!frag ") and BOT_NAME.lower() in message.lower():
        question = message.lower().split(BOT_NAME.lower(), 1)[1].strip()
        if question:
            threading.Thread(target=lambda: respond_to_direct_question(user, question, platform)).start()
    
    elif BOT_NAME.lower() in message.lower():
        if "?" in message:
            threading.Thread(target=lambda: respond_to_question(user, message, platform)).start()

def send_platform_message(message, platform):
    """Sendet eine Nachricht an eine spezifische Plattform"""
    if platform == "twitch":
        return send_twitch_message(message)
    elif platform == "youtube":
        # YouTube Chat API unterstützt kein Senden für normale Bots
        log(f"YouTube-Nachricht (nur Log): {message}", platform="YOUTUBE")
        return True
    return False

# === Twitch IRC-Funktionen ===
def connect_to_twitch():
    """Stellt eine Verbindung zum Twitch IRC-Server her"""
    global twitch_sock, twitch_connected
    
    if not ENABLE_TWITCH:
        return False
    
    with reconnect_lock:
        if twitch_sock:
            try:
                twitch_sock.close()
            except:
                pass
        
        twitch_sock = socket.socket()
        twitch_sock.settimeout(SOCKET_TIMEOUT)
        
        try:
            log(f"Verbinde mit {SERVER}:{PORT}...", platform="TWITCH")
            twitch_sock.connect((SERVER, PORT))
            
            twitch_sock.send(f"PASS {TOKEN}\r\n".encode('utf-8'))
            twitch_sock.send(f"NICK {NICKNAME}\r\n".encode('utf-8'))
            
            response = ""
            start_time = time.time()
            while time.time() - start_time < 10:
                try:
                    data = twitch_sock.recv(2048).decode('utf-8')
                    if not data:
                        continue
                    
                    response += data
                    log(f"Empfangen: {data.strip()}", level=2, platform="TWITCH")
                    
                    if "Welcome, GLHF!" in response or ":tmi.twitch.tv 001" in response:
                        log("Erfolgreich authentifiziert!", platform="TWITCH")
                        
                        twitch_sock.send("CAP REQ :twitch.tv/membership\r\n".encode('utf-8'))
                        twitch_sock.send("CAP REQ :twitch.tv/tags\r\n".encode('utf-8'))
                        twitch_sock.send("CAP REQ :twitch.tv/commands\r\n".encode('utf-8'))
                        
                        twitch_sock.send(f"JOIN {CHANNEL}\r\n".encode('utf-8'))
                        log(f"Kanal {CHANNEL} beigetreten", platform="TWITCH")
                        
                        time.sleep(1)
                        data = twitch_sock.recv(2048).decode('utf-8')
                        log(f"Join-Antwort: {data.strip()}", level=2, platform="TWITCH")
                        
                        send_twitch_message(f"👋 [Twitch] Hallo! Ich bin {BOT_NAME} und bereit, euch zu unterhalten! Befehle: !witz, !info, !stats, !hilfe")
                        
                        twitch_connected = True
                        return True
                except socket.timeout:
                    continue
                except Exception as recv_err:
                    log_error("Fehler beim Empfangen von Daten", recv_err, platform="TWITCH")
                    break
            
            log_error("Timeout bei der Authentifizierung", None, platform="TWITCH")
            return False
        except Exception as e:
            log_error("Verbindungsfehler", e, platform="TWITCH")
            return False

def send_twitch_ping():
    """Sendet einen PING an den Twitch-Server"""
    global twitch_connected
    
    if not twitch_connected:
        return False
    
    try:
        twitch_sock.send("PING :tmi.twitch.tv\r\n".encode('utf-8'))
        log("PING gesendet", level=2, platform="TWITCH")
        return True
    except Exception as e:
        log_error("Fehler beim Senden des PINGs", e, platform="TWITCH")
        twitch_connected = False
        return False

def extract_username(message_line):
    """Extrahiert den Benutzernamen aus einer IRC-Nachricht"""
    username = ""
    
    if "display-name=" in message_line:
        try:
            match = re.search(r'display-name=([^;]+)', message_line)
            if match:
                username = match.group(1)
        except:
            pass
    
    if not username:
        try:
            match = re.search(r':([^!]+)!', message_line)
            if match:
                username = match.group(1)
            else:
                username = "unknown_user"
        except:
            username = "unknown_user"
    
    return username

# === Kommando-Funktionen ===
def joke_worker(platform="all"):
    """Erzeugt einen Witz und sendet ihn an den Chat"""
    prompt = f"Erzähle einen kurzen, lustigen Witz. Mach ihn besonders humorvoll."
    joke = get_response_from_ollama(prompt)
    if joke:
        message = f"🎭 {joke[:450]}"
        if platform == "all":
            send_message_to_platforms(message)
        else:
            send_platform_message(message, platform)
        log(f"Witz gesendet: {joke[:50]}...")
    else:
        fallback_joke = random.choice(WITZE)
        message = f"🎭 {fallback_joke}"
        if platform == "all":
            send_message_to_platforms(message)
        else:
            send_platform_message(message, platform)
        log(f"Fallback-Witz gesendet: {fallback_joke[:50]}...")

def scene_comment_worker(platform="all"):
    """Hauptfunktion für den !bild Befehl"""
    log("Scene Comment Worker gestartet", level=1)
    
    screenshot_path = get_latest_screenshot()
    if not screenshot_path:
        log("Kein Screenshot gefunden", level=1)
        message = f"👁️ Ich kann leider keinen Screenshot finden, um ihn zu kommentieren."
        if platform == "all":
            send_message_to_platforms(message)
        else:
            send_platform_message(message, platform)
        return
    
    log(f"Analysiere Screenshot: {screenshot_path}", level=1)
    description = analyze_image_with_llava(screenshot_path)
    
    if not description and os.path.exists(VISION_CACHE_FILE):
        try:
            with open(VISION_CACHE_FILE, "r", encoding="utf-8") as f:
                description = f.read().strip()
                log(f"Beschreibung aus Cache geladen ({len(description)} Zeichen)", level=1)
        except Exception as e:
            log_error(f"Fehler beim Lesen der Cache-Datei: {e}", e)
    
    if description:
        content_type = identify_content_type(description)
        log(f"Erkannter Inhaltstyp: {content_type}", level=1)
        
        comment = generate_content_comment(content_type, description)
        
        if comment:
            message = f"👁️ {comment[:450]}"
            if platform == "all":
                send_message_to_platforms(message)
            else:
                send_platform_message(message, platform)
            log(f"Bildkommentar gesendet: {comment[:50]}...", level=1)
            return
    
    fallback_comment = random.choice(SCENE_KOMMENTARE)
    message = f"👁️ {fallback_comment}"
    if platform == "all":
        send_message_to_platforms(message)
    else:
        send_platform_message(message, platform)
    log(f"Fallback-Bildkommentar gesendet: {fallback_comment[:50]}...")

def send_info(platform="all"):
    """Sendet Informationen zum aktuellen Spiel und Ort"""
    load_game_state()
    game = game_state.get("spiel", "Unbekannt")
    location = game_state.get("ort", "Unbekannt")
    message = f"🎮 Aktuelles Spiel: {game} | 📍 Ort: {location} | ⏱️ Spielzeit: {game_state.get('spielzeit', '00:00:00')}"
    if platform == "all":
        send_message_to_platforms(message)
    else:
        send_platform_message(message, platform)

def send_stats(platform="all"):
    """Sendet Statistiken zum aktuellen Spielstand"""
    load_game_state()
    deaths = game_state.get("tode", 0)
    level = game_state.get("level", 1)
    message = f"📊 Statistiken: 💀 Tode: {deaths} | 📈 Level: {level} | 🕹️ Spiel: {game_state.get('spiel', 'Unbekannt')}"
    if platform == "all":
        send_message_to_platforms(message)
    else:
        send_platform_message(message, platform)

def send_help(platform="all"):
    """Sendet eine Hilfe-Nachricht mit verfügbaren Befehlen"""
    help_message = "📋 Befehle: !witz (zufälliger Witz), !info (Spielinfo), !stats (Statistiken), " + \
                  "!bild/!scene (Kommentar zur aktuellen Szene), !spiel NAME (Spiel ändern), " + \
                  "!ort NAME (Ort ändern), !tod (Tod zählen), !level X (Level setzen), !frag " + BOT_NAME + " ... (direkte Frage an mich)"
    if platform == "all":
        send_message_to_platforms(help_message)
    else:
        send_platform_message(help_message, platform)

def update_game(game_name, user, platform):
    """Aktualisiert den Spielnamen im Spielstand"""
    load_game_state()
    old_game = game_state.get("spiel", "Unbekannt")
    game_state["spiel"] = game_name
    save_game_state()
    platform_emoji = "💬" if platform == "twitch" else "🔴" if platform == "youtube" else "💭"
    message = f"🎮 {platform_emoji} @{user} hat das Spiel von '{old_game}' zu '{game_name}' geändert!"
    send_message_to_platforms(message)

def update_location(location, user, platform):
    """Aktualisiert den aktuellen Ort im Spielstand"""
    load_game_state()
    old_location = game_state.get("ort", "Unbekannt")
    game_state["ort"] = location
    save_game_state()
    platform_emoji = "💬" if platform == "twitch" else "🔴" if platform == "youtube" else "💭"
    message = f"📍 {platform_emoji} @{user} hat den Ort von '{old_location}' zu '{location}' geändert!"
    send_message_to_platforms(message)

def increment_deaths(user, platform):
    """Erhöht den Todeszähler"""
    load_game_state()
    game_state["tode"] = game_state.get("tode", 0) + 1
    deaths = game_state["tode"]
    save_game_state()
    platform_emoji = "💬" if platform == "twitch" else "🔴" if platform == "youtube" else "💭"
    message = f"💀 {platform_emoji} R.I.P! Todeszähler steht jetzt bei {deaths}. " + random.choice([
        "Das war knapp!",
        "Kopf hoch, nächstes Mal klappt's besser!",
        "Halb so wild, du schaffst das!",
        "Aus Fehlern lernt man!",
        "Die Gegner werden auch immer gemeiner..."
    ])
    send_message_to_platforms(message)

def update_level(level, user, platform):
    """Aktualisiert das aktuelle Level im Spielstand"""
    load_game_state()
    old_level = game_state.get("level", 1)
    game_state["level"] = level
    save_game_state()
    
    platform_emoji = "💬" if platform == "twitch" else "🔴" if platform == "youtube" else "💭"
    if level > old_level:
        message = f"📈 {platform_emoji} Level Up! @{user} hat das Level von {old_level} auf {level} erhöht! Weiter so!"
    else:
        message = f"📊 {platform_emoji} @{user} hat das Level auf {level} gesetzt."
    send_message_to_platforms(message)

def greeting_worker(user, platform):
    """Begrüßt einen neuen Zuschauer"""
    platform_emoji = "💬" if platform == "twitch" else "🔴" if platform == "youtube" else "💭"
    greeting = random.choice(BEGRÜSSUNGEN).format(user=user)
    message = f"{platform_emoji} {greeting}"
    send_platform_message(message, platform)
    log(f"Neuer Zuschauer begrüßt: {user} auf {platform}")

def respond_to_question(user, message, platform):
    """Antwortet auf eine Frage, die den Bot-Namen enthält"""
    prompt = f"Du bist ein Twitch-Bot namens {BOT_NAME}. Der Benutzer {user} hat dich folgendes gefragt: '{message}'. Gib eine kurze, hilfreiche Antwort (max. 200 Zeichen)."
    
    response = get_response_from_ollama(prompt)
    platform_emoji = "💬" if platform == "twitch" else "🔴" if platform == "youtube" else "💭"
    if response:
        reply = f"{platform_emoji} @{user} {response[:450]}"
        send_platform_message(reply, platform)
        log(f"Antwort auf Frage gesendet: {response[:50]}...")
    else:
        reply = f"{platform_emoji} @{user} Hmm, ich bin mir nicht sicher, was ich dazu sagen soll. Versuch's mal mit !witz für einen lustigen Witz!"
        send_platform_message(reply, platform)

def respond_to_direct_question(user, question, platform):
    """Antwortet auf eine direkte Frage mit dem !frag Befehl"""
    prompt = f"Du bist ein Twitch-Bot namens {BOT_NAME}. Beantworte folgende Frage von {user} direkt und präzise (max. 250 Zeichen): '{question}'."
    
    response = get_response_from_ollama(prompt)
    platform_emoji = "💬" if platform == "twitch" else "🔴" if platform == "youtube" else "💭"
    if response:
        reply = f"{platform_emoji} @{user} {response[:450]}"
        send_platform_message(reply, platform)
        log(f"Antwort auf direkte Frage gesendet: {response[:50]}...")
    else:
        reply = f"{platform_emoji} @{user} Entschuldige, ich konnte keine Antwort generieren. Versuche es später noch einmal."
        send_platform_message(reply, platform)

# === Thread-Funktionen ===
def auto_joke_worker():
    """Thread für automatische Witze in regelmäßigen Abständen"""
    log(f"Automatischer Witz-Thread gestartet - Intervall: {AUTO_JOKE_INTERVAL} Sekunden")
    time.sleep(10)
    
    while running:
        if twitch_connected or youtube_active:
            joke_worker("all")
        else:
            log("Überspringe automatischen Witz: Keine Plattform verbunden")
        
        for _ in range(AUTO_JOKE_INTERVAL):
            if not running:
                break
            time.sleep(1)

def auto_comment_worker():
    """Thread für automatische Spielkommentare in regelmäßigen Abständen"""
    log(f"Automatischer Kommentar-Thread gestartet - Intervall: {AUTO_COMMENT_INTERVAL} Sekunden")
    time.sleep(30)
    
    while running:
        if twitch_connected or youtube_active:
            load_game_state()
            game = game_state.get("spiel", "Unbekannt")
            location = game_state.get("ort", "Unbekannt")
            
            if game != "Unbekannt":
                prompt = f"Du bist ein Twitch-Bot namens {BOT_NAME}. Der Streamer spielt gerade {game} und befindet sich in/bei {location}. Gib einen kurzen, lustigen und hilfreichen Spielkommentar ab (max. 200 Zeichen)."
                comment = get_response_from_ollama(prompt)
                
                if comment:
                    send_message_to_platforms(f"🎮 {comment[:450]}")
                    log(f"Spiel-Kommentar gesendet: {comment[:50]}...")
                else:
                    fallback_comment = random.choice(GAME_KOMMENTARE)
                    send_message_to_platforms(f"🎮 {fallback_comment}")
                    log(f"Fallback-Spielkommentar gesendet: {fallback_comment[:50]}...")
        else:
            log("Überspringe automatischen Kommentar: Keine Plattform verbunden")
        
        for _ in range(AUTO_COMMENT_INTERVAL):
            if not running:
                break
            time.sleep(1)

def auto_scene_comment_worker():
    """Thread für automatische Bildkommentare in regelmäßigen Abständen"""
    global last_scene_comment_time
    
    log(f"Automatischer Bildkommentar-Thread gestartet - Intervall: {AUTO_SCENE_COMMENT_INTERVAL} Sekunden")
    time.sleep(60)
    
    while running:
        current_time = time.time()
        
        if (twitch_connected or youtube_active) and current_time - last_scene_comment_time >= AUTO_SCENE_COMMENT_INTERVAL:
            scene_comment_worker("all")
            last_scene_comment_time = current_time
        else:
            remaining = AUTO_SCENE_COMMENT_INTERVAL - (current_time - last_scene_comment_time)
            log(f"Überspringe automatischen Bildkommentar: Nächster in {int(max(0, remaining))} Sekunden", level=2)
        
        time.sleep(30)

def command_reminder_worker():
    """Thread für Befehlserinnerungen in regelmäßigen Abständen"""
    log(f"Befehlserinnerungs-Thread gestartet - Intervall: {COMMAND_REMINDER_INTERVAL} Sekunden")
    time.sleep(120)
    
    reminder_index = 0
    while running:
        if twitch_connected or youtube_active:
            reminder = COMMAND_REMINDERS[reminder_index]
            send_message_to_platforms(reminder)
            log(f"Befehlserinnerung gesendet: {reminder}")
            
            reminder_index = (reminder_index + 1) % len(COMMAND_REMINDERS)
        else:
            log("Überspringe Befehlserinnerung: Keine Plattform verbunden")
        
        for _ in range(COMMAND_REMINDER_INTERVAL):
            if not running:
                break
            time.sleep(1)

def twitch_connection_watchdog():
    """Überwacht die Twitch-Verbindung und versucht bei Verbindungsabbrüchen eine Wiederverbindung"""
    global twitch_connected, last_ping_time
    
    if not ENABLE_TWITCH:
        return
    
    log("Twitch-Verbindungs-Watchdog gestartet", platform="TWITCH")
    retry_count = 0
    max_retries = 10
    
    while running:
        current_time = time.time()
        
        if not twitch_connected:
            retry_count += 1
            
            if retry_count > max_retries:
                log_error(f"Maximale Anzahl an Wiederverbindungsversuchen ({max_retries}) erreicht", None, platform="TWITCH")
                log("Twitch-Verbindung aufgegeben", platform="TWITCH")
                break
            
            log(f"Nicht verbunden - Versuche Wiederverbindung ({retry_count}/{max_retries})...", platform="TWITCH")
            if connect_to_twitch():
                retry_count = 0
                last_ping_time = current_time
        else:
            if current_time - last_ping_time > PING_INTERVAL:
                if send_twitch_ping():
                    last_ping_time = current_time
        
        time.sleep(5)

def twitch_message_receiver():
    """Empfängt und verarbeitet eingehende Twitch IRC-Nachrichten"""
    global twitch_connected, last_ping_time
    
    if not ENABLE_TWITCH:
        return
    
    log("Twitch-Nachrichtenempfänger gestartet", platform="TWITCH")
    
    while running:
        if not twitch_connected:
            time.sleep(1)
            continue
        
        try:
            response = ""
            twitch_sock.settimeout(0.5)
            
            try:
                response = twitch_sock.recv(2048).decode('utf-8')
                last_ping_time = time.time()
            except socket.timeout:
                continue
            except Exception as e:
                log_error("Fehler beim Empfangen", e, platform="TWITCH")
                twitch_connected = False
                continue
            
            if not response:
                continue
            
            for line in response.split('\r\n'):
                if not line:
                    continue
                
                log(f"Empfangen: {line}", level=2, platform="TWITCH")
                
                if line.startswith("PING"):
                    reply = line.replace("PING", "PONG")
                    twitch_sock.send(f"{reply}\r\n".encode('utf-8'))
                    log(f"PING beantwortet mit: {reply}", level=2, platform="TWITCH")
                    continue
                
                if "PRIVMSG" in line:
                    username = extract_username(line)
                    
                    try:
                        message_content = line.split("PRIVMSG", 1)[1].split(":", 1)[1]
                        threading.Thread(target=lambda: process_message_unified(username, message_content, "twitch")).start()
                    except Exception as msg_err:
                        log_error(f"Fehler beim Parsen der Nachricht: {line}", msg_err, platform="TWITCH")
        except Exception as e:
            log_error("Unerwarteter Fehler im Nachrichtenempfänger", e, platform="TWITCH")
            time.sleep(1)

def youtube_message_handler(user, message, platform):
    """Handler-Funktion für YouTube-Nachrichten"""
    process_message_unified(user, message, platform)

def youtube_status_monitor():
    """Überwacht den YouTube Chat Reader Status"""
    global youtube_active
    
    if not ENABLE_YOUTUBE or not YOUTUBE_AVAILABLE:
        return
        
    log("YouTube Status Monitor gestartet", platform="YOUTUBE")
    
    while running:
        try:
            status = get_youtube_status()
            new_active = status.get('active', False)
            
            if new_active != youtube_active:
                youtube_active = new_active
                if youtube_active:
                    log("YouTube Chat erfolgreich aktiviert", platform="YOUTUBE")
                else:
                    log("YouTube Chat nicht aktiv - versuche Neuinitialisierung", platform="YOUTUBE")
                    # Versuche Neuinitialisierung
                    try:
                        from youtube_chat_reader import initialize_youtube_chat
                        if initialize_youtube_chat():
                            log("YouTube Chat Neuinitialisierung erfolgreich", platform="YOUTUBE")
                        else:
                            log("YouTube Chat Neuinitialisierung fehlgeschlagen", platform="YOUTUBE")
                    except Exception as e:
                        log_error("Fehler bei YouTube Neuinitialisierung", e, platform="YOUTUBE")
        except Exception as e:
            log_error("Fehler im YouTube Status Monitor", e, platform="YOUTUBE")
        
        time.sleep(10)  # Alle 10 Sekunden prüfen

# === Hauptprogramm ===
def main():
    global running, last_scene_comment_time, youtube_connected, youtube_active
    
    try:
        create_pid_file()
        
        log(f"{BOT_NAME} Multi-Platform-Bot wird gestartet...")
        log(f"Plattformen: Twitch={ENABLE_TWITCH}, YouTube={ENABLE_YOUTUBE}")
        
        current_time = time.time()
        last_scene_comment_time = current_time
        
        if not os.path.exists(SCREENSHOTS_DIR):
            os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
            log(f"Screenshots-Verzeichnis erstellt: {SCREENSHOTS_DIR}")
        
        load_game_state()
        
        server_running, version = check_ollama_server()
        if server_running:
            log(f"Ollama-Server ist erreichbar, Version: {version}")
        else:
            log_error("Ollama-Server ist nicht erreichbar! Der Bot wird möglicherweise nicht korrekt funktionieren.")
            log("Versuche trotzdem fortzufahren...")
        
        # Teste YouTube-Verbindung wenn aktiviert
        if ENABLE_YOUTUBE and YOUTUBE_AVAILABLE:
            if test_youtube_connection():
                log("YouTube-Verbindung erfolgreich getestet", platform="YOUTUBE")
            else:
                log_error("YouTube-Verbindungstest fehlgeschlagen", platform="YOUTUBE")
        
        # Initialisiere Twitch-Verbindung
        if ENABLE_TWITCH:
            if not connect_to_twitch():
                log_error("Initiale Twitch-Verbindung fehlgeschlagen, versuche Wiederverbindung", None, platform="TWITCH")
        
        # Starte Threads
        threads = []
        
        # Twitch-Threads
        if ENABLE_TWITCH:
            twitch_receiver_thread = threading.Thread(target=twitch_message_receiver)
            twitch_receiver_thread.daemon = True
            twitch_receiver_thread.start()
            threads.append(twitch_receiver_thread)
            
            twitch_watchdog_thread = threading.Thread(target=twitch_connection_watchdog)
            twitch_watchdog_thread.daemon = True
            twitch_watchdog_thread.start()
            threads.append(twitch_watchdog_thread)
        
        # YouTube-Thread
        if ENABLE_YOUTUBE and YOUTUBE_AVAILABLE:
            youtube_thread = start_youtube_chat_reader(youtube_message_handler)
            threads.append(youtube_thread)
            youtube_connected = True
            log("YouTube Chat Reader gestartet", platform="YOUTUBE")
            
            # Warte kurz und prüfe dann den Status
            time.sleep(3)
            status = get_youtube_status()
            youtube_active = status.get('active', False)
            if youtube_active:
                log("YouTube Chat erfolgreich initialisiert", platform="YOUTUBE")
            else:
                log("YouTube Chat noch nicht aktiv - wird überwacht", platform="YOUTUBE")
            
            # Starte YouTube Status Monitor
            youtube_monitor_thread = threading.Thread(target=youtube_status_monitor)
            youtube_monitor_thread.daemon = True
            youtube_monitor_thread.start()
            threads.append(youtube_monitor_thread)
        
        # Gemeinsame Threads
        joke_thread = threading.Thread(target=auto_joke_worker)
        joke_thread.daemon = True
        joke_thread.start()
        threads.append(joke_thread)
        
        comment_thread = threading.Thread(target=auto_comment_worker)
        comment_thread.daemon = True
        comment_thread.start()
        threads.append(comment_thread)
        
        scene_thread = threading.Thread(target=auto_scene_comment_worker)
        scene_thread.daemon = True
        scene_thread.start()
        threads.append(scene_thread)
        
        reminder_thread = threading.Thread(target=command_reminder_worker)
        reminder_thread.daemon = True
        reminder_thread.start()
        threads.append(reminder_thread)
        
        # Test der Bildanalyse beim Start
        log("Teste Bildanalyse-Funktionen...")
        screenshot = get_latest_screenshot()
        if screenshot:
            test_description = analyze_image_with_llava(screenshot)
            if test_description:
                log(f"Bildanalyse funktioniert: {len(test_description)} Zeichen Beschreibung erhalten")
            else:
                log_error("Bildanalyse-Test fehlgeschlagen! !bild-Befehl wird möglicherweise nicht funktionieren.")
        else:
            log("Keine Screenshots zum Testen gefunden")
        
        log("Multi-Platform-Bot läuft jetzt...")
        
        # Status-Ausgabe alle 60 Sekunden
        status_counter = 0
        while running:
            time.sleep(1)
            status_counter += 1
            
            if status_counter >= 60:  # Alle 60 Sekunden
                status_counter = 0
                platforms_status = []
                if ENABLE_TWITCH:
                    platforms_status.append(f"Twitch: {'✅' if twitch_connected else '❌'}")
                if ENABLE_YOUTUBE and YOUTUBE_AVAILABLE:
                    platforms_status.append(f"YouTube: {'✅' if youtube_active else '❌'}")
                
                log(f"Status: {' | '.join(platforms_status) if platforms_status else 'Keine Plattformen aktiv'}")
    
    except KeyboardInterrupt:
        log("Bot wird durch Benutzer beendet")
    except Exception as e:
        log_error("Unerwarteter Fehler im Hauptprogramm", e)
    finally:
        running = False
        
        if ENABLE_YOUTUBE and YOUTUBE_AVAILABLE:
            stop_youtube_chat_reader()
        
        if twitch_sock:
            try:
                twitch_sock.close()
            except:
                pass
        
        remove_pid_file()
        log("Multi-Platform-Bot wird beendet...")

if __name__ == "__main__":
    main()

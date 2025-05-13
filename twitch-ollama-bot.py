#!/usr/bin/env python3
# twitch-ollama-bot.py - Ein Twitch-Chat-Bot mit Ollama-Integration für KI-gestützte Interaktionen

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

# Prüfung der kritischen Umgebungsvariablen
if not NICKNAME or not TOKEN or not CHANNEL:
    print("Kritische Umgebungsvariablen fehlen. Bitte .env-Datei prüfen: BOT_USERNAME, OAUTH_TOKEN, CHANNEL")
    # Fallback für Test-/Entwicklungszwecke
    if not NICKNAME: 
        NICKNAME = "testbot"
        print("Verwende Fallback für BOT_USERNAME")
    if not TOKEN: 
        TOKEN = "oauth:test"
        print("Verwende Fallback für OAUTH_TOKEN (nur für Tests!)")
    if not CHANNEL: 
        CHANNEL = "#testchannel"
        print("Verwende Fallback für CHANNEL")

# Ollama-Konfiguration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL = os.getenv("OLLAMA_MODEL", "zephyr")
VISION_MODEL = os.getenv("VISION_MODEL", "llava")

# Pfade und Dateien
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if not os.path.exists(BASE_DIR):
    BASE_DIR = os.path.expanduser("~/zephyr")
    os.makedirs(BASE_DIR, exist_ok=True)
    print(f"BASE_DIR nicht gefunden, verwende: {BASE_DIR}")

LOG_FILE = os.path.join(BASE_DIR, "twitch-ollama-bot.log")
GAME_STATE_FILE = os.path.join(BASE_DIR, "game_state.json")
PID_FILE = os.path.join(BASE_DIR, "twitch-ollama-bot.pid")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")
VISION_CACHE_FILE = os.path.join(BASE_DIR, "latest_vision.txt")

# Timing-Konfiguration
AUTO_JOKE_INTERVAL = int(os.getenv("AUTO_JOKE_INTERVAL", "180"))  # Sekunden zwischen automatischen Witzen
AUTO_COMMENT_INTERVAL = int(os.getenv("AUTO_COMMENT_INTERVAL", "240"))  # Sekunden zwischen automatischen Kommentaren
AUTO_SCENE_COMMENT_INTERVAL = int(os.getenv("AUTO_SCENE_COMMENT_INTERVAL", "300"))  # Sekunden zwischen Kommentaren zu Szenen
COMMAND_REMINDER_INTERVAL = int(os.getenv("COMMAND_REMINDER_INTERVAL", "600"))  # Sekunden zwischen Befehlserinnerungen
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "30"))  # Timeout für Ollama-Anfragen in Sekunden
RECONNECT_DELAY = int(os.getenv("RECONNECT_DELAY", "10"))  # Sekunden zwischen Wiederverbindungsversuchen
PING_INTERVAL = int(os.getenv("PING_INTERVAL", "30"))  # Sekunden zwischen PING-Anfragen
SOCKET_TIMEOUT = int(os.getenv("SOCKET_TIMEOUT", "15"))  # Socket-Timeout in Sekunden
OLLAMA_RETRY_COUNT = int(os.getenv("OLLAMA_RETRY_COUNT", "3"))  # Anzahl der Wiederholungsversuche für Ollama-API-Anfragen

# Debug-Level (0=minimal, 1=normal, 2=ausführlich)
DEBUG_LEVEL = int(os.getenv("DEBUG_LEVEL", "1"))

# === Vordefinierte Text-Antworten ===
# Fallback-Witze, wenn die Ollama-API nicht antwortet
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

# Fallback-Kommentare für Spiele
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

# Fallback-Kommentare für Szenen/Bilder
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

# Kommentare für Programmiercode
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

# Kommentare für Webseiten
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

# Kommentare für Terminal/Konsole
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

# Kommentare für Dokumente
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

# Begrüßungen für neue Zuschauer
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

# Befehlserinnerungen
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
is_connected = False
sock = None
known_viewers = set()
game_state = {}
last_ping_time = 0
last_scene_comment_time = 0
reconnect_lock = threading.Lock()

# === Logging-Funktionen ===
def log(message, level=1):
    if level > DEBUG_LEVEL:
        return
        
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"[{timestamp}] Fehler beim Loggen: {e}")

def log_error(message, exception=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] ERROR: {message}")
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] ERROR: {message}\n")
            if exception:
                f.write(f"[{timestamp}] Exception: {str(exception)}\n")
                if DEBUG_LEVEL >= 2:  # Nur bei hohem Debug-Level den vollen Traceback loggen
                    f.write(f"[{timestamp}] {traceback.format_exc()}\n")
    except Exception as e:
        print(f"[{timestamp}] Fehler beim Loggen: {e}")

# === PID-Datei-Funktionen ===
def create_pid_file():
    try:
        pid = os.getpid()
        with open(PID_FILE, 'w') as f:
            f.write(str(pid))
        log(f"PID-Datei erstellt: {pid}")
    except Exception as e:
        log_error("Fehler beim Erstellen der PID-Datei", e)

def remove_pid_file():
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
            log("PID-Datei entfernt")
    except Exception as e:
        log_error("Fehler beim Entfernen der PID-Datei", e)

# === Spielstand-Funktionen ===
def load_game_state():
    global game_state
    try:
        if os.path.exists(GAME_STATE_FILE):
            with open(GAME_STATE_FILE, 'r', encoding="utf-8") as f:
                game_state = json.load(f)
                log(f"Spielstand geladen: {game_state}", level=2)
        else:
            game_state = {
                "spiel": "Unbekannt",
                "ort": "Unbekannt",
                "tode": 0,
                "level": 1,
                "spielzeit": "00:00:00"
            }
            save_game_state()
    except Exception as e:
        log_error("Fehler beim Laden des Spielstands", e)
        game_state = {
            "spiel": "Unbekannt",
            "ort": "Unbekannt",
            "tode": 0,
            "level": 1,
            "spielzeit": "00:00:00"
        }

def save_game_state():
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
        
        response = requests.post(
            "http://localhost:11434/api/generate", 
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            description = response.json().get("response", "").strip()
            log(f"LLaVA-Beschreibung erhalten ({len(description)} Zeichen)", level=1)
            
            # Speichere die Beschreibung für die nächste Verwendung
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
    
    if any(word in description_lower for word in ["code", "programming", "programmier", "entwicklungsumgebung", "editor", "code editor", "entwickler"]):
        return "code"
    elif any(word in description_lower for word in ["browser", "website", "webpage", "web page", "web-site", "webseite"]):
        return "browser"
    elif any(word in description_lower for word in ["game", "gaming", "playing", "spiel", "videospiel", "spielen", "videogame", "game character"]):
        return "game"
    elif any(word in description_lower for word in ["terminal", "console", "konsole", "command line", "kommandozeile", "shell", "bash", "ubuntu"]):
        return "terminal"
    elif any(word in description_lower for word in ["document", "dokument", "text", "word", "textdatei", "spreadsheet", "tabelle", "präsentation"]):
        return "document"
    
    return "allgemein"

def generate_content_comment(content_type, description):
    """Generiert einen Kommentar basierend auf dem Content-Typ und der Beschreibung"""
    
    # Spezifische Prompts je nach erkanntem Inhaltstyp
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
    
    # Auswahl des passenden Prompts
    prompt = prompts.get(content_type, prompts["allgemein"])
    
    # Anfrage an Ollama senden
    comment = get_response_from_ollama(prompt)
    
    # Fallback-Kommentare, wenn keine Antwort von Ollama
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
    log(f"Sende an Ollama: {prompt[:50]}...", level=1)
    
    for attempt in range(retries):
        try:
            # Versuche zuerst das neuere Format für Ollama 0.6.x
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL,
                    "messages": [{"role": "system", "content": f"Du bist ein hilfreicher Twitch-Bot namens {BOT_NAME}. Antworte immer auf Deutsch, kurz und prägnant."}, {"role": "user", "content": prompt}],
                    "stream": False
                },
                timeout=OLLAMA_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result.get("response", "").strip()
                if text:
                    log(f"Antwort von Ollama erhalten: {text[:50]}...", level=1)
                    return text
                
            # Wenn die erste Methode fehlschlägt, versuche die ältere Methode
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=OLLAMA_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result.get("response", "").strip()
                if text:
                    log(f"Antwort von Ollama erhalten (altes Format): {text[:50]}...", level=1)
                    return text
                    
            log_error(f"Fehler bei Ollama-Anfrage (Versuch {attempt+1}/{retries}): Status {response.status_code}")
            
            # Warte etwas länger zwischen den Versuchen
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                
        except Exception as e:
            log_error(f"Ausnahme bei Ollama-Anfrage (Versuch {attempt+1}/{retries})", e)
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    
    return None

# === IRC-Funktionen ===
def connect_to_twitch():
    global sock, is_connected
    
    with reconnect_lock:
        # Schließe alte Verbindung, falls vorhanden
        if sock:
            try:
                sock.close()
            except:
                pass
        
        # Erstelle neuen Socket
        sock = socket.socket()
        sock.settimeout(SOCKET_TIMEOUT)
        
        try:
            log(f"Verbinde mit {SERVER}:{PORT}...")
            sock.connect((SERVER, PORT))
            
            # Sende Authentifizierungs-Daten
            sock.send(f"PASS {TOKEN}\r\n".encode('utf-8'))
            sock.send(f"NICK {NICKNAME}\r\n".encode('utf-8'))
            
            # Warte auf Antwort
            response = ""
            start_time = time.time()
            while time.time() - start_time < 10:  # 10 Sekunden Timeout für Auth
                try:
                    data = sock.recv(2048).decode('utf-8')
                    if not data:
                        continue
                    
                    response += data
                    log(f"Empfangen: {data.strip()}", level=2)
                    
                    # Prüfe auf erfolgreiche Authentifizierung
                    if "Welcome, GLHF!" in response or ":tmi.twitch.tv 001" in response:
                        log("Erfolgreich authentifiziert!")
                        
                        # Fordere IRC-Capabilities an
                        sock.send("CAP REQ :twitch.tv/membership\r\n".encode('utf-8'))
                        sock.send("CAP REQ :twitch.tv/tags\r\n".encode('utf-8'))
                        sock.send("CAP REQ :twitch.tv/commands\r\n".encode('utf-8'))
                        
                        # Tritt dem Kanal bei
                        sock.send(f"JOIN {CHANNEL}\r\n".encode('utf-8'))
                        log(f"Kanal {CHANNEL} beigetreten")
                        
                        # Warte kurz auf Join-Bestätigung
                        time.sleep(1)
                        data = sock.recv(2048).decode('utf-8')
                        log(f"Join-Antwort: {data.strip()}", level=2)
                        
                        # Sende Begrüßung
                        send_message(f"👋 Hallo! Ich bin {BOT_NAME} und bereit, euch zu unterhalten! Befehle: !witz, !info, !stats, !hilfe")
                        
                        is_connected = True
                        return True
                except socket.timeout:
                    continue
                except Exception as recv_err:
                    log_error("Fehler beim Empfangen von Daten", recv_err)
                    break
            
            log_error("Timeout bei der Authentifizierung", None)
            return False
        except Exception as e:
            log_error("Verbindungsfehler", e)
            return False

def send_message(message):
    global is_connected
    
    if not is_connected:
        log("Nicht verbunden beim Senden der Nachricht")
        return False
    
    try:
        sock.send(f"PRIVMSG {CHANNEL} :{message}\r\n".encode('utf-8'))
        log(f"Nachricht gesendet: {message[:50]}...")
        return True
    except Exception as e:
        log_error("Fehler beim Senden der Nachricht", e)
        is_connected = False
        return False

def send_ping():
    global is_connected
    
    if not is_connected:
        return False
    
    try:
        sock.send("PING :tmi.twitch.tv\r\n".encode('utf-8'))
        log("PING gesendet", level=2)
        return True
    except Exception as e:
        log_error("Fehler beim Senden des PINGs", e)
        is_connected = False
        return False

def extract_username(message_line):
    # Versuche zuerst, den display-name aus Tags zu extrahieren
    username = ""
    
    if "display-name=" in message_line:
        try:
            parts = message_line.split("display-name=")[1].split(";")
            username = parts[0]
        except:
            pass
    
    # Wenn kein display-name gefunden wurde, versuche die traditionelle Methode
    if not username:
        try:
            parts = message_line.split("PRIVMSG", 1)[0].split("!")
            username = parts[0].replace(":", "")
        except:
            username = "unknown_user"
    
    return username

def process_message(user, message):
    log(f"Nachricht: {user}: {message}")
    
    # Wichtig: Jetzt vergleichen wir mit dem Bot-Namen statt mit NICKNAME
    if user.lower() == BOT_NAME.lower():
        log(f"Eigene Nachricht ignoriert: {message}")
        return
    
    # Prüfen, ob es ein neuer Zuschauer ist (nur für Nicht-Bot-Accounts)
    if user.lower() not in known_viewers and not user.lower().endswith('bot'):
        known_viewers.add(user.lower())
        # Begrüße neuen Zuschauer
        threading.Thread(target=lambda: greeting_worker(user)).start()
    
    # Befehle verarbeiten
    if message.lower() == "!witz":
        threading.Thread(target=joke_worker).start()
    
    elif message.lower() == "!info":
        send_info()
    
    elif message.lower() == "!stats":
        send_stats()
    
    elif message.lower() == "!hilfe" or message.lower() == "!help":
        send_help()
    
    elif message.lower() == "!bild" or message.lower() == "!scene":
        threading.Thread(target=scene_comment_worker).start()
    
    elif message.lower().startswith("!spiel "):
        game_name = message[7:].strip()
        if game_name:
            update_game(game_name, user)
    
    elif message.lower().startswith("!ort "):
        location = message[5:].strip()
        if location:
            update_location(location, user)
    
    elif message.lower() == "!tod":
        increment_deaths(user)
    
    elif message.lower().startswith("!level "):
        try:
            new_level = int(message[7:].strip())
            update_level(new_level, user)
        except ValueError:
            send_message(f"@{user} Bitte gib eine gültige Levelnummer an!")
    
    elif message.lower().startswith("!frag ") and BOT_NAME.lower() in message.lower():
        question = message.lower().split(BOT_NAME.lower(), 1)[1].strip()
        if question:
            threading.Thread(target=lambda: respond_to_direct_question(user, question)).start()
    
    elif BOT_NAME.lower() in message.lower():
        if "?" in message:
            threading.Thread(target=lambda: respond_to_question(user, message)).start()

# === Kommando-Funktionen ===
def joke_worker():
    prompt = f"Erzähle einen kurzen, lustigen Witz. Mach ihn besonders humorvoll."
    joke = get_response_from_ollama(prompt)
    if joke:
        send_message(f"🎭 {joke[:450]}")
        log(f"Witz gesendet: {joke[:50]}...")
    else:
        fallback_joke = random.choice(WITZE)
        send_message(f"🎭 {fallback_joke}")
        log(f"Fallback-Witz gesendet: {fallback_joke[:50]}...")

def scene_comment_worker():
    """Hauptfunktion für den !bild Befehl - holt Screenshot, analysiert und kommentiert ihn"""
    log("Scene Comment Worker gestartet", level=1)
    
    # 1. Neuester Screenshot finden
    screenshot_path = get_latest_screenshot()
    if not screenshot_path:
        log("Kein Screenshot gefunden", level=1)
        send_message(f"👁️ Ich kann leider keinen Screenshot finden, um ihn zu kommentieren.")
        return
    
    # 2. Bild mit LLaVA analysieren
    log(f"Analysiere Screenshot: {screenshot_path}", level=1)
    description = analyze_image_with_llava(screenshot_path)
    
    # Wenn keine Beschreibung, versuche gespeicherte zu laden
    if not description and os.path.exists(VISION_CACHE_FILE):
        try:
            with open(VISION_CACHE_FILE, "r", encoding="utf-8") as f:
                description = f.read().strip()
                log(f"Beschreibung aus Cache geladen ({len(description)} Zeichen)", level=1)
        except Exception as e:
            log_error(f"Fehler beim Lesen der Cache-Datei: {e}", e)
    
    # 3. Inhaltstyp identifizieren
    if description:
        content_type = identify_content_type(description)
        log(f"Erkannter Inhaltstyp: {content_type}", level=1)
        
        # 4. Kommentar generieren
        comment = generate_content_comment(content_type, description)
        
        # 5. Kommentar senden
        if comment:
            send_message(f"👁️ {comment[:450]}")
            log(f"Bildkommentar gesendet: {comment[:50]}...", level=1)
            return
    
    # Fallback, wenn keine Beschreibung oder kein Kommentar
    fallback_comment = random.choice(SCENE_KOMMENTARE)
    send_message(f"👁️ {fallback_comment}")
    log(f"Fallback-Bildkommentar gesendet: {fallback_comment[:50]}...")

def send_info():
    load_game_state()
    game = game_state.get("spiel", "Unbekannt")
    location = game_state.get("ort", "Unbekannt")
    send_message(f"🎮 Aktuelles Spiel: {game} | 📍 Ort: {location} | ⏱️ Spielzeit: {game_state.get('spielzeit', '00:00:00')}")

def send_stats():
    load_game_state()
    deaths = game_state.get("tode", 0)
    level = game_state.get("level", 1)
    send_message(f"📊 Statistiken: 💀 Tode: {deaths} | 📈 Level: {level} | 🕹️ Spiel: {game_state.get('spiel', 'Unbekannt')}")

def send_help():
    help_message = "📋 Befehle: !witz (zufälliger Witz), !info (Spielinfo), !stats (Statistiken), " + \
                  "!bild/!scene (Kommentar zur aktuellen Szene), !spiel NAME (Spiel ändern), " + \
                  "!ort NAME (Ort ändern), !tod (Tod zählen), !level X (Level setzen), !frag " + BOT_NAME + " ... (direkte Frage an mich)"
    send_message(help_message)

def update_game(game_name, user):
    load_game_state()
    old_game = game_state.get("spiel", "Unbekannt")
    game_state["spiel"] = game_name
    save_game_state()
    send_message(f"🎮 @{user} hat das Spiel von '{old_game}' zu '{game_name}' geändert!")

def update_location(location, user):
    load_game_state()
    old_location = game_state.get("ort", "Unbekannt")
    game_state["ort"] = location
    save_game_state()
    send_message(f"📍 @{user} hat den Ort von '{old_location}' zu '{location}' geändert!")

def increment_deaths(user):
    load_game_state()
    game_state["tode"] = game_state.get("tode", 0) + 1
    deaths = game_state["tode"]
    save_game_state()
    send_message(f"💀 R.I.P! Todeszähler steht jetzt bei {deaths}. " + random.choice([
        "Das war knapp!",
        "Kopf hoch, nächstes Mal klappt's besser!",
        "Halb so wild, du schaffst das!",
        "Aus Fehlern lernt man!",
        "Die Gegner werden auch immer gemeiner..."
    ]))

def update_level(level, user):
    load_game_state()
    old_level = game_state.get("level", 1)
    game_state["level"] = level
    save_game_state()
    
    if level > old_level:
        send_message(f"📈 Level Up! @{user} hat das Level von {old_level} auf {level} erhöht! Weiter so!")
    else:
        send_message(f"📊 @{user} hat das Level auf {level} gesetzt.")

def greeting_worker(user):
    greeting = random.choice(BEGRÜSSUNGEN).format(user=user)
    send_message(greeting)
    log(f"Neuer Zuschauer begrüßt: {user}")

def respond_to_question(user, message):
    prompt = f"Du bist ein Twitch-Bot namens {BOT_NAME}. Der Benutzer {user} hat dich folgendes gefragt: '{message}'. Gib eine kurze, hilfreiche Antwort (max. 200 Zeichen)."
    
    response = get_response_from_ollama(prompt)
    if response:
        send_message(f"@{user} {response[:450]}")
        log(f"Antwort auf Frage gesendet: {response[:50]}...")
    else:
        send_message(f"@{user} Hmm, ich bin mir nicht sicher, was ich dazu sagen soll. Versuch's mal mit !witz für einen lustigen Witz!")

def respond_to_direct_question(user, question):
    prompt = f"Du bist ein Twitch-Bot namens {BOT_NAME}. Beantworte folgende Frage von {user} direkt und präzise (max. 250 Zeichen): '{question}'."
    
    response = get_response_from_ollama(prompt)
    if response:
        send_message(f"@{user} {response[:450]}")
        log(f"Antwort auf direkte Frage gesendet: {response[:50]}...")
    else:
        send_message(f"@{user} Entschuldige, ich konnte keine Antwort generieren. Versuche es später noch einmal.")

# === Thread-Funktionen ===
def auto_joke_worker():
    log(f"Automatischer Witz-Thread gestartet - Intervall: {AUTO_JOKE_INTERVAL} Sekunden")
    time.sleep(10)  # Initiale Verzögerung
    
    while running:
        if is_connected:
            joke_worker()
        else:
            log("Überspringe automatischen Witz: Nicht verbunden")
        
        for _ in range(AUTO_JOKE_INTERVAL):
            if not running:
                break
            time.sleep(1)

def auto_comment_worker():
    log(f"Automatischer Kommentar-Thread gestartet - Intervall: {AUTO_COMMENT_INTERVAL} Sekunden")
    time.sleep(30)  # Initiale Verzögerung
    
    while running:
        if is_connected:
            load_game_state()
            game = game_state.get("spiel", "Unbekannt")
            location = game_state.get("ort", "Unbekannt")
            
            if game != "Unbekannt":
                prompt = f"Du bist ein Twitch-Bot namens {BOT_NAME}. Der Streamer spielt gerade {game} und befindet sich in/bei {location}. Gib einen kurzen, lustigen und hilfreichen Spielkommentar ab (max. 200 Zeichen)."
                comment = get_response_from_ollama(prompt)
                
                if comment:
                    send_message(f"🎮 {comment[:450]}")
                    log(f"Spiel-Kommentar gesendet: {comment[:50]}...")
                else:
                    fallback_comment = random.choice(GAME_KOMMENTARE)
                    send_message(f"🎮 {fallback_comment}")
                    log(f"Fallback-Spielkommentar gesendet: {fallback_comment[:50]}...")
        else:
            log("Überspringe automatischen Kommentar: Nicht verbunden")
        
        for _ in range(AUTO_COMMENT_INTERVAL):
            if not running:
                break
            time.sleep(1)

def auto_scene_comment_worker():
    global last_scene_comment_time
    
    log(f"Automatischer Bildkommentar-Thread gestartet - Intervall: {AUTO_SCENE_COMMENT_INTERVAL} Sekunden")
    time.sleep(60)  # Längere initiale Verzögerung
    
    while running:
        current_time = time.time()
        
        # Kommentare nur senden, wenn genug Zeit vergangen ist
        if is_connected and current_time - last_scene_comment_time >= AUTO_SCENE_COMMENT_INTERVAL:
            scene_comment_worker()
            last_scene_comment_time = current_time
        else:
            remaining = AUTO_SCENE_COMMENT_INTERVAL - (current_time - last_scene_comment_time)
            log(f"Überspringe automatischen Bildkommentar: Nächster in {int(max(0, remaining))} Sekunden", level=2)
        
        # Kurze Pause vor der nächsten Prüfung
        time.sleep(30)

def command_reminder_worker():
    log(f"Befehlserinnerungs-Thread gestartet - Intervall: {COMMAND_REMINDER_INTERVAL} Sekunden")
    time.sleep(120)  # Initiale Verzögerung (2 Minuten nach Start)
    
    reminder_index = 0
    while running:
        if is_connected:
            reminder = COMMAND_REMINDERS[reminder_index]
            send_message(reminder)
            log(f"Befehlserinnerung gesendet: {reminder}")
            
            # Nächster Index für die nächste Nachricht
            reminder_index = (reminder_index + 1) % len(COMMAND_REMINDERS)
        else:
            log("Überspringe Befehlserinnerung: Nicht verbunden")
        
        # Warte auf das nächste Intervall
        for _ in range(COMMAND_REMINDER_INTERVAL):
            if not running:
                break
            time.sleep(1)

def connection_watchdog():
    global is_connected, last_ping_time
    
    log("Verbindungs-Watchdog gestartet")
    retry_count = 0
    max_retries = 10
    
    while running:
        current_time = time.time()
        
        if not is_connected:
            retry_count += 1
            
            if retry_count > max_retries:
                log_error(f"Maximale Anzahl an Wiederverbindungsversuchen ({max_retries}) erreicht", None)
                log("Bot wird neu gestartet...")
                os._exit(42)  # Exit-Code 42 für Neustart
            
            log(f"Nicht verbunden - Versuche Wiederverbindung ({retry_count}/{max_retries})...")
            if connect_to_twitch():
                retry_count = 0
                last_ping_time = current_time
        else:
            # Sende regelmäßig PINGs zur Verbindungsprüfung
            if current_time - last_ping_time > PING_INTERVAL:
                if send_ping():
                    last_ping_time = current_time
        
        time.sleep(5)  # Kurze Pause

def message_receiver():
    global is_connected, last_ping_time
    
    log("Nachrichtenempfänger gestartet")
    
    while running:
        if not is_connected:
            time.sleep(1)
            continue
        
        try:
            response = ""
            sock.settimeout(0.5)  # Kurzer Timeout für schnelle Reaktion
            
            try:
                response = sock.recv(2048).decode('utf-8')
                last_ping_time = time.time()  # Aktualisiere bei jeder Nachricht
            except socket.timeout:
                continue
            except Exception as e:
                log_error("Fehler beim Empfangen", e)
                is_connected = False
                continue
            
            if not response:
                continue
            
            # Verarbeite jede Zeile separat
            for line in response.split('\r\n'):
                if not line:
                    continue
                
                log(f"Empfangen: {line}", level=2)  # Nur bei höherem Debug-Level
                
                # Reagiere auf PING vom Server
                if line.startswith("PING"):
                    reply = line.replace("PING", "PONG")
                    sock.send(f"{reply}\r\n".encode('utf-8'))
                    log(f"PING beantwortet mit: {reply}", level=2)  # Nur bei höherem Debug-Level
                    continue
                
                # Verarbeite Nachrichten
                if "PRIVMSG" in line:
                    # Extrahiere Benutzernamen und Nachricht
                    username = extract_username(line)
                    
                    try:
                        message_content = line.split("PRIVMSG", 1)[1].split(":", 1)[1]
                        
                        # Verarbeite die Nachricht in einem separaten Thread
                        threading.Thread(target=lambda: process_message(username, message_content)).start()
                    except Exception as msg_err:
                        log_error(f"Fehler beim Parsen der Nachricht: {line}", msg_err)
        except Exception as e:
            log_error("Unerwarteter Fehler im Nachrichtenempfänger", e)
            time.sleep(1)  # Kurze Pause bei Fehlern

# === Hauptprogramm ===
def main():
    global running, last_scene_comment_time
    
    try:
        # Erstelle PID-Datei
        create_pid_file()
        
        log(f"{BOT_NAME} Twitch-Bot wird gestartet...")
        
        # Initialisiere Zeitstempel
        current_time = time.time()
        last_scene_comment_time = current_time
        
        # Stelle sicher, dass Screenshots-Verzeichnis existiert
        if not os.path.exists(SCREENSHOTS_DIR):
            os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
            log(f"Screenshots-Verzeichnis erstellt: {SCREENSHOTS_DIR}")
        
        # Lade den initialen Spielstand
        load_game_state()
        
        # Initialisiere IRC-Verbindung
        if not connect_to_twitch():
            log_error("Initiale Verbindung fehlgeschlagen, versuche Wiederverbindung", None)
        
        # Starte Threads
        threads = []
        
        receiver_thread = threading.Thread(target=message_receiver)
        receiver_thread.daemon = True
        receiver_thread.start()
        threads.append(receiver_thread)
        
        joke_thread = threading.Thread(target=auto_joke_worker)
        joke_thread.daemon = True
        joke_thread.start()
        threads.append(joke_thread)
        
        comment_thread = threading.Thread(target=auto_comment_worker)
        comment_thread.daemon = True
        comment_thread.start()
        threads.append(comment_thread)
        
        # Thread für automatische Bildkommentare
        scene_thread = threading.Thread(target=auto_scene_comment_worker)
        scene_thread.daemon = True
        scene_thread.start()
        threads.append(scene_thread)
        
        # Thread für Befehlserinnerungen
        reminder_thread = threading.Thread(target=command_reminder_worker)
        reminder_thread.daemon = True
        reminder_thread.start()
        threads.append(reminder_thread)
        
        # Verbindungs-Watchdog
        watchdog_thread = threading.Thread(target=connection_watchdog)
        watchdog_thread.daemon = True
        watchdog_thread.start()
        threads.append(watchdog_thread)
        
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
        
        # Hauptschleife - warte einfach auf Beendigung
        log("Bot läuft jetzt...")
        while running:
            time.sleep(1)
    
    except KeyboardInterrupt:
        log("Bot wird durch Benutzer beendet")
    except Exception as e:
        log_error("Unerwarteter Fehler im Hauptprogramm", e)
    finally:
        running = False
        if sock:
            try:
                sock.close()
            except:
                pass
        
        remove_pid_file()
        log("Bot wird beendet...")

if __name__ == "__main__":
    main()

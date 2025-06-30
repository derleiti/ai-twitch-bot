#!/usr/bin/env python3
# multi_platform_bot.py - Zephyr Multi-Platform Bot (Twitch + YouTube)

import os
import sys
import time
import json
import random
import threading
import requests
import traceback
from datetime import datetime
from dotenv import load_dotenv

# Lade Umgebungsvariablen
load_dotenv()

# Base Directory Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if not os.path.exists(BASE_DIR):
    BASE_DIR = os.path.expanduser("~/zephyr")
    os.makedirs(BASE_DIR, exist_ok=True)

# Konfiguration
BOT_NAME = os.getenv("BOT_NAME", "zephyr")
DEBUG_LEVEL = int(os.getenv("DEBUG_LEVEL", "1"))

# Platform Configuration
ENABLE_TWITCH = os.getenv("ENABLE_TWITCH", "true").lower() == "true"
ENABLE_YOUTUBE = os.getenv("ENABLE_YOUTUBE", "true").lower() == "true"

# Timing
AUTO_JOKE_INTERVAL = int(os.getenv("AUTO_JOKE_INTERVAL", "180"))
AUTO_COMMENT_INTERVAL = int(os.getenv("AUTO_COMMENT_INTERVAL", "240"))
AUTO_SCENE_COMMENT_INTERVAL = int(os.getenv("AUTO_SCENE_COMMENT_INTERVAL", "300"))
COMMAND_REMINDER_INTERVAL = int(os.getenv("COMMAND_REMINDER_INTERVAL", "600"))

# Files
LOG_FILE = os.path.join(BASE_DIR, "multi-platform-bot.log")
PID_FILE = os.path.join(BASE_DIR, "multi-platform-bot.pid")
GAME_STATE_FILE = os.path.join(BASE_DIR, "game_state.json")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")
VISION_CACHE_FILE = os.path.join(BASE_DIR, "latest_vision.txt")

# Global Status
running = True
game_state = {}
known_viewers = set()

# Ollama Configuration
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "zephyr")
VISION_MODEL = os.getenv("VISION_MODEL", "llava")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "30"))
OLLAMA_RETRY_COUNT = int(os.getenv("OLLAMA_RETRY_COUNT", "3"))

# Fallback Content
WITZE = [
    "Warum können Skelette so schlecht lügen? Man sieht ihnen durch die Rippen!",
    "Was ist rot und schlecht für die Zähne? Ein Ziegelstein.",
    "Wie nennt man einen Cowboy ohne Pferd? Sattelschlepper.",
    "Warum sollte man nie Poker mit einem Zauberer spielen? Weil er Asse im Ärmel hat!",
    "Was macht ein Pirat beim Camping? Er schlägt sein Segel auf!",
    "Was ist ein Keks unter einem Baum? Ein schattiges Plätzchen!",
    "Was passiert, wenn man Cola und Bier gleichzeitig trinkt? Man colabiert.",
    "Warum können Seeräuber schlecht mit Kreisen rechnen? Weil sie Pi raten."
]

GAME_KOMMENTARE = [
    "Dieser Boss sieht gefährlich aus! Pass auf die Angriffe auf!",
    "Nice! Das war ein guter Move!",
    "Die Grafik in diesem Spiel ist wirklich beeindruckend!",
    "Diese Gegner-KI ist ziemlich schlau!",
    "Perfektes Timing bei diesem Sprung!",
    "Vielleicht solltest du deine Ausrüstung upgraden?"
]

SCENE_KOMMENTARE = [
    "Die Grafik sieht wirklich fantastisch aus!",
    "Die Farben und Texturen in dieser Szene sind unglaublich detailliert!",
    "Diese Landschaft ist einfach atemberaubend gestaltet!",
    "Der Charakter-Look ist echt cool - tolle Details!",
    "Die Lichtstimmung in dieser Szene ist wirklich beeindruckend!"
]

COMMAND_REMINDERS = [
    "📋 Verfügbare Befehle: !witz, !info, !stats, !hilfe, !bild, !spiel NAME, !ort NAME, !tod, !level X, !frag zephyr ...",
    "👋 Neu hier? Mit !witz bekommst du einen zufälligen Witz von mir!",
    "🎮 Verwende !info für aktuelle Spielinfos oder !stats für Statistiken.",
    "❓ Du hast eine Frage? Benutze !frag zephyr gefolgt von deiner Frage!",
    "🖼️ Mit !bild oder !scene kommentiere ich das aktuelle Bild im Stream.",
    "🤔 Brauchst du Hilfe? Tippe !hilfe für eine Liste aller Befehle!"
]

BEGRÜSSUNGEN = [
    "Willkommen im Stream, {user}! Schön, dass du da bist!",
    "Hey {user}! Willkommen! Was hältst du bisher vom Stream?",
    "Hallo {user}! Danke, dass du vorbeischaust!",
    "Willkommen an Bord, {user}! Mach es dir gemütlich.",
    "Hi {user}! Schön, dich im Chat zu sehen!"
]

# === Logging Functions ===
def log(message, level=1):
    """Loggt eine Nachricht"""
    if level > DEBUG_LEVEL:
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"[MULTI] [{timestamp}] {message}"
    print(formatted_message)
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{formatted_message}\n")
    except Exception as e:
        print(f"Logging error: {e}")

def log_error(message, exception=None):
    """Loggt Fehlermeldungen"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"[MULTI] [{timestamp}] ERROR: {message}"
    print(formatted_message)
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{formatted_message}\n")
            if exception:
                f.write(f"[MULTI] [{timestamp}] Exception: {str(exception)}\n")
    except:
        pass

# === PID File Management ===
def create_pid_file():
    """Erstellt PID-Datei"""
    try:
        pid = os.getpid()
        with open(PID_FILE, 'w') as f:
            f.write(str(pid))
        log(f"PID-Datei erstellt: {pid}")
    except Exception as e:
        log_error("Fehler beim Erstellen der PID-Datei", e)

def remove_pid_file():
    """Entfernt PID-Datei"""
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
            log("PID-Datei entfernt")
    except Exception as e:
        log_error("Fehler beim Entfernen der PID-Datei", e)

# === Game State Management ===
def load_game_state():
    """Lädt Spielstand"""
    global game_state
    try:
        if os.path.exists(GAME_STATE_FILE):
            with open(GAME_STATE_FILE, 'r', encoding="utf-8") as f:
                game_state = json.load(f)
                log(f"Spielstand geladen: {game_state}")
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
        game_state = {"spiel": "Unbekannt", "ort": "Unbekannt", "tode": 0, "level": 1, "spielzeit": "00:00:00"}

def save_game_state():
    """Speichert Spielstand"""
    try:
        with open(GAME_STATE_FILE, 'w', encoding="utf-8") as f:
            json.dump(game_state, f, indent=2)
    except Exception as e:
        log_error("Fehler beim Speichern des Spielstands", e)

# === Ollama Functions ===
def check_ollama_server():
    """Prüft Ollama Server"""
    try:
        response = requests.get("http://localhost:11434/api/version", timeout=5)
        if response.status_code == 200:
            version_info = response.json()
            return True, version_info.get("version", "unbekannt")
        return False, None
    except Exception as e:
        log_error(f"Ollama-Server nicht erreichbar: {e}")
        return False, None

def get_response_from_ollama(prompt, retries=OLLAMA_RETRY_COUNT):
    """Sendet Anfrage an Ollama"""
    log(f"Sende an Ollama: {prompt[:50]}...")
    
    for attempt in range(retries):
        try:
            # Chat API versuchen
            response = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": OLLAMA_MODEL,
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
                    log(f"Antwort von Ollama Chat API erhalten: {text[:50]}...")
                    return text
        except Exception as e:
            log_error(f"Fehler bei Chat API-Anfrage, versuche Generate: {str(e)}", e)
            
        try:
            # Generate API als Fallback
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": OLLAMA_MODEL,
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
                    log(f"Antwort von Ollama Generate API erhalten: {text[:50]}...")
                    return text
                    
            log_error(f"Fehler bei Ollama-Anfrage (Versuch {attempt+1}/{retries}): Status {response.status_code}")
            
        except Exception as e:
            log_error(f"Fehler bei Ollama-Anfrage (Versuch {attempt+1}/{retries})", e)
        
        if attempt < retries - 1:
            wait_time = 2 * (attempt + 1)
            time.sleep(wait_time)
    
    return None

# === Platform Integration ===
def setup_platforms():
    """Initialisiert verfügbare Plattformen"""
    global twitch_enabled, youtube_enabled
    
    twitch_enabled = False
    youtube_enabled = False
    
    # Message Dispatcher initialisieren
    try:
        log("🔗 Initialisiere Message Dispatcher...")
        from message_dispatcher import message_dispatcher, start_dispatcher, register_platform_handler, register_platform_sender
        
        # Handler für eingehende Nachrichten registrieren
        register_platform_handler("twitch", handle_chat_message)
        register_platform_handler("youtube", handle_chat_message)
        register_platform_handler("vision", handle_vision_message)
        
        # Sender für ausgehende Nachrichten registrieren
        if ENABLE_TWITCH:
            register_platform_sender("twitch", send_twitch_message)
        if ENABLE_YOUTUBE:
            register_platform_sender("youtube", send_youtube_message)
        
        # Dispatcher starten
        start_dispatcher()
        log("✅ Message Dispatcher erfolgreich initialisiert")
        
    except ImportError:
        log_error("Message Dispatcher nicht verfügbar - verwende direkte Integration")
        return setup_platforms_direct()
    except Exception as e:
        log_error(f"Fehler beim Initialisieren des Message Dispatchers: {e}")
        return setup_platforms_direct()
    
    # Twitch Setup
    if ENABLE_TWITCH:
        try:
            from twitch_ollama_bot import connect_to_twitch, send_message as twitch_send
            if connect_to_twitch():
                twitch_enabled = True
                log("✅ Twitch erfolgreich initialisiert")
        except Exception as e:
            log_error(f"Twitch-Initialisierung fehlgeschlagen: {e}")
    
    # YouTube Setup
    if ENABLE_YOUTUBE:
        try:
            from youtube_chat_reader import test_youtube_connection, start_youtube_chat_reader
            if test_youtube_connection():
                start_youtube_chat_reader(youtube_message_handler)
                youtube_enabled = True
                log("✅ YouTube erfolgreich initialisiert")
        except Exception as e:
            log_error(f"YouTube-Initialisierung fehlgeschlagen: {e}")
    
    return twitch_enabled or youtube_enabled

def setup_platforms_direct():
    """Fallback: Direkte Platform-Integration ohne Message Dispatcher"""
    global twitch_enabled, youtube_enabled
    
    twitch_enabled = False
    youtube_enabled = False
    
    # Twitch
    if ENABLE_TWITCH:
        try:
            sys.path.append(BASE_DIR)
            import twitch_ollama_bot
            
            # Starte Twitch-Verbindung in separatem Thread
            twitch_thread = threading.Thread(target=twitch_ollama_bot.main)
            twitch_thread.daemon = True
            twitch_thread.start()
            
            twitch_enabled = True
            log("✅ Twitch (direkt) erfolgreich gestartet")
        except Exception as e:
            log_error(f"Twitch-Setup fehlgeschlagen: {e}")
    
    # YouTube
    if ENABLE_YOUTUBE:
        try:
            from youtube_chat_reader import test_youtube_connection, start_youtube_chat_reader
            if test_youtube_connection():
                start_youtube_chat_reader(youtube_message_handler)
                youtube_enabled = True
                log("✅ YouTube (direkt) erfolgreich gestartet")
        except Exception as e:
            log_error(f"YouTube-Setup fehlgeschlagen: {e}")
    
    return twitch_enabled or youtube_enabled

# === Message Handlers ===
def handle_chat_message(user, message, platform):
    """Behandelt Chat-Nachrichten von allen Plattformen"""
    log(f"💬 [{platform.upper()}] {user}: {message}")
    
    # Prüfe auf Bot-eigene Nachrichten
    if user.lower() == BOT_NAME.lower():
        return
    
    # Neue Zuschauer begrüßen
    viewer_key = f"{user}_{platform}"
    if viewer_key not in known_viewers and not user.lower().endswith('bot'):
        known_viewers.add(viewer_key)
        threading.Thread(target=lambda: greeting_worker(user, platform)).start()
    
    # Befehle verarbeiten
    process_commands(user, message, platform)

def handle_vision_message(source, message, metadata=None):
    """Behandelt Vision-Nachrichten (Screenshot-Kommentare)"""
    log(f"👁️ Vision: {message}")
    send_message_to_platforms(f"👁️ {message}")

def youtube_message_handler(user, message, platform):
    """YouTube-spezifischer Message Handler für direkte Integration"""
    handle_chat_message(user, message, platform)

# === Command Processing ===
def process_commands(user, message, platform):
    """Verarbeitet Chat-Befehle"""
    msg_lower = message.lower().strip()
    
    if msg_lower == "!witz":
        threading.Thread(target=joke_worker).start()
    elif msg_lower == "!info":
        send_info()
    elif msg_lower == "!stats":
        send_stats()
    elif msg_lower in ["!hilfe", "!help"]:
        send_help()
    elif msg_lower in ["!bild", "!scene"]:
        threading.Thread(target=scene_comment_worker).start()
    elif msg_lower.startswith("!spiel "):
        game_name = message[7:].strip()
        if game_name:
            update_game(game_name, user)
    elif msg_lower.startswith("!ort "):
        location = message[5:].strip()
        if location:
            update_location(location, user)
    elif msg_lower == "!tod":
        increment_deaths(user)
    elif msg_lower.startswith("!level "):
        try:
            new_level = int(message[7:].strip())
            update_level(new_level, user)
        except ValueError:
            send_message_to_platforms(f"@{user} Bitte gib eine gültige Levelnummer an!")
    elif msg_lower.startswith("!frag ") and BOT_NAME.lower() in msg_lower:
        question = message.lower().split(BOT_NAME.lower(), 1)[1].strip()
        if question:
            threading.Thread(target=lambda: respond_to_direct_question(user, question)).start()
    elif BOT_NAME.lower() in msg_lower and "?" in message:
        threading.Thread(target=lambda: respond_to_question(user, message)).start()

# === Worker Functions ===
def joke_worker():
    """Generiert und sendet einen Witz"""
    prompt = "Erzähle einen kurzen, lustigen Witz. Mach ihn besonders humorvoll."
    joke = get_response_from_ollama(prompt)
    if joke:
        send_message_to_platforms(f"🎭 {joke[:450]}")
        log(f"Witz gesendet: {joke[:50]}...")
    else:
        fallback_joke = random.choice(WITZE)
        send_message_to_platforms(f"🎭 {fallback_joke}")
        log(f"Fallback-Witz gesendet: {fallback_joke[:50]}...")

def scene_comment_worker():
    """Analysiert Screenshots und kommentiert sie"""
    log("Scene Comment Worker gestartet")
    
    # Finde neuesten Screenshot
    screenshot_path = get_latest_screenshot()
    if not screenshot_path:
        send_message_to_platforms("👁️ Ich kann leider keinen Screenshot finden.")
        return
    
    log(f"Analysiere Screenshot: {screenshot_path}")
    
    # Verwende analyze_and_respond.py für Bildanalyse
    try:
        from analyze_and_respond import analyze_and_comment
        result = analyze_and_comment(screenshot_path)
        if result:
            log("Bildkommentar erfolgreich generiert und gesendet")
        else:
            fallback_comment = random.choice(SCENE_KOMMENTARE)
            send_message_to_platforms(f"👁️ {fallback_comment}")
            log("Fallback-Bildkommentar gesendet")
    except Exception as e:
        log_error(f"Fehler bei Bildanalyse: {e}")
        fallback_comment = random.choice(SCENE_KOMMENTARE)
        send_message_to_platforms(f"👁️ {fallback_comment}")

def get_latest_screenshot():
    """Findet den neuesten Screenshot"""
    if not os.path.exists(SCREENSHOTS_DIR):
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        return None
    
    screenshots = sorted([
        os.path.join(SCREENSHOTS_DIR, f)
        for f in os.listdir(SCREENSHOTS_DIR)
        if f.lower().endswith(('.png', '.jpg', '.jpeg'))
    ], key=os.path.getmtime, reverse=True)
    
    if screenshots:
        log(f"Neuester Screenshot gefunden: {screenshots[0]}")
        return screenshots[0]
    return None

def greeting_worker(user, platform):
    """Begrüßt neue Zuschauer"""
    greeting = random.choice(BEGRÜSSUNGEN).format(user=user)
    send_message_to_platforms(greeting)
    log(f"Neuer Zuschauer begrüßt: {user} auf {platform}")

def respond_to_question(user, message):
    """Antwortet auf Fragen"""
    prompt = f"Du bist ein Twitch-Bot namens {BOT_NAME}. Der Benutzer {user} hat dich folgendes gefragt: '{message}'. Gib eine kurze, hilfreiche Antwort (max. 200 Zeichen)."
    response = get_response_from_ollama(prompt)
    if response:
        send_message_to_platforms(f"@{user} {response[:450]}")
    else:
        send_message_to_platforms(f"@{user} Hmm, ich bin mir nicht sicher. Versuch's mal mit !witz!")

def respond_to_direct_question(user, question):
    """Antwortet auf direkte Fragen"""
    prompt = f"Du bist ein Twitch-Bot namens {BOT_NAME}. Beantworte folgende Frage von {user} direkt und präzise (max. 250 Zeichen): '{question}'."
    response = get_response_from_ollama(prompt)
    if response:
        send_message_to_platforms(f"@{user} {response[:450]}")
    else:
        send_message_to_platforms(f"@{user} Entschuldige, ich konnte keine Antwort generieren.")

# === Info Functions ===
def send_info():
    """Sendet Spielinformationen"""
    load_game_state()
    game = game_state.get("spiel", "Unbekannt")
    location = game_state.get("ort", "Unbekannt")
    send_message_to_platforms(f"🎮 Spiel: {game} | 📍 Ort: {location} | ⏱️ Zeit: {game_state.get('spielzeit', '00:00:00')}")

def send_stats():
    """Sendet Spielstatistiken"""
    load_game_state()
    deaths = game_state.get("tode", 0)
    level = game_state.get("level", 1)
    send_message_to_platforms(f"📊 💀 Tode: {deaths} | 📈 Level: {level} | 🎮 Spiel: {game_state.get('spiel', 'Unbekannt')}")

def send_help():
    """Sendet Hilfe"""
    help_msg = f"📋 Befehle: !witz, !info, !stats, !bild, !spiel NAME, !ort NAME, !tod, !level X, !frag {BOT_NAME} ..., !hilfe"
    send_message_to_platforms(help_msg)

# === Game State Updates ===
def update_game(game_name, user):
    """Aktualisiert Spielname"""
    load_game_state()
    old_game = game_state.get("spiel", "Unbekannt")
    game_state["spiel"] = game_name
    save_game_state()
    send_message_to_platforms(f"🎮 @{user} hat das Spiel von '{old_game}' zu '{game_name}' geändert!")

def update_location(location, user):
    """Aktualisiert Ort"""
    load_game_state()
    old_location = game_state.get("ort", "Unbekannt")
    game_state["ort"] = location
    save_game_state()
    send_message_to_platforms(f"📍 @{user} hat den Ort von '{old_location}' zu '{location}' geändert!")

def increment_deaths(user):
    """Erhöht Todeszähler"""
    load_game_state()
    game_state["tode"] = game_state.get("tode", 0) + 1
    deaths = game_state["tode"]
    save_game_state()
    reactions = ["Das war knapp!", "Kopf hoch!", "Aus Fehlern lernt man!", "Die Gegner werden gemeiner..."]
    send_message_to_platforms(f"💀 R.I.P! Todeszähler: {deaths}. {random.choice(reactions)}")

def update_level(level, user):
    """Aktualisiert Level"""
    load_game_state()
    old_level = game_state.get("level", 1)
    game_state["level"] = level
    save_game_state()
    
    if level > old_level:
        send_message_to_platforms(f"📈 Level Up! @{user} hat Level {level} erreicht! Weiter so!")
    else:
        send_message_to_platforms(f"📊 @{user} hat das Level auf {level} gesetzt.")

# === Message Sending ===
def send_message_to_platforms(message, exclude_platform=None):
    """Sendet Nachricht an alle verfügbaren Plattformen"""
    success = False
    
    # Versuche Message Dispatcher
    try:
        from message_dispatcher import broadcast_message
        return broadcast_message(message, exclude_platform)
    except ImportError:
        pass
    except Exception as e:
        log_error(f"Message Dispatcher Fehler: {e}")
    
    # Fallback: Direkte Sendung
    if ENABLE_TWITCH and exclude_platform != "twitch":
        if send_twitch_message(message):
            success = True
    
    if ENABLE_YOUTUBE and exclude_platform != "youtube":
        if send_youtube_message(message):
            success = True
    
    return success

def send_twitch_message(message):
    """Sendet Nachricht an Twitch"""
    try:
        from twitch_ollama_bot import send_message
        return send_message(message)
    except Exception as e:
        log_error(f"Twitch-Sendung fehlgeschlagen: {e}")
        return False

def send_youtube_message(message):
    """Sendet Nachricht an YouTube (Placeholder - YouTube API unterstützt kein Senden)"""
    log(f"📺 [YouTube] Würde senden: {message}")
    return True  # YouTube unterstützt kein Senden, aber wir loggen die Nachricht

# === Auto Workers ===
def auto_joke_worker():
    """Automatische Witze"""
    log(f"Automatischer Witz-Thread gestartet - Intervall: {AUTO_JOKE_INTERVAL} Sekunden")
    time.sleep(10)
    
    while running:
        joke_worker()
        for _ in range(AUTO_JOKE_INTERVAL):
            if not running:
                break
            time.sleep(1)

def auto_comment_worker():
    """Automatische Spielkommentare"""
    log(f"Automatischer Kommentar-Thread gestartet - Intervall: {AUTO_COMMENT_INTERVAL} Sekunden")
    time.sleep(30)
    
    while running:
        load_game_state()
        game = game_state.get("spiel", "Unbekannt")
        location = game_state.get("ort", "Unbekannt")
        
        if game != "Unbekannt":
            prompt = f"Du bist ein Twitch-Bot namens {BOT_NAME}. Der Streamer spielt gerade {game} und befindet sich in/bei {location}. Gib einen kurzen, lustigen Spielkommentar ab (max. 200 Zeichen)."
            comment = get_response_from_ollama(prompt)
            
            if comment:
                send_message_to_platforms(f"🎮 {comment[:450]}")
                log(f"Spiel-Kommentar gesendet: {comment[:50]}...")
            else:
                fallback_comment = random.choice(GAME_KOMMENTARE)
                send_message_to_platforms(f"🎮 {fallback_comment}")
                log(f"Fallback-Spielkommentar gesendet: {fallback_comment[:50]}...")
        
        for _ in range(AUTO_COMMENT_INTERVAL):
            if not running:
                break
            time.sleep(1)

def auto_scene_comment_worker():
    """Automatische Bildkommentare"""
    log(f"Automatischer Bildkommentar-Thread gestartet - Intervall: {AUTO_SCENE_COMMENT_INTERVAL} Sekunden")
    time.sleep(60)
    
    last_comment_time = 0
    
    while running:
        current_time = time.time()
        
        if current_time - last_comment_time >= AUTO_SCENE_COMMENT_INTERVAL:
            scene_comment_worker()
            last_comment_time = current_time
        else:
            remaining = AUTO_SCENE_COMMENT_INTERVAL - (current_time - last_comment_time)
            log(f"Überspringe automatischen Bildkommentar: Nächster in {int(remaining)} Sekunden")
        
        time.sleep(30)

def command_reminder_worker():
    """Befehlserinnerungen"""
    log(f"Befehlserinnerungs-Thread gestartet - Intervall: {COMMAND_REMINDER_INTERVAL} Sekunden")
    time.sleep(120)
    
    reminder_index = 0
    while running:
        reminder = COMMAND_REMINDERS[reminder_index]
        send_message_to_platforms(reminder)
        log(f"Befehlserinnerung gesendet: {reminder}")
        
        reminder_index = (reminder_index + 1) % len(COMMAND_REMINDERS)
        
        for _ in range(COMMAND_REMINDER_INTERVAL):
            if not running:
                break
            time.sleep(1)

# === Status Monitor ===
def status_monitor():
    """Überwacht und loggt den Bot-Status"""
    while running:
        try:
            # Status-Message Dispatcher
            dispatcher_stats = ""
            try:
                from message_dispatcher import get_dispatcher_stats
                stats = get_dispatcher_stats()
                dispatcher_stats = f" | Dispatcher: {stats.get('total_messages', 0)} msgs"
            except:
                pass
            
            # Platform-Status
            twitch_status = "✅" if ENABLE_TWITCH else "❌"
            youtube_status = "✅" if ENABLE_YOUTUBE else "❌"
            
            log(f"Status: Twitch: {twitch_status} | YouTube: {youtube_status}{dispatcher_stats}")
            
        except Exception as e:
            log_error(f"Status Monitor Fehler: {e}")
        
        time.sleep(60)  # Alle 60 Sekunden

# === Image Analysis ===
def test_image_analysis():
    """Testet Bildanalyse-Funktionen"""
    log("Teste Bildanalyse-Funktionen...")
    
    screenshot = get_latest_screenshot()
    if screenshot:
        log(f"Analysiere Bild mit LLaVA: {screenshot}")
        
        try:
            # Verwende analyze_and_respond Modul
            from analyze_and_respond import get_vision_description
            description = get_vision_description(screenshot)
            
            if description:
                log(f"Bildanalyse funktioniert: {len(description)} Zeichen Beschreibung erhalten")
                # Speichere Beschreibung
                try:
                    with open(VISION_CACHE_FILE, "w", encoding="utf-8") as f:
                        f.write(description)
                    log(f"Beschreibung in {VISION_CACHE_FILE} gespeichert")
                except Exception as e:
                    log_error(f"Fehler beim Speichern der Beschreibung: {e}")
            else:
                log_error("Bildanalyse-Test fehlgeschlagen!")
                
        except ImportError:
            log_error("analyze_and_respond Modul nicht verfügbar")
        except Exception as e:
            log_error(f"Fehler bei Bildanalyse-Test: {e}")
    else:
        log("Keine Screenshots zum Testen gefunden")

# === Main Function ===
def main():
    global running
    
    try:
        # Setup
        create_pid_file()
        log(f"{BOT_NAME} Multi-Platform-Bot wird gestartet...")
        log(f"Plattformen: Twitch={ENABLE_TWITCH}, YouTube={ENABLE_YOUTUBE}")
        
        # Lade Spielstand
        load_game_state()
        
        # Prüfe Ollama
        server_running, version = check_ollama_server()
        if server_running:
            log(f"Ollama-Server ist erreichbar, Version: {version}")
        else:
            log_error("Ollama-Server ist nicht erreichbar!")
        
        # Setup Plattformen
        if not setup_platforms():
            log_error("Keine Plattform konnte initialisiert werden!")
            return
        
        # Starte Worker Threads
        threads = []
        
        # Auto-Workers
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
        
        # Status Monitor
        status_thread = threading.Thread(target=status_monitor)
        status_thread.daemon = True
        status_thread.start()
        threads.append(status_thread)
        
        # Teste Bildanalyse
        test_image_analysis()
        
        log("Multi-Platform-Bot läuft jetzt...")
        
        # Hauptschleife
        while running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        log("Bot wird durch Benutzer beendet")
    except Exception as e:
        log_error("Unerwarteter Fehler im Hauptprogramm", e)
    finally:
        running = False
        
        # Stoppe Message Dispatcher
        try:
            from message_dispatcher import stop_dispatcher
            stop_dispatcher()
        except:
            pass
        
        remove_pid_file()
        log("Multi-Platform-Bot wird beendet...")

if __name__ == "__main__":
    main()

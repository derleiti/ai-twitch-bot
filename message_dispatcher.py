#!/usr/bin/env python3
"""
Message Dispatcher - Zentrale Nachrichtenverarbeitung für Multi-Platform Chatbot
Verarbeitet Nachrichten von Twitch und YouTube gleichzeitig
"""
import os
import time
import threading
import json
import traceback
from datetime import datetime
from collections import deque
from dotenv import load_dotenv
from analyze_and_respond import analyze_and_comment

# Lade Umgebungsvariablen
load_dotenv()

# Konfiguration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")
VISION_CACHE_FILE = os.path.join(BASE_DIR, "latest_vision.txt")

# Erstelle notwendige Verzeichnisse
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# Logging-Dateien
DISPATCHER_LOG = os.path.join(LOG_DIR, "dispatcher.log")
TWITCH_LOG = os.path.join(LOG_DIR, "twitch.log") 
YOUTUBE_LOG = os.path.join(LOG_DIR, "youtube.log")
WATCHER_LOG = os.path.join(LOG_DIR, "watcher.log")

# Bot-Konfiguration
TWITCH_BOT_NAME = os.getenv("BOT_NAME", "zephyr").lower()
YOUTUBE_BOT_NAME = os.getenv("YOUTUBE_BOT_NAME", "ZephyrBotYT").lower()  # Wichtig: Unterschiedlich zum Kanalnamen!
CHANNEL_NAME = os.getenv("YOUTUBE_CHANNEL_NAME", "").lower()

# Dispatcher-Konfiguration
MAX_QUEUE_SIZE = 100
PROCESS_INTERVAL = 0.5  # Sekunden zwischen Nachrichtenverarbeitung
MAX_MESSAGE_AGE = 300   # Maximales Alter einer Nachricht in Sekunden

class MessageDispatcher:
    def __init__(self):
        self.message_queue = deque(maxlen=MAX_QUEUE_SIZE)
        self.running = False
        self.process_thread = None
        self.lock = threading.Lock()
        
        # Platform-spezifische Sender
        self.platform_senders = {}
        
        # Statistiken
        self.stats = {
            "total_messages": 0,
            "twitch_messages": 0,
            "youtube_messages": 0,
            "processed_messages": 0,
            "failed_messages": 0,
            "start_time": time.time()
        }
        
        self.log("Message Dispatcher initialisiert")
    
    def log(self, message, level="INFO", platform="DISPATCHER"):
        """Zentrale Logging-Funktion"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] [{level}] [{platform}] {message}"
        
        print(formatted_message)
        
        try:
            # Hauptlog
            with open(DISPATCHER_LOG, "a", encoding="utf-8") as f:
                f.write(f"{formatted_message}\n")
            
            # Platform-spezifische Logs
            if platform == "TWITCH":
                with open(TWITCH_LOG, "a", encoding="utf-8") as f:
                    f.write(f"{formatted_message}\n")
            elif platform == "YOUTUBE":
                with open(YOUTUBE_LOG, "a", encoding="utf-8") as f:
                    f.write(f"{formatted_message}\n")
            elif level == "VISION" or "bild" in message.lower():
                with open(WATCHER_LOG, "a", encoding="utf-8") as f:
                    f.write(f"{formatted_message}\n")
                    
        except Exception as e:
            print(f"[{timestamp}] [ERROR] [DISPATCHER] Logging-Fehler: {e}")
    
    def register_sender(self, platform, sender_function):
        """Registriert eine Sender-Funktion für eine Platform"""
        self.platform_senders[platform.lower()] = sender_function
        self.log(f"Sender für {platform} registriert")
    
    def add_message(self, platform, user, message, timestamp=None):
        """Fügt eine Nachricht zur Verarbeitungsqueue hinzu"""
        if timestamp is None:
            timestamp = time.time()
        
        # Filtere Bot-eigene Nachrichten
        user_lower = user.lower()
        if platform.lower() == "twitch" and user_lower == TWITCH_BOT_NAME:
            return False
        elif platform.lower() == "youtube" and user_lower == YOUTUBE_BOT_NAME:
            return False
        elif platform.lower() == "youtube" and CHANNEL_NAME and user_lower == CHANNEL_NAME:
            return False  # Filtere auch Kanalnachrichten
        
        message_obj = {
            "platform": platform.lower(),
            "user": user,
            "message": message,
            "timestamp": timestamp,
            "processed": False
        }
        
        with self.lock:
            self.message_queue.append(message_obj)
            self.stats["total_messages"] += 1
            self.stats[f"{platform.lower()}_messages"] += 1
        
        self.log(f"Nachricht hinzugefügt: {user}: {message[:50]}...", platform=platform.upper())
        return True
    
    def process_message(self, message_obj):
        """Verarbeitet eine einzelne Nachricht"""
        try:
            platform = message_obj["platform"]
            user = message_obj["user"]
            message = message_obj["message"]
            
            self.log(f"Verarbeite Nachricht von {user}: {message[:100]}...", platform=platform.upper())
            
            # Prüfe auf Befehle
            if self.is_command(message):
                response = self.handle_command(message_obj)
            else:
                # Normale Nachricht - mit Bildanalyse
                response = self.generate_contextual_response(message_obj)
            
            if response:
                success = self.send_response(platform, response)
                if success:
                    self.stats["processed_messages"] += 1
                    self.log(f"Antwort gesendet: {response[:100]}...", platform=platform.upper())
                else:
                    self.stats["failed_messages"] += 1
                    self.log(f"Fehler beim Senden der Antwort", "ERROR", platform.upper())
            
        except Exception as e:
            self.stats["failed_messages"] += 1
            self.log(f"Fehler bei Nachrichtenverarbeitung: {str(e)}", "ERROR")
            self.log(f"Traceback: {traceback.format_exc()}", "DEBUG")
    
    def is_command(self, message):
        """Prüft, ob eine Nachricht ein Bot-Befehl ist"""
        commands = ["!witz", "!info", "!stats", "!hilfe", "!help", "!bild", "!scene", 
                   "!spiel", "!ort", "!tod", "!level", "!frag"]
        
        message_lower = message.lower().strip()
        return any(message_lower.startswith(cmd) for cmd in commands)
    
    def handle_command(self, message_obj):
        """Behandelt Bot-Befehle"""
        message = message_obj["message"].lower().strip()
        user = message_obj["user"]
        platform = message_obj["platform"]
        
        if message == "!witz":
            return self.get_joke()
        elif message == "!bild" or message == "!scene":
            return self.get_image_comment()
        elif message == "!stats":
            return self.get_bot_stats()
        elif message == "!hilfe" or message == "!help":
            return self.get_help_message()
        elif message.startswith("!frag"):
            question = message[5:].strip()
            return self.answer_question(user, question)
        else:
            return f"@{user} Unbekannter Befehl. Tippe !hilfe für verfügbare Befehle."
    
    def generate_contextual_response(self, message_obj):
        """Generiert eine kontextuelle Antwort basierend auf Chat und aktuellem Bild"""
        try:
            message = message_obj["message"]
            user = message_obj["user"]
            platform = message_obj["platform"]
            
            # Lade aktuelle Bildbeschreibung
            image_context = ""
            if os.path.exists(VISION_CACHE_FILE):
                try:
                    with open(VISION_CACHE_FILE, "r", encoding="utf-8") as f:
                        image_context = f.read().strip()
                except Exception as e:
                    self.log(f"Fehler beim Lesen der Bildbeschreibung: {e}", "ERROR")
            
            # Erstelle kontextuellen Prompt
            prompt = f"""Du bist ein Twitch/YouTube-Bot namens Zephyr. 
            
Benutzer {user} hat auf {platform} geschrieben: "{message}"

Aktueller Bildinhalt im Stream: {image_context[:200] if image_context else "Kein Bildkontext verfügbar"}

Erstelle eine kurze, witzige und passende Antwort (max. 200 Zeichen) die sowohl auf die Nachricht als auch den Bildinhalt eingeht. Sei freundlich und unterhaltsam."""
            
            # Nutze die bestehende Ollama-Integration
            from analyze_and_respond import generate_chat_comment
            
            # Wenn Bildkontext vorhanden, nutze ihn
            if image_context:
                response = generate_chat_comment(f"Chat: {message} | Bild: {image_context}")
            else:
                # Fallback ohne Bildkontext
                response = generate_chat_comment(message)
            
            if response:
                return f"@{user} {response}"
            else:
                return None
                
        except Exception as e:
            self.log(f"Fehler bei kontextueller Antwortgenerierung: {e}", "ERROR")
            return None
    
    def get_joke(self):
        """Generiert einen Witz"""
        try:
            from analyze_and_respond import generate_chat_comment
            joke = generate_chat_comment("Erzähle einen kurzen, lustigen Witz für Twitch/YouTube Chat")
            return f"🎭 {joke}" if joke else "🎭 Warum ging der Programmierer zum Arzt? Er hatte einen Bug! 🐛"
        except:
            return "🎭 Warum ging der Programmierer zum Arzt? Er hatte einen Bug! 🐛"
    
    def get_image_comment(self):
        """Kommentiert das aktuelle Bild"""
        try:
            # Hole neuesten Screenshot
            screenshots = [f for f in os.listdir(SCREENSHOTS_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if not screenshots:
                return "👁️ Ich kann keinen Screenshot finden zum Kommentieren."
            
            latest_screenshot = os.path.join(SCREENSHOTS_DIR, sorted(screenshots)[-1])
            comment = analyze_and_comment(latest_screenshot)
            
            if comment:
                self.log(f"Bildkommentar generiert: {comment[:100]}...", "VISION")
                return f"👁️ {comment}"
            else:
                return "👁️ Die Grafik sieht interessant aus!"
                
        except Exception as e:
            self.log(f"Fehler bei Bildkommentar: {e}", "ERROR")
            return "👁️ Ich kann das Bild gerade nicht analysieren."
    
    def get_bot_stats(self):
        """Gibt Bot-Statistiken zurück"""
        uptime = int(time.time() - self.stats["start_time"])
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        
        return (f"📊 Stats: {self.stats['processed_messages']} Nachrichten verarbeitet | "
                f"Twitch: {self.stats['twitch_messages']} | YouTube: {self.stats['youtube_messages']} | "
                f"Uptime: {hours}h {minutes}m")
    
    def get_help_message(self):
        """Gibt Hilfe-Nachricht zurück"""
        return ("📋 Befehle: !witz (Witz), !bild (Bildkommentar), !stats (Statistiken), "
                "!frag [Frage] (Frage stellen), !hilfe (diese Hilfe)")
    
    def answer_question(self, user, question):
        """Beantwortet eine direkte Frage"""
        if not question:
            return f"@{user} Stell mir eine Frage mit: !frag [deine Frage]"
        
        try:
            from analyze_and_respond import generate_chat_comment
            prompt = f"Beantworte folgende Frage kurz und hilfreich: {question}"
            answer = generate_chat_comment(prompt)
            
            if answer:
                return f"@{user} {answer}"
            else:
                return f"@{user} Hmm, darauf habe ich leider keine gute Antwort."
                
        except Exception as e:
            self.log(f"Fehler bei Fragebeantwortung: {e}", "ERROR")
            return f"@{user} Entschuldige, ich konnte deine Frage nicht bearbeiten."
    
    def send_response(self, platform, response):
        """Sendet eine Antwort über die entsprechende Platform"""
        if platform in self.platform_senders:
            try:
                return self.platform_senders[platform](response)
            except Exception as e:
                self.log(f"Fehler beim Senden über {platform}: {e}", "ERROR")
                return False
        else:
            self.log(f"Kein Sender für Platform {platform} registriert", "ERROR")
            return False
    
    def process_queue(self):
        """Hauptverarbeitungsschleife für die Nachrichtenqueue"""
        while self.running:
            try:
                current_time = time.time()
                
                with self.lock:
                    # Entferne alte Nachrichten
                    while (self.message_queue and 
                           current_time - self.message_queue[0]["timestamp"] > MAX_MESSAGE_AGE):
                        old_msg = self.message_queue.popleft()
                        self.log(f"Nachricht zu alt entfernt: {old_msg['user']}: {old_msg['message'][:50]}...", "DEBUG")
                    
                    # Verarbeite nächste Nachricht
                    if self.message_queue:
                        message = self.message_queue.popleft()
                        if not message["processed"]:
                            message["processed"] = True
                            # Verarbeitung außerhalb des Locks
                            threading.Thread(target=self.process_message, args=(message,)).start()
                
                time.sleep(PROCESS_INTERVAL)
                
            except Exception as e:
                self.log(f"Fehler in Verarbeitungsschleife: {e}", "ERROR")
                time.sleep(1)
    
    def start(self):
        """Startet den Message Dispatcher"""
        if not self.running:
            self.running = True
            self.process_thread = threading.Thread(target=self.process_queue)
            self.process_thread.daemon = True
            self.process_thread.start()
            self.log("Message Dispatcher gestartet")
    
    def stop(self):
        """Stoppt den Message Dispatcher"""
        if self.running:
            self.running = False
            if self.process_thread:
                self.process_thread.join(timeout=5)
            self.log("Message Dispatcher gestoppt")

# Globale Dispatcher-Instanz
dispatcher = MessageDispatcher()

def get_dispatcher():
    """Gibt die globale Dispatcher-Instanz zurück"""
    return dispatcher

if __name__ == "__main__":
    # Test des Dispatchers
    dispatcher.start()
    
    try:
        # Simuliere einige Testnachrichten
        time.sleep(1)
        dispatcher.add_message("twitch", "testuser1", "!witz")
        dispatcher.add_message("youtube", "testuser2", "Das sieht cool aus!")
        dispatcher.add_message("twitch", "testuser3", "!bild")
        
        # Lasse den Dispatcher laufen
        time.sleep(10)
        
    except KeyboardInterrupt:
        print("Test beendet")
    finally:
        dispatcher.stop()

#!/usr/bin/env python3
"""Enhanced Message Dispatcher für Zephyr - Vollversion mit Auto-Features"""
import os
import time
import threading
import random
from datetime import datetime
from collections import deque, defaultdict
from dotenv import load_dotenv

load_dotenv()

# Konfiguration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")
VISION_CACHE_FILE = os.path.join(BASE_DIR, "latest_vision.txt")

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# Bot-Namen
TWITCH_BOT_NAME = os.getenv("BOT_NAME", "zephyr").lower()
YOUTUBE_BOT_NAME = os.getenv("YOUTUBE_BOT_NAME", "ZephyroBot").lower()
CHANNEL_NAME = os.getenv("YOUTUBE_CHANNEL_NAME", "").lower()

# Auto-Feature Konfiguration
AUTO_COMMAND_REMINDER = int(os.getenv("AUTO_COMMAND_REMINDER_MINUTES", "5")) * 60
AUTO_VISION_ANALYSIS = os.getenv("AUTO_VISION_ANALYSIS", "true").lower() == "true"
VISION_ANALYSIS_INTERVAL = int(os.getenv("VISION_ANALYSIS_INTERVAL_MINUTES", "2")) * 60
AUTO_VISION_COMMENTS = os.getenv("AUTO_VISION_COMMENTS", "true").lower() == "true"
VISION_COMMENT_INTERVAL = int(os.getenv("VISION_COMMENT_INTERVAL_MINUTES", "3")) * 60
ENABLE_COMMAND_SPAM = os.getenv("ENABLE_COMMAND_SPAM", "true").lower() == "true"
ENABLE_VISION_SPAM = os.getenv("ENABLE_VISION_SPAM", "true").lower() == "true"

class EnhancedMessageDispatcher:
    def __init__(self):
        self.message_queue = deque(maxlen=200)
        self.running = False
        self.process_thread = None
        self.auto_features_thread = None
        self.vision_thread = None
        self.lock = threading.Lock()
        self.platform_senders = {}
        
        self.stats = {
            "total_messages": 0,
            "twitch_messages": 0,
            "youtube_messages": 0,
            "processed_messages": 0,
            "failed_messages": 0,
            "vision_updates": 0,
            "auto_commands_sent": 0,
            "auto_vision_comments": 0,
            "start_time": time.time()
        }
        
        # Auto-Feature Timing
        self.last_command_reminder = 0
        self.last_vision_analysis = 0
        self.last_vision_comment = 0
        self.current_vision_context = {}
        
        self.last_response_time = defaultdict(float)
        self.min_response_interval = 3
        
        print("✅ Enhanced Message Dispatcher mit Auto-Features initialisiert")
    
    def log(self, message, level="INFO", platform="DISPATCHER"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{platform}] {message}")
    
    def register_sender(self, platform, sender_function):
        self.platform_senders[platform.lower()] = sender_function
        self.log(f"Sender für {platform} registriert", "SUCCESS")
    
    def add_message(self, platform, user, message, timestamp=None):
        if timestamp is None:
            timestamp = time.time()
        
        user_lower = user.lower()
        platform_lower = platform.lower()
        
        # Filtere Bot-eigene Nachrichten
        if platform_lower == "twitch" and user_lower == TWITCH_BOT_NAME:
            return False
        elif platform_lower == "youtube" and user_lower == YOUTUBE_BOT_NAME:
            return False
        elif platform_lower == "youtube" and CHANNEL_NAME and user_lower == CHANNEL_NAME:
            return False
        
        message_obj = {
            "platform": platform_lower,
            "user": user,
            "message": message.strip(),
            "timestamp": timestamp,
            "processed": False
        }
        
        with self.lock:
            self.message_queue.append(message_obj)
            self.stats["total_messages"] += 1
            self.stats[f"{platform_lower}_messages"] += 1
        
        self.log(f"📨 {user}: {message[:30]}...")
        return True
    
    def should_respond_now(self, platform):
        current_time = time.time()
        last_response = self.last_response_time[platform]
        return current_time - last_response >= self.min_response_interval
    
    def update_vision_context(self):
        """Aktualisiert den Bildkontext mit LLaVA"""
        try:
            # Hole neuesten Screenshot
            screenshots = [f for f in os.listdir(SCREENSHOTS_DIR) 
                          if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            
            if not screenshots:
                return False
            
            latest_screenshot = os.path.join(SCREENSHOTS_DIR, sorted(screenshots)[-1])
            
            # Analysiere Bild mit bestehender analyze_and_respond.py
            try:
                from analyze_and_respond import get_vision_description, identify_content_type
                
                description = get_vision_description(latest_screenshot)
                if description:
                    content_type = identify_content_type(description)
                    
                    self.current_vision_context = {
                        "description": description[:300],
                        "content_type": content_type,
                        "timestamp": time.time(),
                        "screenshot_path": latest_screenshot
                    }
                    
                    # Speichere für andere Komponenten
                    with open(VISION_CACHE_FILE, "w", encoding="utf-8") as f:
                        f.write(description)
                    
                    self.stats["vision_updates"] += 1
                    self.log(f"Bildkontext aktualisiert: {content_type}", "VISION")
                    return True
                    
            except ImportError:
                self.log("analyze_and_respond.py nicht verfügbar", "WARNING")
                return False
                
        except Exception as e:
            self.log(f"Fehler bei Bildanalyse: {str(e)}", "ERROR")
        
        return False
    
    def generate_vision_comment(self):
        """Generiert einen Kommentar basierend auf dem aktuellen Bild"""
        if not self.current_vision_context:
            return None
            
        try:
            from analyze_and_respond import generate_chat_comment
            
            content_type = self.current_vision_context.get("content_type", "unbekannt")
            description = self.current_vision_context.get("description", "")
            
            # Verschiedene Prompt-Stile
            prompts = {
                "witzig": f"Kommentiere witzig was auf dem Bild zu sehen ist ({content_type}): {description[:150]}. Maximal 120 Zeichen, deutsch, lustig.",
                "informativ": f"Beschreibe sachlich was auf dem Bild zu sehen ist ({content_type}): {description[:150]}. Maximal 120 Zeichen, deutsch.",
                "gaming": f"Kommentiere das Spiel/die Szene ({content_type}): {description[:150]}. Maximal 120 Zeichen, gaming-style, deutsch."
            }
            
            style = os.getenv("VISION_PROMPT_STYLE", "witzig")
            prompt = prompts.get(style, prompts["witzig"])
            
            comment = generate_chat_comment(prompt)
            
            if comment:
                max_length = int(os.getenv("VISION_MAX_COMMENT_LENGTH", "150"))
                return comment[:max_length]
            
        except Exception as e:
            self.log(f"Fehler bei Vision-Kommentar-Generierung: {e}", "ERROR")
        
        # Fallback-Kommentare
        fallbacks = [
            "👁️ Interessante Szene! Was denkst ihr dazu?",
            "🎮 Das sieht spannend aus!",
            "🖼️ Schöne Grafik in diesem Moment!",
            "📸 Screenshot-würdiger Moment!",
            "👀 Da passiert gerade einiges!"
        ]
        
        return random.choice(fallbacks)
    
    def send_to_all_platforms(self, message):
        """Sendet eine Nachricht an alle aktiven Plattformen"""
        sent_count = 0
        for platform, sender in self.platform_senders.items():
            try:
                if sender(message):
                    sent_count += 1
                    self.log(f"Auto-Message an {platform}: {message[:50]}...")
            except Exception as e:
                self.log(f"Fehler beim Senden an {platform}: {e}", "ERROR")
        return sent_count > 0
    
    def auto_features_worker(self):
        """Background-Thread für automatische Features"""
        while self.running:
            try:
                current_time = time.time()
                
                # Automatische Befehlserinnerung
                if (ENABLE_COMMAND_SPAM and 
                    current_time - self.last_command_reminder > AUTO_COMMAND_REMINDER):
                    
                    commands = [
                        "📋 Verfügbare Befehle: !ping, !stats, !witz, !hilfe, !bild",
                        "🎮 Probiert die Befehle aus: !ping (Test), !stats (Statistiken), !witz (Witz)",
                        "👁️ Neu: !bild für Live-Bildanalyse mit KI!",
                        "🤖 Ich bin Zephyr - euer KI-Bot! Befehle: !ping, !witz, !stats, !hilfe",
                        "💡 Tipp: Schreibt !hilfe für alle verfügbaren Bot-Befehle!"
                    ]
                    
                    message = random.choice(commands)
                    if self.send_to_all_platforms(message):
                        self.stats["auto_commands_sent"] += 1
                        self.last_command_reminder = current_time
                
                # Automatische Vision-Analyse
                if (AUTO_VISION_ANALYSIS and 
                    current_time - self.last_vision_analysis > VISION_ANALYSIS_INTERVAL):
                    
                    if self.update_vision_context():
                        self.last_vision_analysis = current_time
                
                # Automatische Vision-Kommentare
                if (AUTO_VISION_COMMENTS and ENABLE_VISION_SPAM and
                    self.current_vision_context and
                    current_time - self.last_vision_comment > VISION_COMMENT_INTERVAL):
                    
                    comment = self.generate_vision_comment()
                    if comment:
                        if self.send_to_all_platforms(f"👁️ {comment}"):
                            self.stats["auto_vision_comments"] += 1
                            self.last_vision_comment = current_time
                
                time.sleep(30)  # Prüfe alle 30 Sekunden
                
            except Exception as e:
                self.log(f"Fehler im Auto-Features Worker: {str(e)}", "ERROR")
                time.sleep(60)
    
    def handle_command(self, message_obj):
        message = message_obj["message"].lower().strip()
        user = message_obj["user"]
        platform = message_obj["platform"]
        
        if message == "!ping":
            return f"@{user} Pong! 🏓 Bot läuft auf {platform.title()} mit KI-Features!"
        
        elif message == "!stats":
            uptime = int(time.time() - self.stats["start_time"])
            hours = uptime // 3600
            minutes = (uptime % 3600) // 60
            return (f"@{user} 📊 Stats: {self.stats['processed_messages']} Nachrichten | "
                   f"Twitch: {self.stats['twitch_messages']} | YouTube: {self.stats['youtube_messages']} | "
                   f"Vision: {self.stats['vision_updates']} | Auto-Befehle: {self.stats['auto_commands_sent']} | "
                   f"Uptime: {hours}h {minutes}m")
        
        elif message == "!witz":
            try:
                from analyze_and_respond import generate_chat_comment
                joke = generate_chat_comment("Erzähle einen kurzen, lustigen Witz (max. 120 Zeichen)")
                if joke:
                    return f"@{user} 🎭 {joke}"
            except:
                pass
            
            jokes = [
                "Warum können Skelette schlecht lügen? Man sieht durch sie hindurch! 💀",
                "Was ist grün und klopft? Ein Klopfsalat! 🥬",
                "Warum nehmen Seeräuber keinen Kreis? Weil sie Pi raten! 🏴‍☠️",
                "Was ist schwarz-weiß und kommt nicht vom Fleck? Eine Zeitung! 📰",
                "Was macht ein Pirat beim Camping? Er schlägt sein Segel auf! ⛺"
            ]
            return f"@{user} 🎭 {random.choice(jokes)}"
        
        elif message == "!bild" or message == "!scene":
            return self.get_image_comment(user)
        
        elif message == "!hilfe" or message == "!help":
            return (f"@{user} 📋 Befehle: !ping (Test), !stats (Statistiken), !witz (Witz), "
                   "!bild (Live-Bildanalyse), !hilfe (diese Hilfe). "
                   "🤖 Powered by Zephyr KI!")
        
        return None
    
    def get_image_comment(self, user):
        """Kommentiert das aktuelle Bild"""
        try:
            # Aktualisiere Vision-Kontext falls nötig
            if not self.current_vision_context or time.time() - self.current_vision_context.get("timestamp", 0) > 120:
                if not self.update_vision_context():
                    return f"@{user} 👁️ Ich kann gerade kein Bild analysieren."
            
            comment = self.generate_vision_comment()
            if comment:
                return f"@{user} {comment}"
            else:
                return f"@{user} 👁️ Das aktuelle Bild ist interessant!"
                
        except Exception as e:
            self.log(f"Fehler bei Bildkommentar: {str(e)}", "ERROR")
            return f"@{user} 👁️ Bildanalyse gerade nicht verfügbar."
    
    def is_command(self, message):
        commands = ["!witz", "!ping", "!stats", "!hilfe", "!help", "!bild", "!scene"]
        return any(message.lower().strip().startswith(cmd) for cmd in commands)
    
    def process_message(self, message_obj):
        try:
            platform = message_obj["platform"]
            user = message_obj["user"]
            message = message_obj["message"]
            
            response = None
            
            if self.is_command(message):
                response = self.handle_command(message_obj)
            elif ("zephyr" in message.lower() or "bot" in message.lower() or 
                  "?" in message or random.random() < 0.05):
                responses = [
                    f"@{user} Hallo! Ich bin Zephyr, euer KI-Bot! 🤖 Probiert !hilfe für Befehle!",
                    f"@{user} Hi! Ich kann Bilder analysieren und Witze erzählen! 👁️🎭",
                    f"@{user} Hey! Verwendet !bild für Live-Bildanalyse oder !witz für einen Lacher! 😄"
                ]
                response = random.choice(responses)
            
            if response and self.should_respond_now(platform) and self.send_response(platform, response):
                self.stats["processed_messages"] += 1
                self.last_response_time[platform] = time.time()
                self.log(f"💬 Antwort: {response[:50]}...")
            
        except Exception as e:
            self.stats["failed_messages"] += 1
            self.log(f"Fehler bei Nachrichtenverarbeitung: {e}", "ERROR")
    
    def send_response(self, platform, response):
        if platform in self.platform_senders:
            try:
                return self.platform_senders[platform](response)
            except Exception as e:
                self.log(f"Fehler beim Senden über {platform}: {e}", "ERROR")
                return False
        return False
    
    def process_queue(self):
        while self.running:
            try:
                with self.lock:
                    if self.message_queue:
                        message = self.message_queue.popleft()
                        if not message["processed"]:
                            message["processed"] = True
                            threading.Thread(target=self.process_message, args=(message,), daemon=True).start()
                time.sleep(0.1)
            except Exception as e:
                self.log(f"Fehler in Verarbeitungsschleife: {e}", "ERROR")
                time.sleep(1)
    
    def start(self):
        if not self.running:
            self.running = True
            
            # Hauptverarbeitungsthread
            self.process_thread = threading.Thread(target=self.process_queue)
            self.process_thread.daemon = True
            self.process_thread.start()
            
            # Auto-Features-Thread
            self.auto_features_thread = threading.Thread(target=self.auto_features_worker)
            self.auto_features_thread.daemon = True
            self.auto_features_thread.start()
            
            # Initiale Bildanalyse
            self.update_vision_context()
            
            self.log("Enhanced Message Dispatcher mit Auto-Features gestartet", "SUCCESS")
    
    def stop(self):
        if self.running:
            self.running = False
            if self.process_thread:
                self.process_thread.join(timeout=5)
            if self.auto_features_thread:
                self.auto_features_thread.join(timeout=5)
            self.log("Enhanced Message Dispatcher gestoppt", "SUCCESS")

# Globale Instanz
dispatcher = EnhancedMessageDispatcher()

def get_dispatcher():
    return dispatcher

if __name__ == "__main__":
    print("🤖 Enhanced Message Dispatcher Test")
    dispatcher.start()
    time.sleep(10)
    dispatcher.stop()

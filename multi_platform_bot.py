#!/usr/bin/env python3
"""
Multi-Platform Bot - Hauptorchestrator für Twitch und YouTube
Koordiniert alle Bot-Komponenten und startet sie gemeinsam
"""
import os
import sys
import time
import signal
import threading
import traceback
from datetime import datetime
from dotenv import load_dotenv

# Lade Umgebungsvariablen
load_dotenv()

# Lokale Imports
from message_dispatcher import MessageDispatcher, get_dispatcher
from youtube_chat_reader import YouTubeChatReader

# Basis-Konfiguration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
PID_FILE = os.path.join(BASE_DIR, "multi_platform_bot.pid")

# Bot-Konfiguration
ENABLE_TWITCH = os.getenv("ENABLE_TWITCH", "true").lower() == "true"
ENABLE_YOUTUBE = os.getenv("ENABLE_YOUTUBE", "true").lower() == "true"
ENABLE_VISION = os.getenv("ENABLE_VISION", "true").lower() == "true"

class MultiPlatformBot:
    def __init__(self):
        self.running = False
        self.components = {}
        self.threads = []
        
        # Erstelle notwendige Verzeichnisse
        os.makedirs(LOG_DIR, exist_ok=True)
        
        # Initialisiere Dispatcher
        self.dispatcher = get_dispatcher()
        
        self.log("Multi-Platform Bot initialisiert")
    
    def log(self, message, level="INFO"):
        """Zentrale Logging-Funktion"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] [MAIN] [{level}] {message}"
        print(formatted_message)
        
        # Auch an Dispatcher weiterleiten
        if hasattr(self, 'dispatcher') and self.dispatcher:
            self.dispatcher.log(message, level, "MAIN")
    
    def create_pid_file(self):
        """Erstellt PID-Datei"""
        try:
            with open(PID_FILE, 'w') as f:
                f.write(str(os.getpid()))
            self.log(f"PID-Datei erstellt: {os.getpid()}")
        except Exception as e:
            self.log(f"Fehler beim Erstellen der PID-Datei: {e}", "ERROR")
    
    def remove_pid_file(self):
        """Entfernt PID-Datei"""
        try:
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
                self.log("PID-Datei entfernt")
        except Exception as e:
            self.log(f"Fehler beim Entfernen der PID-Datei: {e}", "ERROR")
    
    def setup_signal_handlers(self):
        """Richtet Signal-Handler ein für sauberes Beenden"""
        def signal_handler(signum, frame):
            self.log(f"Signal {signum} empfangen, beende Bot...")
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def start_twitch_component(self):
        """Startet die Twitch-Komponente"""
        if not ENABLE_TWITCH:
            self.log("Twitch-Integration deaktiviert")
            return None
        
        try:
            self.log("Starte Twitch-Komponente...")
            
            # Importiere und starte modifizierten Twitch Bot
            from twitch_integration import TwitchBotAdapter
            
            twitch_bot = TwitchBotAdapter(self.dispatcher)
            if twitch_bot.start():
                self.components["twitch"] = twitch_bot
                self.log("Twitch-Komponente erfolgreich gestartet")
                return twitch_bot
            else:
                self.log("Fehler beim Starten der Twitch-Komponente", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"Exception beim Starten der Twitch-Komponente: {e}", "ERROR")
            self.log(f"Traceback: {traceback.format_exc()}", "DEBUG")
            return None
    
    def start_youtube_component(self):
        """Startet die YouTube-Komponente"""
        if not ENABLE_YOUTUBE:
            self.log("YouTube-Integration deaktiviert")
            return None
        
        try:
            self.log("Starte YouTube-Komponente...")
            
            youtube_reader = YouTubeChatReader(self.dispatcher)
            
            # Registriere YouTube-Sender beim Dispatcher
            self.dispatcher.register_sender("youtube", youtube_reader.send_message)
            
            if youtube_reader.start():
                self.components["youtube"] = youtube_reader
                self.log("YouTube-Komponente erfolgreich gestartet")
                return youtube_reader
            else:
                self.log("Fehler beim Starten der YouTube-Komponente", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"Exception beim Starten der YouTube-Komponente: {e}", "ERROR")
            self.log(f"Traceback: {traceback.format_exc()}", "DEBUG")
            return None
    
    def start_vision_component(self):
        """Startet die Bildanalyse-Komponente"""
        if not ENABLE_VISION:
            self.log("Bildanalyse deaktiviert")
            return None
        
        try:
            self.log("Starte Bildanalyse-Komponente...")
            
            from vision_watcher import VisionWatcher
            
            vision_watcher = VisionWatcher()
            if vision_watcher.start():
                self.components["vision"] = vision_watcher
                self.log("Bildanalyse-Komponente erfolgreich gestartet")
                return vision_watcher
            else:
                self.log("Fehler beim Starten der Bildanalyse-Komponente", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"Exception beim Starten der Bildanalyse-Komponente: {e}", "ERROR")
            self.log(f"Traceback: {traceback.format_exc()}", "DEBUG")
            return None
    
    def check_dependencies(self):
        """Prüft Abhängigkeiten und Konfiguration"""
        self.log("Prüfe Abhängigkeiten...")
        
        missing_deps = []
        
        # Prüfe Ollama-Server
        try:
            import requests
            response = requests.get("http://localhost:11434/api/version", timeout=5)
            if response.status_code == 200:
                version_info = response.json()
                self.log(f"Ollama-Server erreichbar: Version {version_info.get('version', 'unbekannt')}")
            else:
                missing_deps.append("Ollama-Server nicht erreichbar")
        except Exception as e:
            missing_deps.append(f"Ollama-Server nicht erreichbar: {e}")
        
        # Prüfe Twitch-Konfiguration
        if ENABLE_TWITCH:
            twitch_config = ["BOT_USERNAME", "OAUTH_TOKEN", "CHANNEL"]
            for config in twitch_config:
                if not os.getenv(config):
                    missing_deps.append(f"Twitch-Konfiguration fehlt: {config}")
        
        # Prüfe YouTube-Konfiguration
        if ENABLE_YOUTUBE:
            youtube_config = ["YOUTUBE_API_KEY", "YOUTUBE_CHANNEL_ID"]
            for config in youtube_config:
                if not os.getenv(config):
                    missing_deps.append(f"YouTube-Konfiguration fehlt: {config}")
        
        # Prüfe Vision-Abhängigkeiten
        if ENABLE_VISION:
            screenshots_dir = os.path.join(BASE_DIR, "screenshots")
            if not os.path.exists(screenshots_dir):
                os.makedirs(screenshots_dir, exist_ok=True)
                self.log(f"Screenshots-Verzeichnis erstellt: {screenshots_dir}")
        
        if missing_deps:
            self.log("Fehlende Abhängigkeiten:", "ERROR")
            for dep in missing_deps:
                self.log(f"  - {dep}", "ERROR")
            return False
        
        self.log("Alle Abhängigkeiten erfüllt")
        return True
    
    def monitor_components(self):
        """Überwacht alle Komponenten und startet sie bei Bedarf neu"""
        while self.running:
            try:
                for name, component in list(self.components.items()):
                    if hasattr(component, 'running') and not component.running:
                        self.log(f"Komponente {name} nicht mehr aktiv, versuche Neustart...", "WARNING")
                        
                        # Versuche Neustart der Komponente
                        if name == "twitch":
                            new_component = self.start_twitch_component()
                        elif name == "youtube":
                            new_component = self.start_youtube_component()
                        elif name == "vision":
                            new_component = self.start_vision_component()
                        else:
                            continue
                        
                        if new_component:
                            self.components[name] = new_component
                            self.log(f"Komponente {name} erfolgreich neu gestartet")
                        else:
                            self.log(f"Neustart von Komponente {name} fehlgeschlagen", "ERROR")
                
                time.sleep(30)  # Prüfe alle 30 Sekunden
                
            except Exception as e:
                self.log(f"Fehler beim Überwachen der Komponenten: {e}", "ERROR")
                time.sleep(10)
    
    def print_status(self):
        """Gibt den aktuellen Status aus"""
        self.log("=== Multi-Platform Bot Status ===")
        self.log(f"Twitch: {'✓ Aktiv' if 'twitch' in self.components else '✗ Inaktiv'}")
        self.log(f"YouTube: {'✓ Aktiv' if 'youtube' in self.components else '✗ Inaktiv'}")
        self.log(f"Vision: {'✓ Aktiv' if 'vision' in self.components else '✗ Inaktiv'}")
        
        # Dispatcher-Statistiken
        if self.dispatcher:
            stats = self.dispatcher.stats
            self.log(f"Verarbeitete Nachrichten: {stats['processed_messages']}")
            self.log(f"Twitch: {stats['twitch_messages']} | YouTube: {stats['youtube_messages']}")
        
        self.log("================================")
    
    def start(self):
        """Startet den Multi-Platform Bot"""
        self.log("Starte Multi-Platform Bot...")
        
        # Prüfe Abhängigkeiten
        if not self.check_dependencies():
            self.log("Abhängigkeiten nicht erfüllt, beende Bot", "ERROR")
            return False
        
        # Erstelle PID-Datei und Signal-Handler
        self.create_pid_file()
        self.setup_signal_handlers()
        
        self.running = True
        
        # Starte Dispatcher
        self.dispatcher.start()
        self.log("Message Dispatcher gestartet")
        
        # Starte Komponenten
        self.start_twitch_component()
        self.start_youtube_component()
        self.start_vision_component()
        
        # Starte Monitor-Thread
        monitor_thread = threading.Thread(target=self.monitor_components)
        monitor_thread.daemon = True
        monitor_thread.start()
        self.threads.append(monitor_thread)
        
        # Status ausgeben
        time.sleep(2)
        self.print_status()
        
        return True
    
    def stop(self):
        """Stoppt den Multi-Platform Bot"""
        if not self.running:
            return
        
        self.log("Stoppe Multi-Platform Bot...")
        self.running = False
        
        # Stoppe alle Komponenten
        for name, component in self.components.items():
            try:
                if hasattr(component, 'stop'):
                    component.stop()
                    self.log(f"Komponente {name} gestoppt")
            except Exception as e:
                self.log(f"Fehler beim Stoppen von {name}: {e}", "ERROR")
        
        # Stoppe Dispatcher
        if self.dispatcher:
            self.dispatcher.stop()
            self.log("Message Dispatcher gestoppt")
        
        # Warte auf Threads
        for thread in self.threads:
            try:
                thread.join(timeout=5)
            except:
                pass
        
        # Entferne PID-Datei
        self.remove_pid_file()
        
        self.log("Multi-Platform Bot gestoppt")
    
    def run(self):
        """Hauptlaufschleife"""
        if not self.start():
            return
        
        try:
            self.log("Multi-Platform Bot läuft... (Ctrl+C zum Beenden)")
            
            # Status-Updates alle 5 Minuten
            last_status = time.time()
            
            while self.running:
                current_time = time.time()
                
                # Status-Update
                if current_time - last_status > 300:  # 5 Minuten
                    self.print_status()
                    last_status = current_time
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.log("Beendet durch Benutzer")
        except Exception as e:
            self.log(f"Unerwarteter Fehler: {e}", "ERROR")
            self.log(f"Traceback: {traceback.format_exc()}", "DEBUG")
        finally:
            self.stop()

# Twitch-Integration (Adapter für bestehenden Bot)
class TwitchBotAdapter:
    """Adapter für den bestehenden Twitch-Bot"""
    
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.running = False
        self.bot_thread = None
        
    def start(self):
        """Startet den Twitch-Bot-Adapter"""
        try:
            # Registriere Twitch-Sender beim Dispatcher
            self.dispatcher.register_sender("twitch", self.send_twitch_message)
            
            # Starte den bestehenden Twitch-Bot in einem Thread
            self.bot_thread = threading.Thread(target=self.run_twitch_bot)
            self.bot_thread.daemon = True
            self.running = True
            self.bot_thread.start()
            
            return True
        except Exception as e:
            print(f"Fehler beim Starten des Twitch-Adapters: {e}")
            return False
    
    def send_twitch_message(self, message):
        """Sendet eine Nachricht über Twitch"""
        try:
            # Hier würde die Nachricht an den Twitch-Bot weitergegeben
            # Da der bestehende Bot seine eigene send_message Funktion hat,
            # nutzen wir eine globale Variable oder Queue
            
            # Temporäre Lösung: Nutze eine Queue oder globale Variable
            if hasattr(self, 'twitch_sender') and self.twitch_sender:
                return self.twitch_sender(message)
            
            return False
        except Exception as e:
            print(f"Fehler beim Senden der Twitch-Nachricht: {e}")
            return False
    
    def run_twitch_bot(self):
        """Führt den bestehenden Twitch-Bot aus"""
        try:
            # Importiere den bestehenden Bot
            import subprocess
            import sys
            
            # Starte den bestehenden Twitch-Bot als Subprozess
            twitch_script = os.path.join(BASE_DIR, "twitch-ollama-bot.py")
            if os.path.exists(twitch_script):
                self.process = subprocess.Popen([sys.executable, twitch_script])
                self.process.wait()
            else:
                print(f"Twitch-Bot-Skript nicht gefunden: {twitch_script}")
                
        except Exception as e:
            print(f"Fehler beim Ausführen des Twitch-Bots: {e}")
            self.running = False
    
    def stop(self):
        """Stoppt den Twitch-Bot-Adapter"""
        self.running = False
        if hasattr(self, 'process'):
            try:
                self.process.terminate()
            except:
                pass

# Vision Watcher (Improved)
class VisionWatcher:
    """Verbesserte Bildanalyse-Komponente"""
    
    def __init__(self):
        self.running = False
        self.watcher_thread = None
    
    def start(self):
        """Startet den Vision Watcher"""
        try:
            # Starte den bestehenden Screenshot-Watcher
            import subprocess
            import sys
            
            watcher_script = os.path.join(BASE_DIR, "watch_screenshots.py")
            if os.path.exists(watcher_script):
                self.process = subprocess.Popen([sys.executable, watcher_script])
                self.running = True
                return True
            else:
                print(f"Vision-Watcher-Skript nicht gefunden: {watcher_script}")
                return False
                
        except Exception as e:
            print(f"Fehler beim Starten des Vision-Watchers: {e}")
            return False
    
    def stop(self):
        """Stoppt den Vision Watcher"""
        self.running = False
        if hasattr(self, 'process'):
            try:
                self.process.terminate()
            except:
                pass

def main():
    """Hauptfunktion"""
    print("🤖 Zephyr Multi-Platform Bot")
    print("============================")
    
    bot = MultiPlatformBot()
    bot.run()

if __name__ == "__main__":
    main()

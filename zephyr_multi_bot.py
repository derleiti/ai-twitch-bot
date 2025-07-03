#!/usr/bin/env python3
"""
Zephyr Multi-Platform Bot v2.0 - Unified Twitch + YouTube Bot
Optimierter Starter für gleichzeitigen Betrieb beider Plattformen
"""
import os
import sys
import time
import signal
import threading
import traceback
import subprocess
import socket
import re
from datetime import datetime
from dotenv import load_dotenv

# Lade Umgebungsvariablen
load_dotenv()

# Lokale Imports
try:
    from enhanced_message_dispatcher import EnhancedMessageDispatcher, get_dispatcher
    from youtube_chat_reader import YouTubeChatReader
except ImportError as e:
    print(f"❌ Import-Fehler: {e}")
    print("Stelle sicher, dass enhanced_message_dispatcher.py und youtube_chat_reader.py existieren.")
    sys.exit(1)

# Basis-Konfiguration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PID_FILE = os.path.join(BASE_DIR, "zephyr_multi_bot.pid")

# Bot-Konfiguration
ENABLE_TWITCH = os.getenv("ENABLE_TWITCH", "true").lower() == "true"
ENABLE_YOUTUBE = os.getenv("ENABLE_YOUTUBE", "true").lower() == "true"
ENABLE_VISION = os.getenv("ENABLE_VISION", "true").lower() == "true"

class ZephyrMultiBot:
    def __init__(self):
        self.running = False
        self.components = {}
        self.threads = []
        
        # Initialisiere Enhanced Dispatcher
        self.dispatcher = get_dispatcher()
        
        self.log("🤖 Zephyr Multi-Platform Bot v2.0 initialisiert")
    
    def log(self, message, level="INFO"):
        """Zentrale Logging-Funktion"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if level == "SUCCESS":
            print(f"✅ [{timestamp}] {message}")
        elif level == "WARNING":
            print(f"⚠️  [{timestamp}] {message}")
        elif level == "ERROR":
            print(f"❌ [{timestamp}] {message}")
        else:
            print(f"ℹ️  [{timestamp}] {message}")
    
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
                self.log(f"Ollama-Server erreichbar: {version_info.get('version', 'unbekannt')}", "SUCCESS")
            else:
                missing_deps.append("Ollama-Server nicht erreichbar")
        except Exception as e:
            missing_deps.append(f"Ollama-Server: {str(e)}")
        
        # Prüfe Twitch-Konfiguration
        if ENABLE_TWITCH:
            twitch_config = ["BOT_USERNAME", "OAUTH_TOKEN", "CHANNEL"]
            missing_twitch = [c for c in twitch_config if not os.getenv(c)]
            if missing_twitch:
                missing_deps.extend([f"Twitch: {c}" for c in missing_twitch])
            else:
                self.log("Twitch-Konfiguration OK", "SUCCESS")
        
        # Prüfe YouTube-Konfiguration
        if ENABLE_YOUTUBE:
            youtube_config = ["YOUTUBE_API_KEY", "YOUTUBE_CHANNEL_ID"]
            missing_youtube = [c for c in youtube_config if not os.getenv(c)]
            if missing_youtube:
                missing_deps.extend([f"YouTube: {c}" for c in missing_youtube])
            else:
                self.log("YouTube-Konfiguration OK", "SUCCESS")
        
        # Prüfe Screenshots-Verzeichnis
        if ENABLE_VISION:
            screenshots_dir = os.path.join(BASE_DIR, "screenshots")
            if not os.path.exists(screenshots_dir):
                os.makedirs(screenshots_dir, exist_ok=True)
                self.log(f"Screenshots-Verzeichnis erstellt: {screenshots_dir}")
        
        if missing_deps:
            self.log("❌ Fehlende Abhängigkeiten:", "ERROR")
            for dep in missing_deps:
                self.log(f"   - {dep}", "ERROR")
            return False
        
        self.log("Alle Abhängigkeiten erfüllt", "SUCCESS")
        return True
    
    def start_twitch_component(self):
        """Startet die Twitch-Komponente als integrierten IRC-Client"""
        if not ENABLE_TWITCH:
            self.log("Twitch-Integration deaktiviert")
            return None
        
        try:
            self.log("Starte Twitch-Komponente...")
            
            # Erstelle einen einfachen Twitch-Adapter
            twitch_adapter = SimpleTwitchAdapter(self.dispatcher)
            
            if twitch_adapter.start():
                self.components["twitch"] = twitch_adapter
                self.log("Twitch-Komponente erfolgreich gestartet", "SUCCESS")
                return twitch_adapter
            else:
                self.log("Fehler beim Starten der Twitch-Komponente", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"Exception beim Starten der Twitch-Komponente: {e}", "ERROR")
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
                self.log("YouTube-Komponente erfolgreich gestartet", "SUCCESS")
                return youtube_reader
            else:
                self.log("Fehler beim Starten der YouTube-Komponente", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"Exception beim Starten der YouTube-Komponente: {e}", "ERROR")
            return None
    
    def start_vision_component(self):
        """Startet die Bildanalyse-Komponente"""
        if not ENABLE_VISION:
            self.log("Bildanalyse deaktiviert")
            return None
        
        try:
            self.log("Starte Bildanalyse-Komponente...")
            
            # Vision ist bereits im Enhanced Dispatcher integriert
            self.log("Bildanalyse-Komponente läuft im Dispatcher", "SUCCESS")
            return True
                
        except Exception as e:
            self.log(f"Exception beim Starten der Bildanalyse: {e}", "ERROR")
            return None
    
    def monitor_components(self):
        """Überwacht alle Komponenten"""
        while self.running:
            try:
                # Prüfe Status aller Komponenten
                for name, component in list(self.components.items()):
                    if hasattr(component, 'running') and not component.running:
                        self.log(f"Komponente {name} nicht mehr aktiv", "WARNING")
                        
                        # Neustart-Logik könnte hier implementiert werden
                        # Momentan nur logging
                
                time.sleep(30)  # Prüfe alle 30 Sekunden
                
            except Exception as e:
                self.log(f"Fehler beim Überwachen: {e}", "ERROR")
                time.sleep(10)
    
    def print_status(self):
        """Gibt den aktuellen Status aus"""
        print("\n" + "="*50)
        print("🤖 ZEPHYR MULTI-PLATFORM BOT STATUS")
        print("="*50)
        
        # Komponenten-Status
        print(f"🎮 Twitch:  {'✅ Aktiv' if 'twitch' in self.components else '❌ Inaktiv'}")
        print(f"🎥 YouTube: {'✅ Aktiv' if 'youtube' in self.components else '❌ Inaktiv'}")
        print(f"👁️  Vision:  {'✅ Aktiv' if ENABLE_VISION else '❌ Inaktiv'}")
        
        # Dispatcher-Statistiken
        if self.dispatcher:
            stats = self.dispatcher.stats
            uptime = int(time.time() - stats["start_time"])
            hours = uptime // 3600
            minutes = (uptime % 3600) // 60
            
            print(f"\n📊 STATISTIKEN:")
            print(f"   Nachrichten: {stats['total_messages']} (Twitch: {stats['twitch_messages']}, YouTube: {stats['youtube_messages']})")
            print(f"   Verarbeitet: {stats['processed_messages']}")
            print(f"   Bildanalysen: {stats['vision_updates']}")
            print(f"   Uptime: {hours}h {minutes}m")
        
        print("="*50 + "\n")
    
    def start(self):
        """Startet den Multi-Platform Bot"""
        self.log("🚀 Starte Zephyr Multi-Platform Bot...")
        
        # Prüfe Abhängigkeiten
        if not self.check_dependencies():
            self.log("Abhängigkeiten nicht erfüllt, beende Bot", "ERROR")
            return False
        
        # Setup
        self.create_pid_file()
        self.setup_signal_handlers()
        self.running = True
        
        # Starte Enhanced Dispatcher
        self.dispatcher.start()
        self.log("Enhanced Message Dispatcher gestartet", "SUCCESS")
        
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
        time.sleep(3)
        self.print_status()
        
        return True
    
    def stop(self):
        """Stoppt den Multi-Platform Bot"""
        if not self.running:
            return
        
        self.log("🛑 Stoppe Zephyr Multi-Platform Bot...")
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
            self.log("Enhanced Dispatcher gestoppt")
        
        # Warte auf Threads
        for thread in self.threads:
            try:
                thread.join(timeout=5)
            except:
                pass
        
        # Entferne PID-Datei
        self.remove_pid_file()
        
        self.log("🏁 Multi-Platform Bot gestoppt", "SUCCESS")
    
    def run(self):
        """Hauptlaufschleife"""
        if not self.start():
            return
        
        try:
            self.log("🎯 Bot läuft! (Ctrl+C zum Beenden)")
            
            # Status-Updates alle 10 Minuten
            last_status = time.time()
            
            while self.running:
                current_time = time.time()
                
                # Status-Update
                if current_time - last_status > 600:  # 10 Minuten
                    self.print_status()
                    last_status = current_time
                
                time.sleep(5)
                
        except KeyboardInterrupt:
            self.log("Beendet durch Benutzer")
        except Exception as e:
            self.log(f"Unerwarteter Fehler: {e}", "ERROR")
        finally:
            self.stop()

class SimpleTwitchAdapter:
    """Vereinfachter Twitch-Adapter für IRC-Integration"""
    
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.running = False
        self.irc_thread = None
        self.sock = None
        
        # Twitch-Konfiguration
        self.server = "irc.chat.twitch.tv"
        self.port = 6667
        self.nickname = os.getenv("BOT_USERNAME", "")
        self.token = os.getenv("OAUTH_TOKEN", "")
        self.channel = os.getenv("CHANNEL", "")
        self.bot_name = os.getenv("BOT_NAME", "zephyr")
    
    def start(self):
        """Startet den Twitch-Adapter"""
        try:
            # Registriere Sender beim Dispatcher
            self.dispatcher.register_sender("twitch", self.send_message)
            
            # Starte IRC-Thread
            self.running = True
            self.irc_thread = threading.Thread(target=self.irc_worker)
            self.irc_thread.daemon = True
            self.irc_thread.start()
            
            return True
        except Exception as e:
            print(f"Fehler beim Starten des Twitch-Adapters: {e}")
            return False
    
    def irc_worker(self):
        """IRC-Worker Thread"""
        while self.running:
            try:
                # Verbinde zu Twitch IRC
                self.sock = socket.socket()
                self.sock.settimeout(10)
                self.sock.connect((self.server, self.port))
                
                # Authentifizierung
                self.sock.send(f"PASS {self.token}\r\n".encode('utf-8'))
                self.sock.send(f"NICK {self.nickname}\r\n".encode('utf-8'))
                self.sock.send(f"JOIN {self.channel}\r\n".encode('utf-8'))
                
                print(f"✅ Twitch IRC verbunden: {self.channel}")
                
                # Nachrichtenschleife
                while self.running:
                    try:
                        response = self.sock.recv(2048).decode('utf-8')
                        
                        for line in response.split('\r\n'):
                            if not line:
                                continue
                            
                            # PING/PONG
                            if line.startswith("PING"):
                                self.sock.send(f"PONG{line[4:]}\r\n".encode('utf-8'))
                                continue
                            
                            # Chat-Nachrichten
                            if "PRIVMSG" in line:
                                try:
                                    # Einfache Regex für Username
                                    match = re.search(r':([^!]+)!', line)
                                    if match:
                                        username = match.group(1)
                                        
                                        # Nachrichteninhalt
                                        message_content = line.split("PRIVMSG", 1)[1].split(":", 1)[1]
                                        
                                        # An Dispatcher weiterleiten
                                        if username.lower() != self.bot_name.lower():
                                            self.dispatcher.add_message("twitch", username, message_content)
                                            
                                except Exception as e:
                                    print(f"Fehler beim Parsen der Twitch-Nachricht: {e}")
                    
                    except socket.timeout:
                        continue
                    except Exception as e:
                        print(f"Fehler im Twitch IRC: {e}")
                        break
                        
            except Exception as e:
                print(f"Twitch IRC Verbindungsfehler: {e}")
                time.sleep(30)  # Warte vor Neuverbindung
    
    def send_message(self, message):
        """Sendet eine Nachricht über Twitch IRC"""
        try:
            if self.sock and self.running:
                self.sock.send(f"PRIVMSG {self.channel} :{message}\r\n".encode('utf-8'))
                return True
        except Exception as e:
            print(f"Fehler beim Senden der Twitch-Nachricht: {e}")
        return False
    
    def stop(self):
        """Stoppt den Twitch-Adapter"""
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass

def main():
    """Hauptfunktion"""
    print("🤖 Zephyr Multi-Platform Bot v2.0")
    print("=" * 40)
    print("🎮 Twitch + 🎥 YouTube + 👁️ Vision AI")
    print("=" * 40)
    
    bot = ZephyrMultiBot()
    bot.run()

if __name__ == "__main__":
    main()

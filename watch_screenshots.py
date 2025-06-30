# Datei: watch_screenshots.py
#!/usr/bin/env python3
import time
import os
import sys
import tempfile
import hashlib
from datetime import datetime
from analyze_and_respond import analyze_and_comment

# Dynamische Pfadbestimmung
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if not os.path.exists(BASE_DIR):
    BASE_DIR = os.path.expanduser("~/zephyr")

SCREENSHOT_DIR = os.path.join(BASE_DIR, "screenshots")
SEEN_FILES_CACHE = os.path.join(tempfile.gettempdir(), "zephyr_seen_files.txt")
MAX_CACHE_SIZE = 1000  # Maximale Anzahl von Dateien im Cache
MAX_SCREENSHOTS = 100  # NEU: Max. 100 Dateien behalten

def send_message_to_platforms(message, exclude_platform=None):
    """Sendet eine Nachricht an alle verfügbaren Plattformen - ERWEITERT mit Message Dispatcher"""
    success = False
    
    # PRIORITÄT 1: Versuche Message Dispatcher
    try:
        from message_dispatcher import queue_message
        queue_message("vision", "Screenshot-Watcher", message)
        print(f"✅ [DISPATCHER] Bildkommentar an Message Queue weitergeleitet: {message[:50]}...")
        return True
    except ImportError:
        print("⚠️ Message Dispatcher nicht verfügbar, verwende Fallback...")
    except Exception as e:
        print(f"❌ Fehler bei Message Dispatcher: {e}")
    
    # PRIORITÄT 2: Versuche Import der Multi-Platform-Bot-Funktionen
    try:
        sys.path.append(BASE_DIR)
        from multi_platform_bot import send_message_to_platforms as bot_send_platforms
        return bot_send_platforms(message, exclude_platform)
    except ImportError:
        print("⚠️ Multi-Platform-Bot Funktionen nicht verfügbar...")
    except Exception as e:
        print(f"❌ Fehler bei Multi-Platform-Bot: {e}")
    
    # PRIORITÄT 3: Fallback: Versuche alte Twitch-Bot-Funktion
    try:
        from twitch_ollama_bot import send_message as twitch_send_message
        return twitch_send_message(message)
    except ImportError:
        print("⚠️ Twitch-Bot nicht verfügbar...")
    except Exception as e:
        print(f"❌ Fehler bei Twitch-Bot: {e}")
    
    # PRIORITÄT 4: Letzter Fallback: Nur ausgeben
    platform_prefix = "📸 [AUTO] " if not exclude_platform else f"📸 [{exclude_platform.upper()}] "
    print(f"⚠ Konnte Nachricht nicht senden - Ausgabe: {platform_prefix}{message}")
    return False

def load_seen_files():
    seen_files = set()
    try:
        if os.path.exists(SEEN_FILES_CACHE):
            with open(SEEN_FILES_CACHE, 'r') as f:
                for line in f:
                    seen_files.add(line.strip())
    except Exception as e:
        print(f"⚠ Fehler beim Laden des Cache: {e}")
    return seen_files

def save_seen_files(seen_files):
    try:
        with open(SEEN_FILES_CACHE, 'w') as f:
            for file_hash in list(seen_files)[-MAX_CACHE_SIZE:]:
                f.write(f"{file_hash}\n")
    except Exception as e:
        print(f"⚠ Fehler beim Speichern des Cache: {e}")

def get_file_hash(file_path):
    try:
        mtime = os.path.getmtime(file_path)
        file_size = os.path.getsize(file_path)
        hash_str = f"{file_path}_{mtime}_{file_size}"
        return hashlib.md5(hash_str.encode()).hexdigest()
    except Exception as e:
        print(f"⚠ Fehler beim Hash-Erstellen für {file_path}: {e}")
        return hashlib.md5(file_path.encode()).hexdigest()

def cleanup_screenshot_dir(max_files=MAX_SCREENSHOTS):
    try:
        files = [os.path.join(SCREENSHOT_DIR, f)
                 for f in os.listdir(SCREENSHOT_DIR)
                 if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

        if len(files) <= max_files:
            return

        files.sort(key=os.path.getmtime)
        files_to_delete = files[:-max_files]

        for f in files_to_delete:
            try:
                os.remove(f)
                print(f"🗑️ Alte Datei gelöscht: {os.path.basename(f)}")
            except Exception as e:
                print(f"⚠ Fehler beim Löschen {f}: {e}")
    except Exception as e:
        print(f"⚠ Fehler beim Bereinigen: {e}")

def handle_new_file(file_path):
    """ERWEITERTE Funktion für neue Dateien mit Message Dispatcher Integration"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] 📸 Neues Bild erkannt: {file_path}")
    
    try:
        # Analysiere das Bild ohne Platform-Hint (für alle Plattformen)
        result = analyze_and_comment(file_path)
        if result:
            # Die analyze_and_comment Funktion sendet bereits über den Message Dispatcher
            # Falls sie das nicht kann, hat sie bereits Fallback-Methoden verwendet
            print(f"[{timestamp}] ✅ Bildanalyse und Weiterleitung erfolgreich")
            return True
        else:
            print(f"[{timestamp}] ⚠ Analyse oder Antwort fehlgeschlagen.")
            
            # Fallback: Direkte Sendung einer Standard-Nachricht
            fallback_message = "📸 Neuer Screenshot erkannt, aber Analyse fehlgeschlagen."
            success = send_message_to_platforms(fallback_message)
            return success
            
    except Exception as e:
        print(f"[{timestamp}] ❌ Fehler bei Bildverarbeitung: {e}")
        
        # Fallback: Sende Fehlermeldung
        try:
            error_message = "📸 Screenshot erkannt, aber Verarbeitung fehlgeschlagen."
            send_message_to_platforms(error_message)
        except:
            pass
    
    return False

def main():
    """ERWEITERTE Hauptfunktion mit Message Dispatcher Integration"""
    print(f"👁 Multi-Platform Screenshot-Watcher startet - Überwache: {SCREENSHOT_DIR}")
    print("🔗 Integriert mit Message Dispatcher für optimale Multi-Platform-Unterstützung")
    
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        print(f"📁 Verzeichnis erstellt: {SCREENSHOT_DIR}")
    
    seen_files = load_seen_files()
    print(f"🔄 {len(seen_files)} bereits gesehene Dateien geladen.")
    
    last_save_time = time.time()
    
    # Test der Message Dispatcher Verbindung
    try:
        from message_dispatcher import get_dispatcher_stats
        stats = get_dispatcher_stats()
        print(f"📊 Message Dispatcher Status: {len(stats.get('platforms_registered', []))} Plattformen registriert")
    except ImportError:
        print("⚠️ Message Dispatcher nicht geladen - verwende Fallback-Methoden")
    
    try:
        while True:
            current_time = time.time()
            
            # Speichere Cache regelmäßig
            if current_time - last_save_time > 300:  # Alle 5 Minuten
                save_seen_files(seen_files)
                last_save_time = current_time
            
            try:
                # Prüfe die letzten 10 Dateien für neue Screenshots
                files = sorted([f for f in os.listdir(SCREENSHOT_DIR) 
                                if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
                
                for f in files[-10:]:  # Nur die neuesten 10 Dateien prüfen
                    full_path = os.path.join(SCREENSHOT_DIR, f)
                    file_hash = get_file_hash(full_path)
                    
                    if file_hash not in seen_files:
                        seen_files.add(file_hash)
                        
                        # Verarbeite neues Bild
                        if handle_new_file(full_path):
                            cleanup_screenshot_dir()  # Auto-Cleanup direkt danach
                            save_seen_files(seen_files)  # Speichere nach erfolgreicher Verarbeitung
                
            except Exception as e:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{timestamp}] ❌ Fehler beim Durchsuchen des Verzeichnisses: {e}")
            
            # Warte 3 Sekunden vor nächster Prüfung
            time.sleep(3)
            
    except KeyboardInterrupt:
        print("\n⛔ Beendet durch Benutzer.")
    except Exception as e:
        print(f"❌ Unerwarteter Fehler: {e}")
    finally:
        save_seen_files(seen_files)
        print("💾 Cache gespeichert. Multi-Platform Screenshot-Watcher wird beendet.")

if __name__ == "__main__":
    main()

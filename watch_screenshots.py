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

# Importiere twitch_ollama_bot.send_message erst wenn benötigt
# um Zirkelbezüge zu vermeiden
def send_message(message):
    try:
        # Dynamisches Importieren nur bei Bedarf
        sys.path.append(BASE_DIR)
        from twitch_ollama_bot import send_message as bot_send_message
        return bot_send_message(message)
    except ImportError:
        print(f"⚠️ Konnte send_message nicht importieren - Ausgabe: {message}")
        return False

def load_seen_files():
    """Lädt die Cache-Datei mit den bereits gesehenen Dateien"""
    seen_files = set()
    try:
        if os.path.exists(SEEN_FILES_CACHE):
            with open(SEEN_FILES_CACHE, 'r') as f:
                for line in f:
                    seen_files.add(line.strip())
    except Exception as e:
        print(f"⚠️ Fehler beim Laden des Cache: {e}")
    return seen_files

def save_seen_files(seen_files):
    """Speichert die gesehenen Dateien im Cache"""
    try:
        with open(SEEN_FILES_CACHE, 'w') as f:
            # Nehme nur die neuesten Einträge, um den Cache-Größe zu begrenzen
            for file_hash in list(seen_files)[-MAX_CACHE_SIZE:]:
                f.write(f"{file_hash}\n")
    except Exception as e:
        print(f"⚠️ Fehler beim Speichern des Cache: {e}")

def get_file_hash(file_path):
    """Erstellt einen Hash aus Dateipfad und Änderungszeit"""
    try:
        mtime = os.path.getmtime(file_path)
        file_size = os.path.getsize(file_path)
        hash_str = f"{file_path}_{mtime}_{file_size}"
        return hashlib.md5(hash_str.encode()).hexdigest()
    except Exception as e:
        print(f"⚠️ Fehler beim Hash-Erstellen für {file_path}: {e}")
        # Fallback: Nur Dateipfad
        return hashlib.md5(file_path.encode()).hexdigest()

def handle_new_file(file_path):
    """Verarbeitet eine neue Screenshot-Datei"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] 📸 Neues Bild erkannt: {file_path}")
    
    try:
        result = analyze_and_comment(file_path)
        if result:
            send_message(f"👁️ {result[:450]}")
            return True
        else:
            print(f"[{timestamp}] ⚠️ Analyse oder Antwort fehlgeschlagen.")
    except Exception as e:
        print(f"[{timestamp}] ❌ Fehler bei Bildverarbeitung: {e}")
    
    return False

def main():
    """Hauptfunktion, überwacht den Screenshot-Ordner"""
    print(f"👁️ Screenshot-Watcher startet - Überwache: {SCREENSHOT_DIR}")
    
    # Stelle sicher, dass das Verzeichnis existiert
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        print(f"📁 Verzeichnis erstellt: {SCREENSHOT_DIR}")
    
    # Lade den Cache mit bereits gesehenen Dateien
    seen_files = load_seen_files()
    print(f"🔄 {len(seen_files)} bereits gesehene Dateien geladen.")
    
    last_save_time = time.time()
    
    try:
        while True:
            current_time = time.time()
            
            # Speichere den Cache regelmäßig
            if current_time - last_save_time > 300:  # Alle 5 Minuten
                save_seen_files(seen_files)
                last_save_time = current_time
            
            try:
                files = sorted([f for f in os.listdir(SCREENSHOT_DIR) 
                              if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
                
                # Verarbeite nur die neuesten 10 Dateien, falls es viele gibt
                for f in files[-10:]:
                    full_path = os.path.join(SCREENSHOT_DIR, f)
                    file_hash = get_file_hash(full_path)
                    
                    if file_hash not in seen_files:
                        seen_files.add(file_hash)
                        handle_new_file(full_path)
                        # Speichere nach jeder neuen Datei
                        save_seen_files(seen_files)
                
            except Exception as e:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{timestamp}] ❌ Fehler beim Durchsuchen des Verzeichnisses: {e}")
            
            # Kurze Pause
            time.sleep(3)
            
    except KeyboardInterrupt:
        print("\n⛔ Beendet durch Benutzer.")
    except Exception as e:
        print(f"❌ Unerwarteter Fehler: {e}")
    finally:
        # Speichere den Cache beim Beenden
        save_seen_files(seen_files)
        print("💾 Cache gespeichert. Programm wird beendet.")

if __name__ == "__main__":
    main()

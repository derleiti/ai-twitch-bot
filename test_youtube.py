#!/usr/bin/env python3
"""
YouTube Chat Reader Test-Skript

Dieses Skript testet die YouTube-API-Verbindung und kann verwendet werden,
um die Konfiguration zu überprüfen, bevor der Bot gestartet wird.
"""

import os
import sys
import time
from dotenv import load_dotenv

# Lade Umgebungsvariablen
load_dotenv()

def main():
    print("🔴 YouTube Chat Reader - Konfigurationstest")
    print("=" * 50)
    
    # Prüfe Umgebungsvariablen
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    channel_id = os.getenv("YOUTUBE_CHANNEL_ID", "")
    
    print(f"📋 Konfiguration:")
    print(f"   YouTube API Key: {'✅ Gesetzt' if api_key else '❌ Nicht gesetzt'}")
    print(f"   YouTube Channel ID: {'✅ Gesetzt' if channel_id else '❌ Nicht gesetzt'}")
    
    if not api_key:
        print("\n❌ YouTube API Key fehlt!")
        print("   Setze YOUTUBE_API_KEY in der .env-Datei")
        print("   API Key erstellen: https://console.developers.google.com/")
        return False
    
    if not channel_id:
        print("\n❌ YouTube Channel ID fehlt!")
        print("   Setze YOUTUBE_CHANNEL_ID in der .env-Datei")
        print("   Channel ID finden: https://commentpicker.com/youtube-channel-id.php")
        return False
    
    # Importiere YouTube Reader
    try:
        from youtube_chat_reader import test_youtube_connection, get_status
        print("\n📦 YouTube Chat Reader-Modul erfolgreich importiert")
    except ImportError as e:
        print(f"\n❌ Fehler beim Importieren des YouTube Chat Readers: {e}")
        return False
    
    # Teste API-Verbindung
    print("\n🔍 Teste YouTube API-Verbindung...")
    
    try:
        if test_youtube_connection():
            print("✅ YouTube-Verbindung erfolgreich!")
            print("   API-Key ist gültig")
            print("   Live-Stream wurde gefunden")
            print("   Live-Chat ist verfügbar")
            return True
        else:
            print("⚠️ YouTube-Verbindungstest nicht erfolgreich")
            print("   Mögliche Ursachen:")
            print("   - Kein aktiver Live-Stream auf dem Kanal")
            print("   - Live-Chat ist deaktiviert")
            print("   - API-Key hat nicht die nötigen Berechtigungen")
            print("   - Channel-ID ist falsch")
            
            # Zusätzliche Diagnose
            print("\n🔧 Erweiterte Diagnose...")
            try:
                import requests
                
                # Teste API-Key direkt
                print("   📡 Teste API-Key...")
                response = requests.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    params={
                        'part': 'id',
                        'mine': 'true',
                        'key': api_key
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    print("   ✅ API-Key ist gültig")
                elif response.status_code == 403:
                    print("   ❌ API-Key ungültig oder Quota überschritten")
                else:
                    print(f"   ⚠️ API-Anfrage fehlgeschlagen: HTTP {response.status_code}")
                
                # Teste Channel-ID
                print("   📺 Teste Channel-ID...")
                response = requests.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    params={
                        'part': 'snippet',
                        'id': channel_id,
                        'key': api_key
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    if items:
                        channel_name = items[0]['snippet']['title']
                        print(f"   ✅ Channel gefunden: {channel_name}")
                    else:
                        print("   ❌ Channel mit dieser ID nicht gefunden")
                else:
                    print(f"   ⚠️ Channel-Anfrage fehlgeschlagen: HTTP {response.status_code}")
                
                # Suche nach Live-Streams
                print("   📡 Suche nach Live-Streams...")
                response = requests.get(
                    "https://www.googleapis.com/youtube/v3/search",
                    params={
                        'part': 'id,snippet',
                        'channelId': channel_id,
                        'eventType': 'live',
                        'type': 'video',
                        'key': api_key,
                        'maxResults': 5
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    if items:
                        print(f"   ✅ {len(items)} Live-Stream(s) gefunden:")
                        for item in items:
                            title = item['snippet']['title']
                            video_id = item['id']['videoId']
                            print(f"      📺 {title} (ID: {video_id})")
                    else:
                        print("   ⚠️ Keine aktiven Live-Streams gefunden")
                        print("      Der Bot funktioniert nur, wenn ein Live-Stream aktiv ist")
                else:
                    print(f"   ❌ Live-Stream-Suche fehlgeschlagen: HTTP {response.status_code}")
                
            except Exception as e:
                print(f"   ❌ Fehler bei der Diagnose: {e}")
            
            return False
            
    except Exception as e:
        print(f"❌ Fehler beim Testen der YouTube-Verbindung: {e}")
        return False

def interactive_test():
    """Interaktiver Test-Modus"""
    print("\n🎮 Interaktiver Test-Modus")
    print("Drücke Ctrl+C zum Beenden")
    
    try:
        from youtube_chat_reader import start_youtube_chat_reader, stop_youtube_chat_reader, get_status
        
        message_count = 0
        
        def test_callback(user, message, platform):
            nonlocal message_count
            message_count += 1
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] 🔴 {user}: {message}")
        
        print("🚀 Starte YouTube Chat Reader...")
        start_youtube_chat_reader(test_callback)
        
        last_status_time = 0
        
        while True:
            current_time = time.time()
            
            # Status alle 30 Sekunden ausgeben
            if current_time - last_status_time > 30:
                status = get_status()
                print(f"\n📊 Status: Running={status['running']}, Active={status['active']}, Nachrichten={message_count}")
                last_status_time = current_time
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n⛔ Test beendet durch Benutzer")
        try:
            stop_youtube_chat_reader()
        except:
            pass
    except Exception as e:
        print(f"\n❌ Fehler im interaktiven Test: {e}")

if __name__ == "__main__":
    print("YouTube Chat Test-Skript")
    
    # Grundtest durchführen
    success = main()
    
    if success:
        print("\n🎉 Alle Tests erfolgreich!")
        
        # Frage nach interaktivem Test
        try:
            response = input("\n❓ Möchtest du den interaktiven Chat-Test starten? (j/n): ")
            if response.lower() in ['j', 'ja', 'y', 'yes']:
                interactive_test()
        except (KeyboardInterrupt, EOFError):
            print("\nTest beendet.")
    else:
        print("\n❌ Tests fehlgeschlagen. Bitte Konfiguration überprüfen.")
        sys.exit(1)

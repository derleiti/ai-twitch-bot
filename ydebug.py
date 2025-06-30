#!/usr/bin/env python3
"""
YouTube Debug & Diagnose Skript

Umfassendes Diagnoseskript für YouTube API-Probleme.
Führt detaillierte Tests durch und gibt spezifische Lösungsvorschläge.
"""

import os
import sys
import time
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

# Lade Umgebungsvariablen
load_dotenv()

def print_header(title):
    """Druckt einen formatierten Header"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")

def print_step(step_num, description):
    """Druckt einen formatierten Schritt"""
    print(f"\n[{step_num}] {description}")
    print("-" * 50)

def test_environment():
    """Testet die Umgebungsvariablen"""
    print_step(1, "Umgebungsvariablen prüfen")
    
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    channel_id = os.getenv("YOUTUBE_CHANNEL_ID", "")
    debug_level = os.getenv("DEBUG_LEVEL", "1")
    
    print(f"✓ YOUTUBE_API_KEY: {'Gesetzt' if api_key else '❌ FEHLT'}")
    if api_key:
        print(f"  Länge: {len(api_key)} Zeichen")
        print(f"  Beginnt mit: {api_key[:10]}...")
    
    print(f"✓ YOUTUBE_CHANNEL_ID: {'Gesetzt' if channel_id else '❌ FEHLT'}")
    if channel_id:
        print(f"  Channel-ID: {channel_id}")
    
    print(f"✓ DEBUG_LEVEL: {debug_level}")
    
    missing = []
    if not api_key:
        missing.append("YOUTUBE_API_KEY")
    if not channel_id:
        missing.append("YOUTUBE_CHANNEL_ID")
    
    if missing:
        print(f"\n❌ Fehlende Variablen: {', '.join(missing)}")
        print("\n🔧 Lösungsschritte:")
        print("1. Erstelle/bearbeite die .env-Datei im Bot-Verzeichnis")
        print("2. Füge die fehlenden Variablen hinzu:")
        for var in missing:
            print(f"   {var}=dein_wert_hier")
        return False
    
    return True, api_key, channel_id

def test_basic_connectivity():
    """Testet die grundlegende Internet-Verbindung zu YouTube"""
    print_step(2, "Internet-Verbindung zu YouTube testen")
    
    try:
        print("Teste Verbindung zu YouTube API...")
        response = requests.get("https://www.googleapis.com/youtube/v3/", timeout=10)
        print(f"✓ YouTube API erreichbar (HTTP {response.status_code})")
        return True
    except requests.exceptions.ConnectionError:
        print("❌ Keine Verbindung zu YouTube API möglich")
        print("\n🔧 Mögliche Ursachen:")
        print("- Keine Internetverbindung")
        print("- Firewall blockiert Zugriff")
        print("- DNS-Probleme")
        return False
    except Exception as e:
        print(f"❌ Verbindungsfehler: {e}")
        return False

def test_api_key(api_key, channel_id):
    """Testet den YouTube API-Key ausführlich"""
    print_step(3, "YouTube API-Key validieren")
    
    # Test 1: Einfacher API-Key Test
    print("Test 1: API-Key Grundvalidierung...")
    try:
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {
            'part': 'id,snippet',
            'id': channel_id,
            'key': api_key
        }
        
        response = requests.get(url, params=params, timeout=15)
        print(f"HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('items'):
                channel = data['items'][0]
                channel_name = channel['snippet']['title']
                print(f"✓ API-Key ist gültig")
                print(f"✓ Kanal gefunden: {channel_name}")
                return True
            else:
                print("❌ Channel-ID nicht gefunden")
                print("\n🔧 Lösungsschritte:")
                print("1. Überprüfe die YOUTUBE_CHANNEL_ID")
                print("2. Finde deine Channel-ID: https://commentpicker.com/youtube-channel-id.php")
                return False
        
        elif response.status_code == 400:
            print("❌ Ungültige Anfrage")
            error_data = response.json()
            print(f"Fehlerdetails: {json.dumps(error_data, indent=2)}")
            return False
            
        elif response.status_code == 403:
            print("❌ API-Zugriff verweigert")
            try:
                error_data = response.json()
                error_info = error_data.get('error', {})
                error_reason = error_info.get('errors', [{}])[0].get('reason', 'unknown')
                
                print(f"Fehlergrund: {error_reason}")
                
                if error_reason == 'keyInvalid':
                    print("\n🔧 Lösungsschritte:")
                    print("1. API-Key ist ungültig oder falsch formatiert")
                    print("2. Erstelle einen neuen API-Key:")
                    print("   - Gehe zu: https://console.developers.google.com/")
                    print("   - Wähle/erstelle ein Projekt")
                    print("   - Aktiviere YouTube Data API v3")
                    print("   - Erstelle Anmeldedaten (API-Key)")
                    
                elif error_reason == 'quotaExceeded':
                    print("\n🔧 Lösungsschritte:")
                    print("1. YouTube API-Quota für heute aufgebraucht")
                    print("2. Warte bis morgen oder erhöhe das Quota")
                    print("3. Überprüfe Quota: https://console.developers.google.com/")
                    
                elif error_reason == 'accessNotConfigured':
                    print("\n🔧 Lösungsschritte:")
                    print("1. YouTube Data API v3 nicht aktiviert")
                    print("2. Aktiviere die API in der Google Cloud Console")
                    
                else:
                    print(f"\n🔧 Unbekannter Fehler: {error_reason}")
                    print("Überprüfe die Google Cloud Console")
                
            except:
                print("Konnte Fehlerdetails nicht parsen")
            
            return False
            
        else:
            print(f"❌ Unerwarteter HTTP-Status: {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ Fehler beim API-Test: {e}")
        return False

def test_live_streams(api_key, channel_id):
    """Testet die Live-Stream-Erkennung"""
    print_step(4, "Live-Stream-Erkennung testen")
    
    try:
        url = "https://www.googleapis.com/youtube/v3/search"
        
        # Test für aktive Live-Streams
        print("Suche nach aktiven Live-Streams...")
        params = {
            'part': 'id,snippet',
            'channelId': channel_id,
            'eventType': 'live',
            'type': 'video',
            'key': api_key,
            'maxResults': 5
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            live_streams = data.get('items', [])
            
            print(f"✓ Gefunden: {len(live_streams)} aktive Live-Stream(s)")
            
            if live_streams:
                for i, stream in enumerate(live_streams, 1):
                    title = stream['snippet']['title']
                    video_id = stream['id']['videoId']
                    print(f"  {i}. {title} (ID: {video_id})")
                
                # Teste Live-Chat für ersten Stream
                test_live_chat(api_key, live_streams[0]['id']['videoId'])
                
            else:
                print("ℹ Keine aktiven Live-Streams gefunden")
                
                # Suche nach geplanten Streams
                print("\nSuche nach geplanten Live-Streams...")
                params['eventType'] = 'upcoming'
                upcoming_response = requests.get(url, params=params, timeout=15)
                
                if upcoming_response.status_code == 200:
                    upcoming_data = upcoming_response.json()
                    upcoming_streams = upcoming_data.get('items', [])
                    
                    print(f"✓ Gefunden: {len(upcoming_streams)} geplante Live-Stream(s)")
                    
                    for i, stream in enumerate(upcoming_streams, 1):
                        title = stream['snippet']['title']
                        scheduled_time = stream['snippet'].get('scheduledStartTime', 'Unbekannt')
                        print(f"  {i}. {title} (geplant für: {scheduled_time})")
                
                print("\n💡 Hinweis:")
                print("Der Bot funktioniert nur, wenn ein Live-Stream aktiv ist.")
                print("Starte einen Live-Stream und teste erneut.")
            
            return len(live_streams) > 0
            
        else:
            print(f"❌ Fehler beim Suchen der Live-Streams: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Fehler beim Live-Stream-Test: {e}")
        return False

def test_live_chat(api_key, video_id):
    """Testet den Live-Chat für ein Video"""
    print(f"\nTeste Live-Chat für Video {video_id}...")
    
    try:
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            'part': 'liveStreamingDetails,snippet',
            'id': video_id,
            'key': api_key
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            
            if items:
                video = items[0]
                video_title = video.get('snippet', {}).get('title', 'Unbekannt')
                
                if 'liveStreamingDetails' in video:
                    live_details = video['liveStreamingDetails']
                    chat_id = live_details.get('activeLiveChatId')
                    
                    if chat_id:
                        print(f"✓ Live-Chat verfügbar für '{video_title}'")
                        print(f"  Chat-ID: {chat_id}")
                        
                        # Teste Chat-Nachrichten
                        test_chat_messages(api_key, chat_id)
                        return True
                    else:
                        print(f"⚠ Live-Chat nicht verfügbar für '{video_title}'")
                        print("Mögliche Gründe:")
                        print("- Chat ist deaktiviert")
                        print("- Stream ist nicht live")
                        print("- Chat-Berechtigung fehlt")
                        return False
                else:
                    print(f"⚠ '{video_title}' hat keine Live-Streaming-Details")
                    return False
            else:
                print("❌ Video nicht gefunden")
                return False
        else:
            print(f"❌ Fehler beim Live-Chat-Test: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Fehler beim Live-Chat-Test: {e}")
        return False

def test_chat_messages(api_key, chat_id):
    """Testet das Abrufen von Chat-Nachrichten"""
    print(f"Teste Chat-Nachrichten-Abruf...")
    
    try:
        url = "https://www.googleapis.com/youtube/v3/liveChat/messages"
        params = {
            'liveChatId': chat_id,
            'part': 'id,snippet,authorDetails',
            'key': api_key,
            'maxResults': 10
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            messages = data.get('items', [])
            
            print(f"✓ Chat-API funktioniert - {len(messages)} Nachrichten abgerufen")
            
            if messages:
                print("Beispiel-Nachrichten:")
                for i, msg in enumerate(messages[:3], 1):
                    author = msg['authorDetails']['displayName']
                    text = msg['snippet']['displayMessage']
                    print(f"  {i}. {author}: {text[:50]}...")
            
            poll_interval = data.get('pollingIntervalMillis', 5000) / 1000
            print(f"Empfohlenes Polling-Intervall: {poll_interval}s")
            
            return True
        else:
            print(f"❌ Chat-Nachrichten-Test fehlgeschlagen: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Fehler beim Chat-Nachrichten-Test: {e}")
        return False

def comprehensive_test():
    """Führt alle Tests durch"""
    print_header("YouTube API Comprehensive Test")
    print(f"Test gestartet: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test 1: Umgebung
    env_result = test_environment()
    if not env_result:
        return False
    
    _, api_key, channel_id = env_result
    
    # Test 2: Konnektivität
    if not test_basic_connectivity():
        return False
    
    # Test 3: API-Key
    if not test_api_key(api_key, channel_id):
        return False
    
    # Test 4: Live-Streams
    live_stream_result = test_live_streams(api_key, channel_id)
    
    print_header("Test-Zusammenfassung")
    
    if live_stream_result:
        print("🎉 ALLE TESTS ERFOLGREICH!")
        print("✓ YouTube-Integration ist vollständig funktionsfähig")
        print("✓ Bot kann Chat-Nachrichten empfangen")
    else:
        print("⚠ TESTS TEILWEISE ERFOLGREICH")
        print("✓ API-Konfiguration ist korrekt")
        print("⚠ Kein aktiver Live-Stream für Chat-Test")
        print("💡 Starte einen Live-Stream für vollständige Funktionalität")
    
    print("\nNächste Schritte:")
    print("1. Starte den Multi-Platform-Bot")
    print("2. Beginne einen Live-Stream auf YouTube")
    print("3. Aktiviere den Live-Chat")
    print("4. Der Bot sollte automatisch Chat-Nachrichten empfangen")
    
    return True

def quick_fix_suggestions():
    """Gibt schnelle Lösungsvorschläge"""
    print_header("Schnelle Lösungsvorschläge")
    
    print("🔧 Häufige Probleme und Lösungen:")
    print("\n1. 'YouTube-Verbindungstest fehlgeschlagen'")
    print("   → Überprüfe YOUTUBE_API_KEY und YOUTUBE_CHANNEL_ID in .env")
    print("   → Teste mit diesem Skript: python3 youtube_debug.py")
    
    print("\n2. 'API-Key ungültig'")
    print("   → Erstelle neuen API-Key in Google Cloud Console")
    print("   → Aktiviere YouTube Data API v3")
    
    print("\n3. 'Kein Live-Stream gefunden'")
    print("   → Starte einen Live-Stream auf YouTube")
    print("   → Aktiviere den Live-Chat in den Stream-Einstellungen")
    
    print("\n4. 'Quota überschritten'")
    print("   → Warte bis morgen (Quota wird täglich zurückgesetzt)")
    print("   → Oder erhöhe das Quota in der Google Cloud Console")
    
    print("\n5. Bot empfängt keine Nachrichten")
    print("   → Setze DEBUG_LEVEL=2 in .env für detaillierte Logs")
    print("   → Überprüfe ob Live-Chat aktiviert ist")
    print("   → Schreibe Testnachrichten in den YouTube-Chat")

def main():
    """Hauptfunktion"""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--quick-fix":
            quick_fix_suggestions()
            return
        elif sys.argv[1] == "--test":
            comprehensive_test()
            return
    
    print("YouTube Debug & Diagnose Skript")
    print("\nOptionen:")
    print("  python3 youtube_debug.py --test       # Umfassender Test")
    print("  python3 youtube_debug.py --quick-fix  # Schnelle Lösungsvorschläge")
    print("  python3 youtube_debug.py              # Interaktiver Modus")
    
    choice = input("\nWas möchtest du tun? (test/quick-fix/exit): ").lower()
    
    if choice in ['test', 't']:
        comprehensive_test()
    elif choice in ['quick-fix', 'fix', 'f']:
        quick_fix_suggestions()
    else:
        print("Auf Wiedersehen!")

if __name__ == "__main__":
    main()

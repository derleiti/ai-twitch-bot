# Datei: youtube_chat_reader.py
#!/usr/bin/env python3
# youtube_chat_reader.py - YouTube Live Chat Reader für Zephyr Bot - COMPLETE FIX

import os
import time
import requests
import json
import threading
from datetime import datetime
from dotenv import load_dotenv

# Lade Umgebungsvariablen
load_dotenv()

# Konfiguration
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "")
YOUTUBE_POLL_INTERVAL = int(os.getenv("YOUTUBE_POLL_INTERVAL", "5"))  # Sekunden zwischen API-Aufrufen
YOUTUBE_MAX_RESULTS = int(os.getenv("YOUTUBE_MAX_RESULTS", "200"))   # Max. Nachrichten pro Aufruf
DEBUG_LEVEL = int(os.getenv("DEBUG_LEVEL", "1"))

# Erweiterte Konfiguration für besseres Error Handling
YOUTUBE_API_TIMEOUT = int(os.getenv("YOUTUBE_API_TIMEOUT", "15"))  # API-Timeout in Sekunden
YOUTUBE_RETRY_COUNT = int(os.getenv("YOUTUBE_RETRY_COUNT", "3"))   # Anzahl Wiederholungsversuche
YOUTUBE_BACKOFF_MULTIPLIER = int(os.getenv("YOUTUBE_BACKOFF_MULTIPLIER", "2"))  # Exponential backoff

# Status-Variablen
running = True
is_active = False
live_chat_id = None
next_page_token = None
known_message_ids = set()
last_api_call = 0
message_callback = None
last_error_time = 0
consecutive_errors = 0

# NEW: Message Dispatcher Integration
message_dispatcher_available = False
try:
    from message_dispatcher import queue_message, get_dispatcher_stats
    message_dispatcher_available = True
    print("✅ [YOUTUBE] Message Dispatcher verfügbar")
except ImportError:
    print("⚠️ [YOUTUBE] Message Dispatcher nicht verfügbar - verwende Callback")

# Logging mit verbesserter Ausgabe
def log(message, level=1):
    """Loggt eine Nachricht, wenn das Debug-Level ausreichend ist"""
    if level > DEBUG_LEVEL:
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[YouTube] [{timestamp}] {message}")

def log_error(message, exception=None, http_response=None):
    """Loggt eine Fehlermeldung mit erweiterten Details"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[YouTube] [{timestamp}] ERROR: {message}")
    
    if http_response:
        print(f"[YouTube] [{timestamp}] HTTP Status: {http_response.status_code}")
        if DEBUG_LEVEL >= 2:
            try:
                response_data = http_response.json()
                print(f"[YouTube] [{timestamp}] API Response: {json.dumps(response_data, indent=2)}")
            except:
                print(f"[YouTube] [{timestamp}] Raw Response: {http_response.text[:500]}")
    
    if exception and DEBUG_LEVEL >= 2:
        print(f"[YouTube] [{timestamp}] Exception: {str(exception)}")

def check_api_key():
    """
    Überprüft, ob der YouTube API-Key gültig ist
    FIXED: Verwendet Channel-ID statt 'mine=true' Parameter
    """
    if not YOUTUBE_API_KEY:
        log_error("YouTube API-Key ist nicht gesetzt! Bitte YOUTUBE_API_KEY in .env setzen.")
        return False
    
    if not YOUTUBE_CHANNEL_ID:
        log_error("YouTube Channel-ID ist nicht gesetzt! Bitte YOUTUBE_CHANNEL_ID in .env setzen.")
        return False
    
    for attempt in range(YOUTUBE_RETRY_COUNT):
        try:
            log(f"Teste YouTube API-Key (Versuch {attempt + 1}/{YOUTUBE_RETRY_COUNT})...", level=2)
            
            # FIXED: Verwende Channel-ID statt 'mine=true'
            url = "https://www.googleapis.com/youtube/v3/channels"
            params = {
                'part': 'id,snippet',
                'id': YOUTUBE_CHANNEL_ID,
                'key': YOUTUBE_API_KEY
            }
            
            response = requests.get(url, params=params, timeout=YOUTUBE_API_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('items'):
                    channel_name = data['items'][0]['snippet']['title']
                    log(f"YouTube API-Key ist gültig - Kanal: {channel_name}")
                    return True
                else:
                    log_error("Channel-ID nicht gefunden", http_response=response)
                    return False
            elif response.status_code == 400:
                log_error("Ungültige Anfrage - prüfe API-Key und Channel-ID", http_response=response)
                return False
            elif response.status_code == 403:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                error_reason = error_data.get('error', {}).get('errors', [{}])[0].get('reason', 'unknown')
                
                if error_reason == 'quotaExceeded':
                    log_error("YouTube API-Quota überschritten - versuche später erneut")
                elif error_reason == 'keyInvalid':
                    log_error("YouTube API-Key ist ungültig")
                else:
                    log_error(f"YouTube API-Zugriff verweigert: {error_reason}", http_response=response)
                return False
            else:
                log_error(f"YouTube API-Key Test fehlgeschlagen: HTTP {response.status_code}", http_response=response)
                
            # Exponential backoff bei wiederholbaren Fehlern
            if attempt < YOUTUBE_RETRY_COUNT - 1:
                wait_time = YOUTUBE_BACKOFF_MULTIPLIER ** attempt
                log(f"Warte {wait_time}s vor nächstem Versuch...", level=2)
                time.sleep(wait_time)
                
        except requests.exceptions.Timeout:
            log_error(f"Timeout beim API-Key Test (Versuch {attempt + 1})")
            if attempt < YOUTUBE_RETRY_COUNT - 1:
                time.sleep(2 ** attempt)
        except Exception as e:
            log_error(f"Fehler beim Testen des API-Keys (Versuch {attempt + 1})", e)
            if attempt < YOUTUBE_RETRY_COUNT - 1:
                time.sleep(2 ** attempt)
    
    return False

def get_live_broadcast_id():
    """
    Findet die aktuelle Live-Übertragung des Kanals
    IMPROVED: Bessere Fehlerbehandlung und Debug-Ausgaben
    """
    for attempt in range(YOUTUBE_RETRY_COUNT):
        try:
            log(f"Suche Live-Stream (Versuch {attempt + 1}/{YOUTUBE_RETRY_COUNT})...", level=2)
            
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                'part': 'id,snippet',
                'channelId': YOUTUBE_CHANNEL_ID,
                'eventType': 'live',
                'type': 'video',
                'key': YOUTUBE_API_KEY,
                'maxResults': 5  # Erweitert für bessere Chance
            }
            
            response = requests.get(url, params=params, timeout=YOUTUBE_API_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                
                log(f"Gefunden: {len(items)} Live-Stream(s)", level=2)
                
                if items:
                    # Nimm den ersten verfügbaren Stream
                    video_id = items[0]['id']['videoId']
                    video_title = items[0]['snippet']['title']
                    log(f"Live-Stream gefunden: {video_title} (ID: {video_id})")
                    return video_id
                else:
                    log("Kein aktiver Live-Stream gefunden")
                    
                    # Bei DEBUG_LEVEL 2: Suche auch nach geplanten Streams
                    if DEBUG_LEVEL >= 2:
                        log("Suche nach geplanten Streams...", level=2)
                        params['eventType'] = 'upcoming'
                        upcoming_response = requests.get(url, params=params, timeout=YOUTUBE_API_TIMEOUT)
                        if upcoming_response.status_code == 200:
                            upcoming_data = upcoming_response.json()
                            upcoming_items = upcoming_data.get('items', [])
                            if upcoming_items:
                                log(f"Gefunden: {len(upcoming_items)} geplante Stream(s)", level=2)
                                for item in upcoming_items:
                                    title = item['snippet']['title']
                                    scheduled_time = item['snippet'].get('scheduledStartTime', 'unbekannt')
                                    log(f"Geplant: {title} um {scheduled_time}", level=2)
                    
                    return None
            else:
                log_error(f"Fehler beim Suchen des Live-Streams: HTTP {response.status_code}", http_response=response)
                
                # Bei bestimmten Fehlern nicht wiederholen
                if response.status_code in [400, 403, 404]:
                    return None
                
            if attempt < YOUTUBE_RETRY_COUNT - 1:
                wait_time = YOUTUBE_BACKOFF_MULTIPLIER ** attempt
                time.sleep(wait_time)
                
        except Exception as e:
            log_error(f"Fehler beim Abrufen der Live-Broadcast-ID (Versuch {attempt + 1})", e)
            if attempt < YOUTUBE_RETRY_COUNT - 1:
                time.sleep(2 ** attempt)
    
    return None

def get_live_chat_id(video_id):
    """
    Holt die Live-Chat-ID für ein Video
    IMPROVED: Bessere Fehlerbehandlung
    """
    for attempt in range(YOUTUBE_RETRY_COUNT):
        try:
            log(f"Hole Live-Chat-ID für Video {video_id} (Versuch {attempt + 1})...", level=2)
            
            url = "https://www.googleapis.com/youtube/v3/videos"
            params = {
                'part': 'liveStreamingDetails,snippet',
                'id': video_id,
                'key': YOUTUBE_API_KEY
            }
            
            response = requests.get(url, params=params, timeout=YOUTUBE_API_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                
                if items:
                    video_info = items[0]
                    video_title = video_info.get('snippet', {}).get('title', 'Unbekannt')
                    
                    if 'liveStreamingDetails' in video_info:
                        live_details = video_info['liveStreamingDetails']
                        chat_id = live_details.get('activeLiveChatId')
                        
                        if chat_id:
                            log(f"Live-Chat-ID gefunden für '{video_title}': {chat_id}")
                            return chat_id
                        else:
                            log(f"Video '{video_title}' hat keinen aktiven Live-Chat")
                            
                            # Debug: Zeige verfügbare Live-Details
                            if DEBUG_LEVEL >= 2:
                                log(f"Live-Details: {json.dumps(live_details, indent=2)}", level=2)
                            
                            return None
                    else:
                        log(f"Video '{video_title}' hat keine Live-Streaming-Details")
                        return None
                else:
                    log("Video nicht gefunden")
                    return None
            else:
                log_error(f"Fehler beim Abrufen der Live-Chat-ID: HTTP {response.status_code}", http_response=response)
                
                if response.status_code in [400, 404]:
                    return None
                    
            if attempt < YOUTUBE_RETRY_COUNT - 1:
                wait_time = YOUTUBE_BACKOFF_MULTIPLIER ** attempt
                time.sleep(wait_time)
                
        except Exception as e:
            log_error(f"Fehler beim Abrufen der Live-Chat-ID (Versuch {attempt + 1})", e)
            if attempt < YOUTUBE_RETRY_COUNT - 1:
                time.sleep(2 ** attempt)
    
    return None

def fetch_chat_messages():
    """
    Holt neue Chat-Nachrichten von der YouTube API
    IMPROVED: Bessere Fehlerbehandlung und Rate Limiting
    """
    global next_page_token, known_message_ids, consecutive_errors, last_error_time
    
    if not live_chat_id:
        log("Keine Live-Chat-ID - kann keine Nachrichten abrufen", level=2)
        return []
    
    try:
        url = "https://www.googleapis.com/youtube/v3/liveChat/messages"
        params = {
            'liveChatId': live_chat_id,
            'part': 'id,snippet,authorDetails',
            'key': YOUTUBE_API_KEY,
            'maxResults': YOUTUBE_MAX_RESULTS
        }
        
        if next_page_token:
            params['pageToken'] = next_page_token
        
        log(f"API-Aufruf: Hole Chat-Nachrichten (Chat-ID: {live_chat_id[:20]}...)", level=2)
        response = requests.get(url, params=params, timeout=YOUTUBE_API_TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            next_page_token = data.get('nextPageToken')
            poll_interval = data.get('pollingIntervalMillis', YOUTUBE_POLL_INTERVAL * 1000) / 1000
            
            # Respektiere das von YouTube empfohlene Polling-Intervall
            if poll_interval > YOUTUBE_POLL_INTERVAL:
                log(f"YouTube empfiehlt Polling-Intervall: {poll_interval}s", level=2)
            
            messages = []
            items = data.get('items', [])
            log(f"API antwortete mit {len(items)} Chat-Items", level=2)
            
            new_message_count = 0
            for item in items:
                message_id = item['id']
                
                # Debug: Zeige jede empfangene Nachricht
                snippet = item['snippet']
                author_details = item['authorDetails']
                message_text = snippet.get('displayMessage', '')
                author_name = author_details.get('displayName', 'Unbekannt')
                message_type = snippet.get('type', 'textMessageEvent')
                
                log(f"API-Item: {author_name}: {message_text} (Type: {message_type})", level=2)
                
                # Überspringe bereits verarbeitete Nachrichten
                if message_id in known_message_ids:
                    log(f"Nachricht bereits bekannt: {message_id}", level=2)
                    continue
                
                known_message_ids.add(message_id)
                new_message_count += 1
                
                # Begrenze die Anzahl der gespeicherten Message-IDs
                if len(known_message_ids) > 10000:
                    old_ids = list(known_message_ids)[:2000]
                    for old_id in old_ids:
                        known_message_ids.discard(old_id)
                    log("Message-ID Cache bereinigt", level=2)
                
                # Überspringe System-Nachrichten oder leere Nachrichten
                if message_type != 'textMessageEvent' or not message_text.strip():
                    log(f"Nachricht übersprungen: Type={message_type}, Text='{message_text}'", level=2)
                    continue
                
                # Überspringe Bot-eigene Nachrichten
                author_channel_id = author_details.get('channelId', '')
                if author_channel_id == YOUTUBE_CHANNEL_ID:
                    log(f"Eigene Nachricht übersprungen: {message_text[:50]}...", level=2)
                    continue
                
                message_obj = {
                    'id': message_id,
                    'user': author_name,
                    'message': message_text,
                    'timestamp': snippet.get('publishedAt', ''),
                    'platform': 'youtube'
                }
                
                messages.append(message_obj)
                log(f"✓ Neue YouTube-Nachricht: {author_name}: {message_text}", level=1)
            
            # Reset error counter bei erfolgreichem Request
            consecutive_errors = 0
            
            log(f"Verarbeite {len(messages)} neue YouTube-Nachrichten ({new_message_count} insgesamt neu)", level=1)
            return messages
            
        elif response.status_code == 403:
            error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
            error_reason = error_data.get('error', {}).get('errors', [{}])[0].get('reason', 'unknown')
            
            if error_reason == 'quotaExceeded':
                log_error("YouTube API-Quota überschritten")
                consecutive_errors += 1
            else:
                log_error(f"YouTube API-Zugriff verweigert: {error_reason}", http_response=response)
            
            return []
            
        elif response.status_code == 404:
            log_error("Live-Chat nicht gefunden - Stream möglicherweise beendet", http_response=response)
            global is_active
            is_active = False  # Trigger für Neuinitialisierung
            return []
            
        else:
            log_error(f"Fehler beim Abrufen der Chat-Nachrichten: HTTP {response.status_code}", http_response=response)
            consecutive_errors += 1
            last_error_time = time.time()
            return []
            
    except requests.exceptions.Timeout:
        log_error("Timeout beim Abrufen der Chat-Nachrichten")
        consecutive_errors += 1
        return []
    except Exception as e:
        log_error("Fehler beim Abrufen der Chat-Nachrichten", e)
        consecutive_errors += 1
        return []

def initialize_youtube_chat():
    """
    Initialisiert den YouTube Live-Chat
    IMPROVED: Robustere Initialisierung mit besserer Fehlerbehandlung
    """
    global live_chat_id, is_active
    
    log("Initialisiere YouTube Live-Chat...")
    
    # Prüfe API-Key
    if not check_api_key():
        log_error("API-Key-Validierung fehlgeschlagen")
        return False
    
    # Finde Live-Broadcast
    video_id = get_live_broadcast_id()
    if not video_id:
        log("Kein aktiver Live-Stream gefunden - Bot bereit für späteren Stream")
        return False
    
    # Hole Live-Chat-ID
    chat_id = get_live_chat_id(video_id)
    if not chat_id:
        log("Kein aktiver Live-Chat gefunden")
        return False
    
    live_chat_id = chat_id
    is_active = True
    log("✓ YouTube Live-Chat erfolgreich initialisiert")
    log(f"Live-Chat-ID: {live_chat_id}")
    return True

def set_message_callback(callback_function):
    """Setzt die Callback-Funktion für neue Nachrichten"""
    global message_callback
    message_callback = callback_function
    log(f"Message-Callback gesetzt: {callback_function.__name__ if hasattr(callback_function, '__name__') else 'anonymous'}")

def process_youtube_message(message_obj):
    """
    NEUE Funktion: Verarbeitet YouTube-Nachrichten über Message Dispatcher oder Callback
    """
    user = message_obj['user']
    message_text = message_obj['message']
    
    log(f"🔴 Verarbeite YouTube-Nachricht: {user}: {message_text}")
    
    # PRIORITÄT 1: Message Dispatcher verwenden
    if message_dispatcher_available:
        try:
            queue_message("youtube", user, message_text)
            log(f"📨 YouTube-Nachricht an Message Dispatcher weitergeleitet: {user}: {message_text}")
            return True
        except Exception as e:
            log_error(f"Fehler beim Weiterleiten an Message Dispatcher: {e}")
    
    # PRIORITÄT 2: Fallback auf Callback
    if message_callback:
        try:
            message_callback(user, message_text, 'youtube')
            log(f"📞 YouTube-Nachricht über Callback verarbeitet: {user}: {message_text}")
            return True
        except Exception as e:
            log_error(f"Fehler beim Callback: {e}")
    
    # PRIORITÄT 3: Direkte Ausgabe als letzter Fallback
    log(f"⚠️ Keine Verarbeitungsmethode verfügbar - nur Ausgabe: {user}: {message_text}")
    return False

def youtube_chat_worker():
    """
    Hauptschleife für das Polling der YouTube-Chat-Nachrichten
    IMPROVED: Intelligenteres Error Handling und Message Dispatcher Integration
    """
    global running, is_active, last_api_call, consecutive_errors
    
    log("YouTube Chat Worker gestartet")
    
    # Initiale Initialisierung
    if not initialize_youtube_chat():
        log("Initiale Initialisierung fehlgeschlagen, versuche später erneut...")
    
    retry_count = 0
    max_retries = 10  # Erhöht für mehr Persistenz
    base_retry_delay = 30  # Basis-Wartezeit in Sekunden
    
    while running:
        current_time = time.time()
        
        # Intelligentes Rate Limiting basierend auf API-Empfehlungen
        time_since_last_call = current_time - last_api_call
        required_interval = YOUTUBE_POLL_INTERVAL
        
        # Erhöhe Intervall bei aufeinanderfolgenden Fehlern
        if consecutive_errors > 0:
            required_interval = min(60, YOUTUBE_POLL_INTERVAL * (2 ** min(consecutive_errors, 4)))
            log(f"Erhöhtes Polling-Intervall wegen Fehlern: {required_interval}s", level=2)
        
        if time_since_last_call < required_interval:
            time.sleep(0.5)
            continue
        
        if not is_active:
            # Versuche Neuinitialisierung mit intelligentem Backoff
            retry_count += 1
            if retry_count <= max_retries:
                log(f"Versuche Neuinitialisierung ({retry_count}/{max_retries})...")
                if initialize_youtube_chat():
                    retry_count = 0
                    consecutive_errors = 0
                else:
                    # Exponentielles Backoff mit Jitter
                    wait_time = min(300, base_retry_delay * (1.5 ** retry_count))  # Max 5 Minuten
                    log(f"Neuinitialisierung fehlgeschlagen, warte {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    continue
            else:
                log("Maximale Anzahl von Neuinitialisierungsversuchen erreicht")
                log("Bot läuft weiter und prüft alle 10 Minuten erneut...")
                time.sleep(600)  # 10 Minuten Pause
                retry_count = 0
                consecutive_errors = 0
                continue
        
        # Hole neue Nachrichten
        try:
            last_api_call = current_time
            log("Rufe neue YouTube-Chat-Nachrichten ab...", level=2)
            messages = fetch_chat_messages()
            
            if messages:
                log(f"✅ Verarbeite {len(messages)} neue YouTube-Nachrichten", level=1)
                
                # NEUE: Verarbeite jede Nachricht über Message Dispatcher oder Callback
                for msg in messages:
                    try:
                        process_youtube_message(msg)
                    except Exception as callback_error:
                        log_error(f"Fehler beim Verarbeiten der YouTube-Nachricht von {msg['user']}", callback_error)
            else:
                log("Keine neuen YouTube-Nachrichten", level=2)
            
            # Reset retry counter bei erfolgreichem Lauf
            if consecutive_errors == 0:
                retry_count = 0
            
        except Exception as e:
            log_error("Fehler im YouTube Chat Worker", e)
            is_active = False
            consecutive_errors += 1
        
        # Adaptive Pause basierend auf Aktivität
        if consecutive_errors > 3:
            time.sleep(10)  # Längere Pause bei Problemen
        else:
            time.sleep(max(1, YOUTUBE_POLL_INTERVAL / 5))  # Normale Pause

def start_youtube_chat_reader(callback_function):
    """Startet den YouTube Chat Reader in einem separaten Thread"""
    global running
    
    log("🚀 Starte YouTube Chat Reader mit verbesserter Integration...")
    
    set_message_callback(callback_function)
    
    reader_thread = threading.Thread(target=youtube_chat_worker)
    reader_thread.daemon = True
    reader_thread.start()
    
    log("YouTube Chat Reader Thread gestartet")
    return reader_thread

def stop_youtube_chat_reader():
    """Stoppt den YouTube Chat Reader"""
    global running, is_active
    
    running = False
    is_active = False
    log("YouTube Chat Reader wird gestoppt...")

def get_status():
    """Gibt den aktuellen Status des YouTube Chat Readers zurück"""
    status = {
        'running': running,
        'active': is_active,
        'live_chat_id': live_chat_id,
        'known_messages': len(known_message_ids),
        'consecutive_errors': consecutive_errors,
        'last_error_time': last_error_time,
        'message_dispatcher_available': message_dispatcher_available
    }
    
    # Zusätzliche Dispatcher-Info wenn verfügbar
    if message_dispatcher_available:
        try:
            dispatcher_stats = get_dispatcher_stats()
            status['dispatcher_stats'] = dispatcher_stats
        except:
            pass
            
    return status

# Test-Funktion - IMPROVED
def test_youtube_connection():
    """
    Testet die Verbindung zur YouTube API
    IMPROVED: Weniger strenge Anforderungen für Test
    """
    log("Teste YouTube-Verbindung...")
    
    # Test 1: API-Key validieren
    if not check_api_key():
        log("✗ API-Key-Test fehlgeschlagen")
        return False
    
    log("✓ API-Key ist gültig")
    
    # Test 2: Live-Stream suchen (nicht kritisch für Funktionalität)
    video_id = get_live_broadcast_id()
    if video_id:
        log("✓ Live-Stream gefunden")
        
        # Test 3: Live-Chat prüfen (optional)
        chat_id = get_live_chat_id(video_id)
        if chat_id:
            log("✓ Live-Chat verfügbar")
            log("YouTube-Verbindung vollständig erfolgreich getestet")
            return True
        else:
            log("⚠ Live-Chat nicht verfügbar, aber Stream erkannt")
            log("YouTube-Verbindung teilweise erfolgreich")
            return True  # CHANGED: Auch ohne Chat als erfolgreich werten
    else:
        log("⚠ Kein Live-Stream aktiv")
        log("YouTube-API funktioniert, wartet auf Live-Stream")
        return True  # CHANGED: API funktioniert, das reicht für den Test

# Hauptprogramm für direkten Test
if __name__ == "__main__":
    import sys
    
    def test_callback(user, message, platform):
        print(f"[{platform.upper()}] {user}: {message}")
    
    if "--test" in sys.argv:
        print("YouTube Chat Reader - Verbindungstest")
        success = test_youtube_connection()
        sys.exit(0 if success else 1)
    
    print("YouTube Chat Reader - Standalone Test")
    print("Drücke Ctrl+C zum Beenden")
    
    try:
        if test_youtube_connection():
            start_youtube_chat_reader(test_callback)
            
            while True:
                status = get_status()
                print(f"Status: Running={status['running']}, Active={status['active']}, "
                      f"Messages={status['known_messages']}, Errors={status['consecutive_errors']}, "
                      f"Dispatcher={status['message_dispatcher_available']}")
                time.sleep(30)
        else:
            print("YouTube-Verbindungstest fehlgeschlagen")
    except KeyboardInterrupt:
        print("\nBeende YouTube Chat Reader...")
        stop_youtube_chat_reader()
        time.sleep(2)

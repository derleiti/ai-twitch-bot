#!/usr/bin/env python3
# youtube_chat_reader.py - YouTube Live Chat Reader für Zephyr Bot

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

# Status-Variablen
running = True
is_active = False
live_chat_id = None
next_page_token = None
known_message_ids = set()
last_api_call = 0
message_callback = None

# Logging
def log(message, level=1):
    """Loggt eine Nachricht, wenn das Debug-Level ausreichend ist"""
    if level > DEBUG_LEVEL:
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[YouTube] [{timestamp}] {message}")

def log_error(message, exception=None):
    """Loggt eine Fehlermeldung"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[YouTube] [{timestamp}] ERROR: {message}")
    if exception and DEBUG_LEVEL >= 2:
        print(f"[YouTube] [{timestamp}] Exception: {str(exception)}")

def check_api_key():
    """Überprüft, ob der YouTube API-Key gültig ist"""
    if not YOUTUBE_API_KEY:
        log_error("YouTube API-Key ist nicht gesetzt! Bitte YOUTUBE_API_KEY in .env setzen.")
        return False
    
    try:
        # Teste API-Key mit einfacher Kanal-Anfrage statt 'mine=true'
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {
            'part': 'id',
            'id': YOUTUBE_CHANNEL_ID,  # Verwende Channel-ID statt 'mine'
            'key': YOUTUBE_API_KEY
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('items'):
                log("YouTube API-Key ist gültig")
                return True
            else:
                log_error("Channel-ID nicht gefunden")
                return False
        else:
            log_error(f"YouTube API-Key ungültig: HTTP {response.status_code}")
            return False
    except Exception as e:
        log_error("Fehler beim Testen des API-Keys", e)
        return False

def get_live_broadcast_id():
    """Findet die aktuelle Live-Übertragung des Kanals"""
    if not YOUTUBE_CHANNEL_ID:
        log_error("YouTube Channel-ID ist nicht gesetzt! Bitte YOUTUBE_CHANNEL_ID in .env setzen.")
        return None
    
    try:
        # Suche nach aktuellen Live-Streams
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            'part': 'id',
            'channelId': YOUTUBE_CHANNEL_ID,
            'eventType': 'live',
            'type': 'video',
            'key': YOUTUBE_API_KEY,
            'maxResults': 1
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            
            if items:
                video_id = items[0]['id']['videoId']
                log(f"Live-Stream gefunden: {video_id}")
                return video_id
            else:
                log("Kein aktiver Live-Stream gefunden")
                return None
        else:
            log_error(f"Fehler beim Suchen des Live-Streams: HTTP {response.status_code}")
            if DEBUG_LEVEL >= 2:
                log_error(f"Response: {response.text}")
            return None
            
    except Exception as e:
        log_error("Fehler beim Abrufen der Live-Broadcast-ID", e)
        return None

def get_live_chat_id(video_id):
    """Holt die Live-Chat-ID für ein Video"""
    try:
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            'part': 'liveStreamingDetails',
            'id': video_id,
            'key': YOUTUBE_API_KEY
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            
            if items and 'liveStreamingDetails' in items[0]:
                live_details = items[0]['liveStreamingDetails']
                chat_id = live_details.get('activeLiveChatId')
                
                if chat_id:
                    log(f"Live-Chat-ID gefunden: {chat_id}")
                    return chat_id
                else:
                    log("Kein aktiver Live-Chat gefunden")
                    return None
            else:
                log("Video hat keine Live-Streaming-Details")
                return None
        else:
            log_error(f"Fehler beim Abrufen der Live-Chat-ID: HTTP {response.status_code}")
            return None
            
    except Exception as e:
        log_error("Fehler beim Abrufen der Live-Chat-ID", e)
        return None

def fetch_chat_messages():
    """Holt neue Chat-Nachrichten von der YouTube API"""
    global next_page_token, known_message_ids
    
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
        
        log(f"API-Aufruf: {url} mit liveChatId={live_chat_id[:20]}...", level=2)
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            next_page_token = data.get('nextPageToken')
            
            messages = []
            items = data.get('items', [])
            log(f"API antwortete mit {len(items)} Items", level=2)
            
            for item in items:
                message_id = item['id']
                
                # Debug: Zeige jede empfangene Nachricht
                snippet = item['snippet']
                author_details = item['authorDetails']
                message_text = snippet.get('displayMessage', '')
                author_name = author_details.get('displayName', 'Unbekannt')
                message_type = snippet.get('type', 'textMessageEvent')
                
                log(f"Empfangen: {author_name}: {message_text} (Type: {message_type})", level=2)
                
                # Überspringe bereits verarbeitete Nachrichten
                if message_id in known_message_ids:
                    log(f"Nachricht bereits bekannt: {message_id}", level=2)
                    continue
                
                known_message_ids.add(message_id)
                log(f"Neue Nachricht-ID hinzugefügt: {message_id}", level=2)
                
                # Begrenze die Anzahl der gespeicherten Message-IDs
                if len(known_message_ids) > 10000:
                    # Entferne die ältesten 2000 IDs
                    old_ids = list(known_message_ids)[:2000]
                    for old_id in old_ids:
                        known_message_ids.discard(old_id)
                
                # Überspringe System-Nachrichten oder leere Nachrichten
                if message_type != 'textMessageEvent' or not message_text.strip():
                    log(f"Nachricht übersprungen: Type={message_type}, Text='{message_text}'", level=2)
                    continue
                
                # Überspringe Bot-eigene Nachrichten (falls der Bot auch sendet)
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
                log(f"Nachricht zur Verarbeitung hinzugefügt: {author_name}: {message_text}", level=1)
            
            log(f"Verarbeite {len(messages)} neue Nachrichten", level=1)
            return messages
            
        elif response.status_code == 403:
            log_error("YouTube API-Quota überschritten oder Chat nicht verfügbar")
            return []
        elif response.status_code == 404:
            log_error("Live-Chat nicht gefunden - Stream möglicherweise beendet")
            return []
        else:
            log_error(f"Fehler beim Abrufen der Chat-Nachrichten: HTTP {response.status_code}")
            if DEBUG_LEVEL >= 2:
                log_error(f"Response: {response.text}")
            return []
            
    except Exception as e:
        log_error("Fehler beim Abrufen der Chat-Nachrichten", e)
        return []

def initialize_youtube_chat():
    """Initialisiert den YouTube Live-Chat"""
    global live_chat_id, is_active
    
    log("Initialisiere YouTube Live-Chat...")
    
    # Prüfe API-Key
    if not check_api_key():
        return False
    
    # Finde Live-Broadcast
    video_id = get_live_broadcast_id()
    if not video_id:
        log("Kein aktiver Live-Stream gefunden")
        return False
    
    # Hole Live-Chat-ID
    chat_id = get_live_chat_id(video_id)
    if not chat_id:
        log("Kein aktiver Live-Chat gefunden")
        return False
    
    live_chat_id = chat_id
    is_active = True
    log("YouTube Live-Chat erfolgreich initialisiert")
    log(f"Live-Chat-ID: {live_chat_id}")
    return True

def set_message_callback(callback_function):
    """Setzt die Callback-Funktion für neue Nachrichten"""
    global message_callback
    message_callback = callback_function
    log(f"Message-Callback gesetzt: {callback_function}")

def youtube_chat_worker():
    """Hauptschleife für das Polling der YouTube-Chat-Nachrichten"""
    global running, is_active, last_api_call
    
    log("YouTube Chat Worker gestartet")
    
    # Initiale Initialisierung
    if not initialize_youtube_chat():
        log("Initiale Initialisierung fehlgeschlagen, versuche später erneut...")
    
    retry_count = 0
    max_retries = 5
    
    while running:
        current_time = time.time()
        
        # Rate Limiting: Mindestabstand zwischen API-Aufrufen
        time_since_last_call = current_time - last_api_call
        if time_since_last_call < YOUTUBE_POLL_INTERVAL:
            time.sleep(0.5)
            continue
        
        if not is_active:
            # Versuche Neuinitialisierung
            retry_count += 1
            if retry_count <= max_retries:
                log(f"Versuche Neuinitialisierung ({retry_count}/{max_retries})...")
                if initialize_youtube_chat():
                    retry_count = 0
                else:
                    # Exponentielles Backoff
                    wait_time = min(60, 5 * (2 ** retry_count))
                    log(f"Neuinitialisierung fehlgeschlagen, warte {wait_time}s...")
                    time.sleep(wait_time)
                    continue
            else:
                log("Maximale Anzahl von Neuinitialisierungsversuchen erreicht, pausiere länger...")
                time.sleep(300)  # 5 Minuten Pause
                retry_count = 0
                continue
        
        # Hole neue Nachrichten
        try:
            last_api_call = current_time
            log("Rufe neue Chat-Nachrichten ab...", level=2)
            messages = fetch_chat_messages()
            
            log(f"Fetch ergab {len(messages)} neue Nachrichten", level=2)
            log(f"Callback-Funktion: {message_callback}", level=2)
            
            if messages:
                log(f"Verarbeite {len(messages)} Nachrichten mit Callback", level=1)
                if message_callback:
                    for msg in messages:
                        try:
                            log(f"Rufe Callback auf für: {msg['user']}: {msg['message']}", level=1)
                            message_callback(msg['user'], msg['message'], 'youtube')
                        except Exception as callback_error:
                            log_error(f"Fehler beim Verarbeiten der Nachricht von {msg['user']}", callback_error)
                else:
                    log("WARNUNG: Keine Callback-Funktion gesetzt!", level=1)
            
            # Reset retry counter bei erfolgreichem Aufruf
            retry_count = 0
            
        except Exception as e:
            log_error("Fehler im YouTube Chat Worker", e)
            is_active = False
            time.sleep(5)
        
        # Kurze Pause vor nächstem Poll
        time.sleep(1)

def start_youtube_chat_reader(callback_function):
    """Startet den YouTube Chat Reader in einem separaten Thread"""
    global running
    
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
    return {
        'running': running,
        'active': is_active,
        'live_chat_id': live_chat_id,
        'known_messages': len(known_message_ids)
    }

# Test-Funktion
def test_youtube_connection():
    """Testet die Verbindung zur YouTube API"""
    log("Teste YouTube-Verbindung...")
    
    if not check_api_key():
        return False
    
    video_id = get_live_broadcast_id()
    if not video_id:
        log("Test fehlgeschlagen: Kein Live-Stream")
        return False
    
    chat_id = get_live_chat_id(video_id)
    if not chat_id:
        log("Test fehlgeschlagen: Kein Live-Chat")
        return False
    
    log("YouTube-Verbindung erfolgreich getestet")
    return True

# Hauptprogramm für direkten Test
if __name__ == "__main__":
    def test_callback(user, message, platform):
        print(f"[{platform.upper()}] {user}: {message}")
    
    print("YouTube Chat Reader - Standalone Test")
    print("Drücke Ctrl+C zum Beenden")
    
    try:
        if test_youtube_connection():
            start_youtube_chat_reader(test_callback)
            
            while True:
                status = get_status()
                print(f"Status: Running={status['running']}, Active={status['active']}, Messages={status['known_messages']}")
                time.sleep(30)
        else:
            print("YouTube-Verbindungstest fehlgeschlagen")
    except KeyboardInterrupt:
        print("\nBeende YouTube Chat Reader...")
        stop_youtube_chat_reader()
        time.sleep(2)

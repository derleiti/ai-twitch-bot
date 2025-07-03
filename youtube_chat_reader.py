#!/usr/bin/env python3
"""
YouTube Chat Reader - Liest YouTube Live Chat und leitet Nachrichten an den Dispatcher weiter
Verwendet die YouTube Data API v3 für Live Chat
"""
import os
import time
import threading
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Lade Umgebungsvariablen
load_dotenv()

# YouTube API Konfiguration
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "")
YOUTUBE_BOT_NAME = os.getenv("YOUTUBE_BOT_NAME", "ZephyrBotYT")
POLLING_INTERVAL = int(os.getenv("YOUTUBE_POLLING_INTERVAL", "5"))  # Sekunden

# API URLs
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
LIVE_STREAMS_URL = f"{YOUTUBE_API_BASE}/search"
LIVE_CHAT_MESSAGES_URL = f"{YOUTUBE_API_BASE}/liveChat/messages"

class YouTubeChatReader:
    def __init__(self, dispatcher=None):
        self.dispatcher = dispatcher
        self.running = False
        self.reader_thread = None
        
        # Live Stream Info
        self.live_video_id = None
        self.live_chat_id = None
        self.next_page_token = None
        self.last_check_time = datetime.utcnow()
        
        # Statistiken
        self.stats = {
            "messages_read": 0,
            "api_calls": 0,
            "errors": 0,
            "start_time": time.time()
        }
        
        self.log("YouTube Chat Reader initialisiert")
    
    def log(self, message, level="INFO"):
        """Logging-Funktion"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] [YOUTUBE] [{level}] {message}"
        print(formatted_message)
        
        if self.dispatcher:
            self.dispatcher.log(message, level, "YOUTUBE")
    
    def validate_config(self):
        """Validiert die YouTube API-Konfiguration"""
        if not YOUTUBE_API_KEY:
            self.log("YOUTUBE_API_KEY nicht gesetzt!", "ERROR")
            return False
        
        if not YOUTUBE_CHANNEL_ID:
            self.log("YOUTUBE_CHANNEL_ID nicht gesetzt!", "ERROR")
            return False
        
        return True
    
    def find_live_stream(self):
        """Findet den aktuellen Live Stream des Kanals"""
        try:
            params = {
                "part": "id,snippet",
                "channelId": YOUTUBE_CHANNEL_ID,
                "eventType": "live",
                "type": "video",
                "key": YOUTUBE_API_KEY,
                "maxResults": 1
            }
            
            response = requests.get(LIVE_STREAMS_URL, params=params, timeout=10)
            self.stats["api_calls"] += 1
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("items"):
                    video = data["items"][0]
                    video_id = video["id"]["videoId"]
                    title = video["snippet"]["title"]
                    
                    self.log(f"Live Stream gefunden: {title} (ID: {video_id})")
                    return video_id
                else:
                    self.log("Kein aktiver Live Stream gefunden")
                    return None
            else:
                self.log(f"Fehler beim Suchen des Live Streams: {response.status_code} - {response.text}", "ERROR")
                return None
                
        except Exception as e:
            self.stats["errors"] += 1
            self.log(f"Exception beim Suchen des Live Streams: {str(e)}", "ERROR")
            return None
    
    def get_live_chat_id(self, video_id):
        """Holt die Live Chat ID für ein Video"""
        try:
            params = {
                "part": "liveStreamingDetails",
                "id": video_id,
                "key": YOUTUBE_API_KEY
            }
            
            response = requests.get(f"{YOUTUBE_API_BASE}/videos", params=params, timeout=10)
            self.stats["api_calls"] += 1
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("items"):
                    video = data["items"][0]
                    live_details = video.get("liveStreamingDetails", {})
                    chat_id = live_details.get("activeLiveChatId")
                    
                    if chat_id:
                        self.log(f"Live Chat ID gefunden: {chat_id}")
                        return chat_id
                    else:
                        self.log("Keine aktive Live Chat ID gefunden", "ERROR")
                        return None
                else:
                    self.log("Video-Details nicht gefunden", "ERROR")
                    return None
            else:
                self.log(f"Fehler beim Abrufen der Video-Details: {response.status_code}", "ERROR")
                return None
                
        except Exception as e:
            self.stats["errors"] += 1
            self.log(f"Exception beim Abrufen der Chat ID: {str(e)}", "ERROR")
            return None
    
    def read_chat_messages(self):
        """Liest neue Chat-Nachrichten"""
        if not self.live_chat_id:
            return []
        
        try:
            params = {
                "liveChatId": self.live_chat_id,
                "part": "id,snippet,authorDetails",
                "key": YOUTUBE_API_KEY,
                "maxResults": 200
            }
            
            if self.next_page_token:
                params["pageToken"] = self.next_page_token
            
            response = requests.get(LIVE_CHAT_MESSAGES_URL, params=params, timeout=10)
            self.stats["api_calls"] += 1
            
            if response.status_code == 200:
                data = response.json()
                
                # Update Page Token für nächste Anfrage
                self.next_page_token = data.get("nextPageToken")
                
                messages = []
                for item in data.get("items", []):
                    try:
                        message_data = self.parse_message(item)
                        if message_data:
                            messages.append(message_data)
                    except Exception as e:
                        self.log(f"Fehler beim Parsen einer Nachricht: {str(e)}", "ERROR")
                
                self.stats["messages_read"] += len(messages)
                return messages
                
            elif response.status_code == 403:
                self.log("API-Quota überschritten oder ungültiger API-Key", "ERROR")
                return []
            elif response.status_code == 404:
                self.log("Live Chat nicht mehr aktiv", "WARNING")
                self.live_chat_id = None
                return []
            else:
                self.log(f"Fehler beim Lesen der Chat-Nachrichten: {response.status_code}", "ERROR")
                return []
                
        except Exception as e:
            self.stats["errors"] += 1
            self.log(f"Exception beim Lesen der Chat-Nachrichten: {str(e)}", "ERROR")
            return []
    
    def parse_message(self, item):
        """Parst eine einzelne YouTube Chat-Nachricht"""
        try:
            snippet = item.get("snippet", {})
            author_details = item.get("authorDetails", {})
            
            # Basis-Informationen
            message_id = item.get("id", "")
            message_text = snippet.get("displayMessage", "")
            timestamp_str = snippet.get("publishedAt", "")
            
            # Autor-Informationen
            author_name = author_details.get("displayName", "Unknown")
            author_channel_id = author_details.get("channelId", "")
            is_moderator = author_details.get("isChatModerator", False)
            is_owner = author_details.get("isChatOwner", False)
            is_sponsor = author_details.get("isChatSponsor", False)
            
            # Zeitstempel verarbeiten
            try:
                from datetime import datetime
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')).timestamp()
            except:
                timestamp = time.time()
            
            # Filtere System-Nachrichten und leere Nachrichten
            if not message_text.strip():
                return None
            
            # Filtere Bot-eigene Nachrichten (wichtig!)
            if author_name.lower() == YOUTUBE_BOT_NAME.lower():
                return None
            
            message_data = {
                "id": message_id,
                "user": author_name,
                "message": message_text,
                "timestamp": timestamp,
                "channel_id": author_channel_id,
                "is_moderator": is_moderator,
                "is_owner": is_owner,
                "is_sponsor": is_sponsor
            }
            
            return message_data
            
        except Exception as e:
            self.log(f"Fehler beim Parsen der Nachricht: {str(e)}", "ERROR")
            return None
    
    def setup_live_stream(self):
        """Initialisiert die Live Stream-Verbindung"""
        self.log("Suche nach aktivem Live Stream...")
        
        # Finde Live Stream
        video_id = self.find_live_stream()
        if not video_id:
            return False
        
        self.live_video_id = video_id
        
        # Hole Chat ID
        chat_id = self.get_live_chat_id(video_id)
        if not chat_id:
            return False
        
        self.live_chat_id = chat_id
        self.last_check_time = datetime.utcnow()
        
        self.log("Live Stream-Verbindung erfolgreich eingerichtet")
        return True
    
    def send_message(self, message):
        """Sendet eine Nachricht in den YouTube Chat (falls implementiert)"""
        # Hinweis: Zum Senden von Nachrichten wird ein OAuth2-Token benötigt
        # Hier ist erstmal nur ein Platzhalter
        self.log(f"YouTube Nachricht senden (nicht implementiert): {message}", "DEBUG")
        
        # TODO: Implementierung mit OAuth2 für das Senden von Nachrichten
        # Dies erfordert zusätzliche Authentifizierung und Berechtigung
        return False
    
    def reader_loop(self):
        """Hauptschleife für das Lesen von Chat-Nachrichten"""
        retry_count = 0
        max_retries = 5
        
        while self.running:
            try:
                # Prüfe Live Stream Status
                if not self.live_chat_id:
                    if not self.setup_live_stream():
                        retry_count += 1
                        if retry_count >= max_retries:
                            self.log(f"Maximale Anzahl Wiederholungsversuche ({max_retries}) erreicht", "ERROR")
                            time.sleep(60)  # Längere Pause vor erneutem Versuch
                            retry_count = 0
                        else:
                            self.log(f"Live Stream Setup fehlgeschlagen, Versuch {retry_count}/{max_retries}")
                            time.sleep(30)
                        continue
                
                retry_count = 0  # Reset bei erfolgreichem Setup
                
                # Lese neue Nachrichten
                messages = self.read_chat_messages()
                
                # Verarbeite Nachrichten
                for message_data in messages:
                    if self.dispatcher:
                        success = self.dispatcher.add_message(
                            "youtube", 
                            message_data["user"], 
                            message_data["message"],
                            message_data["timestamp"]
                        )
                        if success:
                            self.log(f"Nachricht weitergeleitet: {message_data['user']}: {message_data['message'][:50]}...")
                
                # Warte vor nächster Abfrage
                time.sleep(POLLING_INTERVAL)
                
            except Exception as e:
                self.stats["errors"] += 1
                self.log(f"Fehler in Reader-Loop: {str(e)}", "ERROR")
                time.sleep(10)  # Pause bei Fehlern
    
    def start(self):
        """Startet den YouTube Chat Reader"""
        if not self.validate_config():
            self.log("Konfiguration ungültig, YouTube Chat Reader wird nicht gestartet", "ERROR")
            return False
        
        if not self.running:
            self.running = True
            self.reader_thread = threading.Thread(target=self.reader_loop)
            self.reader_thread.daemon = True
            self.reader_thread.start()
            self.log("YouTube Chat Reader gestartet")
            return True
        return False
    
    def stop(self):
        """Stoppt den YouTube Chat Reader"""
        if self.running:
            self.running = False
            if self.reader_thread:
                self.reader_thread.join(timeout=10)
            self.log("YouTube Chat Reader gestoppt")
    
    def get_stats(self):
        """Gibt Statistiken zurück"""
        uptime = int(time.time() - self.stats["start_time"])
        return {
            "messages_read": self.stats["messages_read"],
            "api_calls": self.stats["api_calls"],
            "errors": self.stats["errors"],
            "uptime_seconds": uptime,
            "live_video_id": self.live_video_id,
            "live_chat_id": self.live_chat_id,
            "is_connected": self.live_chat_id is not None
        }

# Test-Funktion
if __name__ == "__main__":
    # Einfacher Test ohne Dispatcher
    reader = YouTubeChatReader()
    
    if reader.validate_config():
        print("Starte YouTube Chat Reader Test...")
        reader.start()
        
        try:
            # Lasse Reader 30 Sekunden laufen
            time.sleep(30)
            
            stats = reader.get_stats()
            print(f"Test-Statistiken: {stats}")
            
        except KeyboardInterrupt:
            print("Test durch Benutzer beendet")
        finally:
            reader.stop()
    else:
        print("YouTube-Konfiguration unvollständig. Bitte .env prüfen.")

#!/usr/bin/env python3
"""YouTube Chat Reader für Zephyr - Vollversion"""
import os
import time
import threading
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# YouTube-Konfiguration
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "")
YOUTUBE_BOT_NAME = os.getenv("YOUTUBE_BOT_NAME", "ZephyroBot")
YOUTUBE_CHANNEL_NAME = os.getenv("YOUTUBE_CHANNEL_NAME", "").lower()
POLLING_INTERVAL = int(os.getenv("YOUTUBE_POLLING_INTERVAL", "5"))

class YouTubeChatReader:
    def __init__(self, dispatcher=None):
        self.dispatcher = dispatcher
        self.running = False
        self.reader_thread = None
        
        self.live_video_id = None
        self.live_chat_id = None
        self.next_page_token = None
        
        self.stats = {
            "messages_read": 0,
            "messages_sent": 0,
            "api_calls": 0,
            "errors": 0,
            "start_time": time.time()
        }
        
        self.seen_message_ids = set()
        self.max_cache_size = 1000
        
        print("✅ YouTube Chat Reader mit echten Features initialisiert")
    
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [YOUTUBE] {message}")
    
    def validate_config(self):
        if not YOUTUBE_API_KEY or not YOUTUBE_CHANNEL_ID:
            self.log("YouTube-Konfiguration fehlt in .env (API_KEY, CHANNEL_ID)", "WARNING")
            self.log("YouTube läuft im Simulations-Modus", "INFO")
            return False
        return True
    
    def find_live_stream(self):
        """Findet aktuellen Live Stream"""
        if not YOUTUBE_API_KEY:
            return None
            
        try:
            params = {
                "part": "id,snippet",
                "channelId": YOUTUBE_CHANNEL_ID,
                "eventType": "live",
                "type": "video",
                "key": YOUTUBE_API_KEY,
                "maxResults": 1
            }
            
            response = requests.get(f"https://www.googleapis.com/youtube/v3/search", 
                                  params=params, timeout=10)
            self.stats["api_calls"] += 1
            
            if response.status_code == 200:
                data = response.json()
                if data.get("items"):
                    video = data["items"][0]
                    video_id = video["id"]["videoId"]
                    title = video["snippet"]["title"]
                    self.log(f"Live Stream gefunden: {title[:50]}...")
                    return video_id
                else:
                    self.log("Kein aktiver Live Stream gefunden")
                    return None
            else:
                self.log(f"Fehler bei Stream-Suche: {response.status_code}", "ERROR")
                return None
                
        except Exception as e:
            self.stats["errors"] += 1
            self.log(f"Exception bei Stream-Suche: {str(e)}", "ERROR")
            return None
    
    def get_live_chat_id(self, video_id):
        """Holt Live Chat ID"""
        if not YOUTUBE_API_KEY or not video_id:
            return None
            
        try:
            params = {
                "part": "liveStreamingDetails",
                "id": video_id,
                "key": YOUTUBE_API_KEY
            }
            
            response = requests.get(f"https://www.googleapis.com/youtube/v3/videos", 
                                  params=params, timeout=10)
            self.stats["api_calls"] += 1
            
            if response.status_code == 200:
                data = response.json()
                if data.get("items"):
                    video = data["items"][0]
                    live_details = video.get("liveStreamingDetails", {})
                    chat_id = live_details.get("activeLiveChatId")
                    
                    if chat_id:
                        self.log(f"Live Chat ID: {chat_id[:20]}...")
                        return chat_id
                    else:
                        self.log("Keine Live Chat ID gefunden", "WARNING")
                        return None
                        
        except Exception as e:
            self.stats["errors"] += 1
            self.log(f"Exception bei Chat ID: {str(e)}", "ERROR")
        
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
            
            response = requests.get(f"https://www.googleapis.com/youtube/v3/liveChat/messages", 
                                  params=params, timeout=10)
            self.stats["api_calls"] += 1
            
            if response.status_code == 200:
                data = response.json()
                self.next_page_token = data.get("nextPageToken")
                
                messages = []
                for item in data.get("items", []):
                    try:
                        message_data = self.parse_message(item)
                        if message_data and message_data["id"] not in self.seen_message_ids:
                            messages.append(message_data)
                            self.seen_message_ids.add(message_data["id"])
                            
                            # Cache-Management
                            if len(self.seen_message_ids) > self.max_cache_size:
                                old_ids = list(self.seen_message_ids)[:100]
                                for old_id in old_ids:
                                    self.seen_message_ids.discard(old_id)
                                    
                    except Exception as e:
                        self.log(f"Fehler beim Parsen: {str(e)}", "ERROR")
                
                if messages:
                    self.stats["messages_read"] += len(messages)
                    self.log(f"{len(messages)} neue Nachrichten gelesen")
                
                return messages
                
            elif response.status_code == 403:
                self.log("API-Quota überschritten", "ERROR")
                return []
            elif response.status_code == 404:
                self.log("Live Chat nicht mehr aktiv", "WARNING")
                self.live_chat_id = None
                return []
            else:
                self.log(f"Fehler beim Lesen: {response.status_code}", "ERROR")
                return []
                
        except Exception as e:
            self.stats["errors"] += 1
            self.log(f"Exception beim Lesen: {str(e)}", "ERROR")
            return []
    
    def parse_message(self, item):
        """Parst YouTube Chat-Nachricht"""
        try:
            snippet = item.get("snippet", {})
            author_details = item.get("authorDetails", {})
            
            message_id = item.get("id", "")
            message_text = snippet.get("displayMessage", "")
            timestamp_str = snippet.get("publishedAt", "")
            
            author_name = author_details.get("displayName", "Unknown")
            
            # Filtere leere Nachrichten
            if not message_text.strip():
                return None
            
            # Filtere Bot-Nachrichten
            if (author_name.lower() == YOUTUBE_BOT_NAME.lower() or
                (YOUTUBE_CHANNEL_NAME and author_name.lower() == YOUTUBE_CHANNEL_NAME)):
                return None
            
            # Zeitstempel
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')).timestamp()
            except:
                timestamp = time.time()
            
            # Filtere alte Nachrichten
            if time.time() - timestamp > 300:
                return None
            
            return {
                "id": message_id,
                "user": author_name,
                "message": message_text,
                "timestamp": timestamp
            }
            
        except Exception as e:
            self.log(f"Fehler beim Parsen: {str(e)}", "ERROR")
            return None
    
    def setup_live_stream(self):
        """Setup Live Stream Verbindung"""
        self.log("Suche Live Stream...")
        
        video_id = self.find_live_stream()
        if not video_id:
            return False
        
        self.live_video_id = video_id
        
        chat_id = self.get_live_chat_id(video_id)
        if not chat_id:
            return False
        
        self.live_chat_id = chat_id
        self.next_page_token = None
        
        self.log("Live Stream Setup erfolgreich")
        return True
    
    def send_message(self, message):
        """Sendet Nachricht (Simulation oder echte API)"""
        try:
            self.log(f"YouTube Nachricht: {message[:50]}...")
            self.stats["messages_sent"] += 1
            
            # TODO: Echtes Senden mit OAuth2
            # Benötigt YouTube Data API v3 mit liveChatMessages.insert
            # und OAuth2-Authentifizierung
            
            return True
        except Exception as e:
            self.log(f"Fehler beim Senden: {e}", "ERROR")
            return False
    
    def reader_loop(self):
        """Haupt-Reader-Loop"""
        retry_count = 0
        max_retries = 3
        
        while self.running:
            try:
                # Setup Live Stream wenn nötig
                if not self.live_chat_id:
                    if self.validate_config():
                        if not self.setup_live_stream():
                            retry_count += 1
                            if retry_count >= max_retries:
                                self.log("Max retries erreicht, längere Pause...", "WARNING")
                                time.sleep(300)  # 5 Minuten
                                retry_count = 0
                            else:
                                self.log(f"Setup fehlgeschlagen, Retry {retry_count}/{max_retries}")
                                time.sleep(30)
                            continue
                    else:
                        # Simulations-Modus
                        self.log("YouTube Reader läuft (Simulations-Modus - keine echte API)")
                        time.sleep(POLLING_INTERVAL)
                        continue
                
                retry_count = 0
                
                # Lese Nachrichten
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
                            self.log(f"Nachricht weitergeleitet: {message_data['user']}")
                
                # Intelligente Pause
                pause_time = POLLING_INTERVAL
                if len(messages) > 10:
                    pause_time = max(1, POLLING_INTERVAL - 2)
                elif len(messages) == 0:
                    pause_time = min(10, POLLING_INTERVAL + 2)
                
                time.sleep(pause_time)
                
            except Exception as e:
                self.stats["errors"] += 1
                self.log(f"Fehler in Reader-Loop: {str(e)}", "ERROR")
                time.sleep(10)
    
    def start(self):
        if not self.running:
            self.running = True
            self.reader_thread = threading.Thread(target=self.reader_loop)
            self.reader_thread.daemon = True
            self.reader_thread.start()
            self.log("YouTube Chat Reader gestartet")
            return True
        return False
    
    def stop(self):
        if self.running:
            self.running = False
            if self.reader_thread:
                self.reader_thread.join(timeout=10)
            self.log("YouTube Chat Reader gestoppt")

if __name__ == "__main__":
    print("🎥 YouTube Chat Reader Test")
    reader = YouTubeChatReader()
    reader.start()
    time.sleep(30)
    reader.stop()

# Datei: message_dispatcher.py
#!/usr/bin/env python3
"""
Zentrale Message Queue und Dispatcher für Multi-Platform Bot
Verarbeitet eingehende Nachrichten von allen Plattformen und koordiniert Antworten
"""

import threading
import queue
import time
import json
from datetime import datetime
from typing import Dict, List, Callable, Optional

class MessageDispatcher:
    """Zentrale Klasse für Message-Routing zwischen Plattformen"""
    
    def __init__(self):
        self.message_queue = queue.Queue()
        self.platform_handlers = {}
        self.platform_senders = {}
        self.running = True
        self.worker_thread = None
        self.known_viewers = set()
        
        # Statistiken
        self.stats = {
            'total_messages': 0,
            'messages_by_platform': {},
            'commands_executed': 0,
            'responses_sent': 0
        }
        
    def register_platform_handler(self, platform: str, handler_func: Callable):
        """Registriert einen Handler für eingehende Nachrichten einer Plattform"""
        self.platform_handlers[platform] = handler_func
        print(f"[DISPATCHER] Handler für {platform} registriert")
        
    def register_platform_sender(self, platform: str, sender_func: Callable):
        """Registriert eine Sender-Funktion für eine Plattform"""
        self.platform_senders[platform] = sender_func
        print(f"[DISPATCHER] Sender für {platform} registriert")
        
    def queue_message(self, platform: str, author: str, message: str, metadata: Optional[Dict] = None):
        """Fügt eine Nachricht zur Verarbeitungsqueue hinzu"""
        message_obj = {
            'platform': platform,
            'author': author,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        self.message_queue.put(message_obj)
        
        # Statistiken aktualisieren
        self.stats['total_messages'] += 1
        self.stats['messages_by_platform'][platform] = self.stats['messages_by_platform'].get(platform, 0) + 1
        
    def send_to_platform(self, platform: str, message: str, exclude_platform: Optional[str] = None):
        """Sendet eine Nachricht an eine spezifische Plattform"""
        if exclude_platform and platform == exclude_platform:
            return False
            
        sender = self.platform_senders.get(platform)
        if sender:
            try:
                success = sender(message)
                if success:
                    self.stats['responses_sent'] += 1
                    print(f"[DISPATCHER] ✓ Nachricht an {platform} gesendet: {message[:50]}...")
                return success
            except Exception as e:
                print(f"[DISPATCHER] ❌ Fehler beim Senden an {platform}: {e}")
                return False
        else:
            print(f"[DISPATCHER] ⚠ Kein Sender für {platform} registriert")
            return False
            
    def broadcast_message(self, message: str, exclude_platform: Optional[str] = None):
        """Sendet eine Nachricht an alle verfügbaren Plattformen"""
        success_count = 0
        
        for platform in self.platform_senders.keys():
            if self.send_to_platform(platform, message, exclude_platform):
                success_count += 1
                
        return success_count > 0
        
    def process_message(self, message_obj: Dict):
        """Verarbeitet eine einzelne Nachricht"""
        platform = message_obj['platform']
        author = message_obj['author']
        message = message_obj['message']
        
        print(f"[DISPATCHER] 📨 {platform.upper()}: {author}: {message}")
        
        # Spezielle Behandlung für Vision-Nachrichten
        if platform == 'vision':
            # Vision-Kommentare an alle Plattformen weiterleiten
            vision_message = f"👁️ {message}"
            self.broadcast_message(vision_message)
            return
            
        # Normale Chat-Nachrichten verarbeiten
        # Prüfe auf neue Zuschauer
        viewer_key = f"{author}_{platform}"
        if viewer_key not in self.known_viewers and not author.lower().endswith('bot'):
            self.known_viewers.add(viewer_key)
            # Neue Zuschauer begrüßen
            self.handle_new_viewer(author, platform)
        
        # Verarbeite Befehle und normale Nachrichten
        handler = self.platform_handlers.get(platform)
        if handler:
            try:
                handler(author, message, platform)
            except Exception as e:
                print(f"[DISPATCHER] ❌ Fehler beim Verarbeiten der Nachricht: {e}")
        else:
            print(f"[DISPATCHER] ⚠ Kein Handler für {platform} registriert")
            
    def handle_new_viewer(self, author: str, platform: str):
        """Behandelt neue Zuschauer"""
        # Import hier um Circular Imports zu vermeiden
        try:
            from multi_platform_bot import greeting_worker
            threading.Thread(target=lambda: greeting_worker(author, platform)).start()
        except ImportError:
            print(f"[DISPATCHER] ⚠ Konnte Begrüßung für {author} nicht laden")
            
    def worker_loop(self):
        """Hauptschleife für die Nachrichtenverarbeitung"""
        print("[DISPATCHER] Message Worker gestartet")
        
        while self.running:
            try:
                # Warte auf neue Nachrichten (mit Timeout für sauberes Beenden)
                message_obj = self.message_queue.get(timeout=1.0)
                self.process_message(message_obj)
                self.message_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[DISPATCHER] ❌ Fehler im Worker Loop: {e}")
                time.sleep(1)
                
        print("[DISPATCHER] Message Worker beendet")
        
    def start(self):
        """Startet den Message Dispatcher"""
        if self.worker_thread is None:
            self.worker_thread = threading.Thread(target=self.worker_loop)
            self.worker_thread.daemon = True
            self.worker_thread.start()
            print("[DISPATCHER] Message Dispatcher gestartet")
            
    def stop(self):
        """Stoppt den Message Dispatcher"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
            print("[DISPATCHER] Message Dispatcher gestoppt")
            
    def get_stats(self) -> Dict:
        """Gibt Statistiken zurück"""
        return {
            **self.stats,
            'queue_size': self.message_queue.qsize(),
            'platforms_registered': list(self.platform_senders.keys()),
            'known_viewers': len(self.known_viewers)
        }

# Globale Dispatcher-Instanz
message_dispatcher = MessageDispatcher()

# Convenience-Funktionen für einfache Nutzung
def queue_message(platform: str, author: str, message: str, metadata: Optional[Dict] = None):
    """Convenience-Funktion zum Einreihen von Nachrichten"""
    message_dispatcher.queue_message(platform, author, message, metadata)

def broadcast_message(message: str, exclude_platform: Optional[str] = None):
    """Convenience-Funktion zum Broadcaaten von Nachrichten"""
    return message_dispatcher.broadcast_message(message, exclude_platform)

def send_to_platform(platform: str, message: str):
    """Convenience-Funktion zum Senden an eine spezifische Plattform"""
    return message_dispatcher.send_to_platform(platform, message)

def register_platform_handler(platform: str, handler_func: Callable):
    """Convenience-Funktion zum Registrieren von Handlers"""
    message_dispatcher.register_platform_handler(platform, handler_func)

def register_platform_sender(platform: str, sender_func: Callable):
    """Convenience-Funktion zum Registrieren von Sendern"""
    message_dispatcher.register_platform_sender(platform, sender_func)

def start_dispatcher():
    """Convenience-Funktion zum Starten"""
    message_dispatcher.start()

def stop_dispatcher():
    """Convenience-Funktion zum Stoppen"""
    message_dispatcher.stop()

def get_dispatcher_stats():
    """Convenience-Funktion für Statistiken"""
    return message_dispatcher.get_stats()

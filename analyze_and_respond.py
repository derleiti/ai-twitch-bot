#!/usr/bin/env python3
import os
import requests
import base64
import random
import time
from dotenv import load_dotenv

# Lade Umgebungsvariablen
load_dotenv()

# Konfiguration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if not os.path.exists(BASE_DIR):
    BASE_DIR = os.path.expanduser("~/zephyr")

# Ollama-Konfiguration - Unterstützt verschiedene API-Versionen
OLLAMA_API_VERSION = os.getenv("OLLAMA_API_VERSION", "legacy")  # "legacy" oder "v1"
OLLAMA_ENDPOINTS = {
    "legacy": {
        "generate": os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate"),
        "chat": os.getenv("OLLAMA_CHAT_URL", "http://localhost:11434/api/chat")
    },
    "v1": {
        "generate": os.getenv("OLLAMA_URL_V1", "http://localhost:11434/v1/generate"),
        "chat": os.getenv("OLLAMA_CHAT_URL_V1", "http://localhost:11434/v1/chat/completions")
    }
}

# Chat-Modell und Vision-Modell
CHAT_MODEL = os.getenv("OLLAMA_MODEL", "zephyr")
VISION_MODEL = os.getenv("VISION_MODEL", "llava")
MAX_RETRIES = int(os.getenv("OLLAMA_RETRY_COUNT", "3"))
BOT_NAME = os.getenv("BOT_NAME", "zephyr")

# Fallback-Kommentare für verschiedene Inhaltstypen
SCENE_KOMMENTARE = [
    "Die Grafik sieht wirklich fantastisch aus!",
    "Die Farben und Texturen in dieser Szene sind unglaublich detailliert!",
    "Diese Landschaft ist einfach atemberaubend gestaltet!",
    "Der Charakter-Look ist echt cool - tolle Details!",
    "Die Lichtstimmung in dieser Szene ist wirklich beeindruckend!",
    "Dieser Ort im Spiel ist wunderschön designt!",
    "Die Umgebung wirkt so realistisch, fast als wäre man selbst dort!",
    "Die Animationen sind super flüssig!",
    "Das Interface ist wirklich übersichtlich gestaltet!",
    "Die Atmosphäre hier ist fantastisch eingefangen!"
]

def get_vision_description(image_path, retries=MAX_RETRIES):
    """Analysiert ein Bild mit dem Vision-Modell"""
    if not os.path.isfile(image_path):
        print(f"❌ Bild existiert nicht: {image_path}")
        return None

    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"❌ Fehler beim Lesen des Bildes: {e}")
        return None
        
    for attempt in range(retries):
        try:
            # Zuerst versuchen wir die v1 API (OpenAI-kompatibel)
            if OLLAMA_API_VERSION == "v1":
                try:
                    # Für v1 API (neuer Ollama)
                    messages = [
                        {"role": "system", "content": "Du beschreibst Bilder detailliert und präzise."},
                        {"role": "user", "content": [
                            {"type": "text", "text": "Beschreibe möglichst genau, was auf dem Bild zu sehen ist."},
                            {"type": "image", "image": img_b64}
                        ]}
                    ]
                    
                    payload = {
                        "model": VISION_MODEL,
                        "messages": messages,
                        "stream": False
                    }
                    
                    response = requests.post(
                        OLLAMA_ENDPOINTS["v1"]["chat"],
                        json=payload,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        description = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                        if description:
                            return description
                except Exception as e:
                    print(f"⚠️ V1 API-Anfrage fehlgeschlagen: {e}")
                    print("Versuche Legacy-API...")
            
            # Legacy API als Fallback oder primäre Option
            legacy_payload = {
                "model": VISION_MODEL,
                "prompt": "Beschreibe möglichst genau, was auf dem Bild zu sehen ist.",
                "images": [img_b64],
                "stream": False
            }
            
            response = requests.post(
                OLLAMA_ENDPOINTS["legacy"]["generate"],
                json=legacy_payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                description = result.get("response", "").strip()
                if description:
                    return description
        except Exception as e:
            print(f"❌ Fehler bei Vision-Modell (Versuch {attempt+1}/{retries}): {e}")
            
        # Bei Fehlern warten wir etwas länger vor dem nächsten Versuch
        if attempt < retries - 1:
            wait_time = 2 * (attempt + 1)  # Exponentielles Backoff
            time.sleep(wait_time)
    
    return None

def identify_content_type(description):
    """Identifiziert den Typ des Inhalts basierend auf der Beschreibung"""
    if not description:
        return "allgemein"
        
    description_lower = description.lower()
    
    # Erweiterte Schlüsselwörter für bessere Kategorisierung
    code_keywords = ["code", "programming", "programmier", "entwicklungsumgebung", "editor", 
                    "code editor", "entwickler", "python", "javascript", "java", "c++", "html", 
                    "css", "ide", "visual studio", "intellij", "github", "git", "repository"]
    
    browser_keywords = ["browser", "website", "webpage", "web page", "web-site", "webseite", 
                       "firefox", "chrome", "edge", "safari", "internet explorer", "url", 
                       "http", "https", "web browser", "online", "internet"]
    
    game_keywords = ["game", "gaming", "playing", "spiel", "videospiel", "spielen", "videogame", 
                     "game character", "player", "level", "quest", "npc", "character", "console", 
                     "playstation", "xbox", "nintendo", "mission", "achievement"]
    
    terminal_keywords = ["terminal", "console", "konsole", "command line", "kommandozeile", "shell", 
                        "bash", "ubuntu", "linux", "powershell", "cmd", "command prompt", "ssh", 
                        "unix", "cli", "befehlszeile", "terminal emulator"]
    
    document_keywords = ["document", "dokument", "text", "word", "textdatei", "spreadsheet", 
                        "tabelle", "präsentation", "excel", "powerpoint", "pdf", "doc", "docx", 
                        "brief", "artikel", "bericht", "report", "paper", "formular"]
    
    # Zählung der Schlüsselwörter in jeder Kategorie
    code_count = sum(1 for keyword in code_keywords if keyword in description_lower)
    browser_count = sum(1 for keyword in browser_keywords if keyword in description_lower)
    game_count = sum(1 for keyword in game_keywords if keyword in description_lower)
    terminal_count = sum(1 for keyword in terminal_keywords if keyword in description_lower)
    document_count = sum(1 for keyword in document_keywords if keyword in description_lower)
    
    # Bestimme die Kategorie mit den meisten Treffern
    counts = {
        "code": code_count,
        "browser": browser_count,
        "game": game_count,
        "terminal": terminal_count,
        "document": document_count
    }
    
    max_category = max(counts.items(), key=lambda x: x[1])
    
    # Wenn mindestens ein Schlüsselwort gefunden wurde, verwende diese Kategorie
    if max_category[1] > 0:
        return max_category[0]
    
    return "allgemein"

def generate_chat_comment(scene_description, retries=MAX_RETRIES):
    """Generiert einen Kommentar basierend auf der Szene-Beschreibung"""
    if not scene_description:
        return None
    
    # Identifiziere den Content-Typ
    content_type = identify_content_type(scene_description)
    
    # Spezifische Prompts je nach erkanntem Inhaltstyp
    prompts = {
        "code": f"""Ein KI-Vision-Modell hat auf einem Screenshot Code oder eine Programmierumgebung erkannt:
\"{scene_description}\"

Formuliere als Twitch-Bot {BOT_NAME} eine witzige, knackige Antwort über diesen Code oder diese Programmierumgebung.
Mach einen coolen, lockeren Spruch, der für Programmierer witzig ist. Maximal 2 Sätze. Deutsch.""",

        "browser": f"""Ein KI-Vision-Modell hat auf einem Screenshot einen Browser oder eine Website erkannt:
\"{scene_description}\"

Formuliere als Twitch-Bot {BOT_NAME} eine witzige, knackige Antwort über diesen Webinhalt.
Mach einen coolen, lockeren Spruch über das, was im Browser zu sehen ist. Maximal 2 Sätze. Deutsch.""",

        "game": f"""Ein KI-Vision-Modell hat auf einem Screenshot ein Videospiel erkannt:
\"{scene_description}\"

Formuliere als Twitch-Bot {BOT_NAME} eine witzige, knackige Twitch-Antwort zum aktuellen Spielgeschehen.
Sprich wie ein Gamer und sei unterhaltsam. Maximal 2 Sätze. Deutsch.""",

        "terminal": f"""Ein KI-Vision-Modell hat auf einem Screenshot ein Terminal oder eine Konsole erkannt:
\"{scene_description}\"

Formuliere als Twitch-Bot {BOT_NAME} eine witzige, knackige Antwort über diese Terminal-Session.
Mach einen coolen Spruch für Linux/Shell-Enthusiasten. Maximal 2 Sätze. Deutsch.""",

        "document": f"""Ein KI-Vision-Modell hat auf einem Screenshot ein Textdokument erkannt:
\"{scene_description}\"

Formuliere als Twitch-Bot {BOT_NAME} eine witzige, knackige Antwort über dieses Dokument.
Sei kreativ und unterhaltsam bezüglich des Textinhalts. Maximal 2 Sätze. Deutsch.""",

        "allgemein": f"""Ein KI-Vision-Modell hat Folgendes auf einem Screenshot erkannt:
\"{scene_description}\"

Formuliere als Chat-Bot {BOT_NAME} eine knackige, witzige Twitch-Antwort zum aktuellen Inhalt.
Sei unterhaltsam und originell. Maximal 2 Sätze. Deutsch."""
    }
    
    # Auswahl des passenden Prompts
    prompt = prompts.get(content_type, prompts["allgemein"])
    
    print(f"🔍 Generiere {content_type}-Kommentar mit {CHAT_MODEL}...")
    
    # Versuche alle API-Versionen, beginnend mit der konfigurierten
    for attempt in range(retries):
        try:
            if OLLAMA_API_VERSION == "v1":
                # Versuche zuerst die v1 API
                response = requests.post(
                    OLLAMA_ENDPOINTS["v1"]["chat"],
                    json={
                        "model": CHAT_MODEL,
                        "messages": [
                            {"role": "system", "content": f"Du bist ein hilfreicher Twitch-Bot namens {BOT_NAME}. Antworte immer auf Deutsch, kurz und prägnant."}, 
                            {"role": "user", "content": prompt}
                        ],
                        "stream": False
                    }, 
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    # OpenAI-kompatible Antwortstruktur
                    text = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    if text:
                        return text
            
            # Versuche die Chat-API
            response = requests.post(
                OLLAMA_ENDPOINTS["legacy"]["chat"],
                json={
                    "model": CHAT_MODEL,
                    "messages": [
                        {"role": "system", "content": f"Du bist ein hilfreicher Twitch-Bot namens {BOT_NAME}. Antworte immer auf Deutsch, kurz und prägnant."}, 
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False
                }, 
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result.get("message", {}).get("content", "").strip()
                if text:
                    return text
            
            # Versuche als letztes die generate-API
            response = requests.post(
                OLLAMA_ENDPOINTS["legacy"]["generate"],
                json={
                    "model": CHAT_MODEL,
                    "prompt": prompt,
                    "system": f"Du bist ein hilfreicher Twitch-Bot namens {BOT_NAME}. Antworte immer auf Deutsch, kurz und prägnant.",
                    "stream": False
                }, 
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result.get("response", "").strip()
                if text:
                    return text
            
        except Exception as e:
            print(f"❌ Fehler bei Ollama-Anfrage (Versuch {attempt+1}/{retries}): {e}")
        
        # Bei Fehlern warten wir etwas länger vor dem nächsten Versuch
        if attempt < retries - 1:
            wait_time = 2 * (attempt + 1)  # Exponentielles Backoff
            time.sleep(wait_time)
    
    # Fallback: zufälliger Standardkommentar
    return random.choice(SCENE_KOMMENTARE)

def analyze_and_comment(image_path):
    """Analysiert ein Bild und generiert einen Kommentar dazu"""
    # Bild analysieren
    scene_description = get_vision_description(image_path)
    
    if not scene_description:
        print("❌ Keine Bildbeschreibung erhalten")
        return None
    
    # Kommentar generieren
    comment = generate_chat_comment(scene_description)
    
    return comment

# Für Testzwecke
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        print(f"🔍 Analysiere Bild: {image_path}")
        
        # Bild analysieren
        scene_description = get_vision_description(image_path)
        if scene_description:
            print(f"✅ Bildbeschreibung:\n{scene_description[:200]}...")
            
            # Content-Typ identifizieren
            content_type = identify_content_type(scene_description)
            print(f"📊 Erkannter Content-Typ: {content_type}")
            
            # Kommentar generieren
            comment = generate_chat_comment(scene_description)
            if comment:
                print(f"💬 Generierter Kommentar:\n{comment}")
            else:
                print("❌ Konnte keinen Kommentar generieren")
        else:
            print("❌ Konnte keine Bildbeschreibung erhalten")
    else:
        print("Bitte Bildpfad angeben: python analyze_and_respond.py /pfad/zum/bild.jpg")

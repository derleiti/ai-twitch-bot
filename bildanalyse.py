#!/usr/bin/env python3
import base64
import requests
import os
import time
import json
from dotenv import load_dotenv

# Lade Umgebungsvariablen (falls vorhanden)
load_dotenv()

# Konfiguration
OLLAMA_API_VERSION = os.getenv("OLLAMA_API_VERSION", "legacy")  # "legacy" oder "v1"
OLLAMA_LEGACY_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_V1_URL = os.getenv("OLLAMA_URL_V1", "http://localhost:11434/v1/chat/completions")

def get_vision_description(image_path, vision_model="llava", max_retries=3):
    """
    Analysiert ein Bild mit einem Vision-Modell über Ollama.
    
    Args:
        image_path: Pfad zum Bild
        vision_model: Name des Vision-Modells (default: "llava")
        max_retries: Maximale Anzahl von Wiederholungsversuchen bei Fehlern
        
    Returns:
        Beschreibung des Bildes oder None bei Fehler
    """
    if not os.path.isfile(image_path):
        print(f"❌ Bild existiert nicht: {image_path}")
        return None

    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"❌ Fehler beim Lesen des Bildes: {e}")
        return None

    for attempt in range(max_retries):
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
                        "model": vision_model,
                        "messages": messages,
                        "stream": False
                    }
                    
                    response = requests.post(
                        OLLAMA_V1_URL,
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
                "model": vision_model,
                "prompt": "Beschreibe möglichst genau, was auf dem Bild zu sehen ist.",
                "images": [img_b64],
                "stream": False
            }
            
            response = requests.post(
                OLLAMA_LEGACY_URL,
                json=legacy_payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                description = result.get("response", "").strip()
                if description:
                    return description
                    
            print(f"⚠️ Versuch {attempt+1}/{max_retries} fehlgeschlagen: HTTP {response.status_code}")
            
            # Bei Fehlern warten wir etwas länger vor dem nächsten Versuch
            if attempt < max_retries - 1:
                wait_time = 2 * (attempt + 1)  # Exponentielles Backoff
                time.sleep(wait_time)
                
        except Exception as e:
            print(f"❌ Fehler bei Vision-Modell (Versuch {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                wait_time = 2 * (attempt + 1)
                time.sleep(wait_time)
    
    return None

def check_ollama_server():
    """Überprüft, ob der Ollama-Server erreichbar ist"""
    try:
        # Versuche erstmal den API-Endpunkt für die Version
        response = requests.get("http://localhost:11434/api/version", timeout=5)
        if response.status_code == 200:
            version_info = response.json()
            return True, version_info.get("version", "unbekannt")
            
        # Fallback auf einfachen HTTP-Request
        response = requests.get("http://localhost:11434/", timeout=5)
        if response.status_code == 200:
            return True, "unbekannt"
            
        return False, None
    except Exception as e:
        print(f"❌ Ollama-Server nicht erreichbar: {e}")
        return False, None

# Für Testzwecke
if __name__ == "__main__":
    import sys
    
    # Prüfe Ollama-Server
    server_running, version = check_ollama_server()
    if server_running:
        print(f"✅ Ollama-Server ist erreichbar, Version: {version}")
    else:
        print("❌ Ollama-Server ist nicht erreichbar!")
        sys.exit(1)
        
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        print(f"🔍 Analysiere Bild: {image_path}")
        description = get_vision_description(image_path)
        if description:
            print(f"✅ Bildanalyse erfolgreich:\n{description}")
        else:
            print("❌ Keine Beschreibung erhalten")
    else:
        print("Bitte Bildpfad angeben: ./bildanalyse.py /pfad/zum/bild.jpg")

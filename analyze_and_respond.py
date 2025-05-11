#!/usr/bin/env python3
import base64
import requests
import os
import time
from log_vision_feedback import log_vision_example

OLLAMA_URL = "http://localhost:11434/api/generate"
VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava")
CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "zephyr")
MAX_RETRIES = 3

def analyze_image(path, retries=MAX_RETRIES):
    if not os.path.isfile(path):
        print(f"❌ Bild existiert nicht: {path}")
        return None

    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"❌ Fehler beim Lesen des Bildes: {e}")
        return None

    print(f"🔍 Sende Bild an {VISION_MODEL}...")
    
    for attempt in range(retries):
        try:
            res = requests.post(OLLAMA_URL, json={
                "model": VISION_MODEL,
                "prompt": "Beschreibe möglichst genau, was auf diesem Bild zu sehen ist.",
                "images": [b64],
                "stream": False
            }, timeout=30)

            if res.ok:
                response_text = res.json().get("response", "").strip()
                if response_text:
                    return response_text
                
            print(f"⚠️ Versuch {attempt+1}/{retries} fehlgeschlagen: HTTP {res.status_code}")
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))  # Exponentielles Backoff
                
        except Exception as e:
            print(f"❌ Versuch {attempt+1}/{retries} fehlgeschlagen: {e}")
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    
    return None

def generate_chat_comment(scene_description, retries=MAX_RETRIES):
    if not scene_description:
        return None
        
    # Verbesserter Prompt mit Anweisung, sich nur auf das zu beziehen, was tatsächlich zu sehen ist
    prompt = f"""Ein KI-Vision-Modell hat folgendes erkannt:
\"{scene_description}\"

Formuliere jetzt als Chat-Bot Zephyr eine knackige, witzige Twitch-Antwort, die sich genau auf das bezieht, was tatsächlich im Bild zu sehen ist.
Antworte auf Deutsch, maximal 2 Sätze. Sprich wie ein Gamer und sei unterhaltsam, aber präzise."""
    
    print(f"🔍 Generiere Kommentar mit {CHAT_MODEL}...")
    
    # ... Rest der Funktion bleibt unverändert        
    prompt = f"""Ein KI-Vision-Modell hat folgendes erkannt:
\"{scene_description}\"

Formuliere jetzt als Chat-Bot Zephyr eine knackige, witzige Twitch-Antwort – auf Deutsch, maximal 2 Sätze. Sprich wie ein Gamer."""
    
    print(f"🔍 Generiere Kommentar mit {CHAT_MODEL}...")
    
    for attempt in range(retries):
        try:
            # Versuche zuerst das neuere Format für Ollama 0.6.x
            res = requests.post(OLLAMA_URL, json={
                "model": CHAT_MODEL,
                "messages": [
                    {"role": "system", "content": "Du bist ein hilfreicher Twitch-Bot. Antworte immer auf Deutsch, kurz und prägnant."}, 
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            }, timeout=30)
            
            if res.ok:
                response_text = res.json().get("response", "").strip()
                if response_text:
                    return response_text
            
            # Wenn nicht erfolgreich, versuche das ältere Format
            res = requests.post(OLLAMA_URL, json={
                "model": CHAT_MODEL,
                "prompt": prompt,
                "stream": False
            }, timeout=30)
            
            if res.ok:
                response_text = res.json().get("response", "").strip()
                if response_text:
                    return response_text
                
            print(f"⚠️ Versuch {attempt+1}/{retries} fehlgeschlagen: HTTP {res.status_code}")
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                
        except Exception as e:
            print(f"❌ Versuch {attempt+1}/{retries} fehlgeschlagen: {e}")
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    
    return None

def analyze_and_comment(image_path):
    print(f"🖼️ Analysiere Bild: {image_path}")
    vision = analyze_image(image_path)
    if not vision:
        print("❌ Vision-Modell konnte nichts erkennen.")
        return None

    print(f"📸 Vision sagt: {vision[:100]}...")
    chat = generate_chat_comment(vision)
    if not chat:
        print("❌ Chatmodell konnte keinen Kommentar erzeugen.")
        return None

    print(f"💬 Kommentar: {chat}")
    
    # Logge das Beispiel für späteres Training
    try:
        log_vision_example(image_path, vision, "(auto)")
    except Exception as e:
        print(f"⚠️ Fehler beim Logging: {e}")
    
    return chat

# Für Testzwecke
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        result = analyze_and_comment(image_path)
        if result:
            print(f"✅ Ergebnis: {result}")
        else:
            print("❌ Keine Antwort generiert")
    else:
        print("Bitte Bildpfad angeben: ./analyze_and_respond.py /pfad/zum/bild.jpg")

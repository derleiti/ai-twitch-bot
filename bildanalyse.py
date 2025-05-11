#!/usr/bin/env python3
import base64
import requests
import os
import time

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
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": vision_model,
                    "prompt": "Beschreibe möglichst genau, was auf dem Bild zu sehen ist.",
                    "images": [img_b64]
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json().get("response", "").strip()
                if result:
                    return result
                    
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

# Für Testzwecke
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        description = get_vision_description(image_path)
        if description:
            print(f"✅ Bildanalyse erfolgreich:\n{description}")
        else:
            print("❌ Keine Beschreibung erhalten")
    else:
        print("Bitte Bildpfad angeben: ./bildanalyse.py /pfad/zum/bild.jpg")

#!/usr/bin/env python3
import base64
import requests
import os
import json
import time

# Pfad zum neuesten Screenshot
screenshots_dir = os.path.expanduser("~/zephyr/screenshots")
if os.path.exists(screenshots_dir):
    screenshots = sorted([
        os.path.join(screenshots_dir, f)
        for f in os.listdir(screenshots_dir)
        if f.lower().endswith(('.png', '.jpg', '.jpeg'))
    ], key=os.path.getmtime, reverse=True)
    
    if screenshots:
        img_path = screenshots[0]
        print(f"Neuester Screenshot: {img_path}")
        
        with open(img_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        payload = {
            "model": "llava",
            "prompt": "Was ist auf diesem Bild zu sehen?",
            "images": [img_b64],
            "stream": False
        }

        response = requests.post("http://localhost:11434/api/generate", json=payload)

        if response.ok:
            try:
                description = response.json().get("response", "Keine Antwort")
                print("\n✅ LLaVA Antwort:\n")
                print(description)
                
                # Speichere in einer Datei, die der Bot lesen kann
                response_file = os.path.expanduser("~/zephyr/latest_vision.txt")
                with open(response_file, "w") as f:
                    f.write(description)
                print(f"\nBeschreibung in {response_file} gespeichert")
                
            except Exception as e:
                print("❌ Fehler beim Parsen:", e)
                print(response.text)
        else:
            print("❌ HTTP-Fehler:", response.status_code)
            print(response.text)
    else:
        print("Keine Screenshots gefunden")
else:
    print(f"Screenshot-Verzeichnis nicht gefunden: {screenshots_dir}")

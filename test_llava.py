#!/usr/bin/env python3
import base64
import requests
import os

img_path = os.path.expanduser("~/zephyr/screenshots/stream_1746899149.jpg")

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
        print("\n✅ LLaVA Antwort:\n")
        print(response.json().get("response", "Keine Antwort"))
    except Exception as e:
        print("❌ Fehler beim Parsen:", e)
        print(response.text)
else:
    print("❌ HTTP-Fehler:", response.status_code)
    print(response.text)

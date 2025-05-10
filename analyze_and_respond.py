#!/usr/bin/env python3
import base64
import requests
import os
from log_vision_feedback import log_vision_example

OLLAMA_URL = "http://localhost:11434/api/generate"
VISION_MODEL = "llava"
CHAT_MODEL = "zephyr"

def analyze_image(path):
    if not os.path.isfile(path):
        return None

    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    res = requests.post(OLLAMA_URL, json={
        "model": VISION_MODEL,
        "prompt": "Beschreibe möglichst genau, was auf diesem Bild zu sehen ist.",
        "images": [b64],
        "stream": False
    })

    if res.ok:
        return res.json().get("response", "").strip()
    return None

def generate_chat_comment(scene_description):
    prompt = f"""Ein KI-Vision-Modell hat folgendes erkannt:
\"{scene_description}\"

Formuliere jetzt als Chat-Bot Zephyr eine knackige, witzige Twitch-Antwort – auf Deutsch, maximal 2 Sätze. Sprich wie ein Gamer."""
    
    res = requests.post(OLLAMA_URL, json={
        "model": CHAT_MODEL,
        "prompt": prompt,
        "stream": False
    })

    if res.ok:
        return res.json().get("response", "").strip()
    return None

def analyze_and_comment(image_path):
    print(f"🖼️  Analysiere Bild: {image_path}")
    vision = analyze_image(image_path)
    if not vision:
        print("❌ Vision-Modell konnte nichts erkennen.")
        return None

    print(f"📸 Vision sagt: {vision}")
    chat = generate_chat_comment(vision)
    if not chat:
        print("❌ Zephyr konnte keinen Kommentar erzeugen.")
        return None

    print(f"💬 Zephyr sagt: {chat}")
    log_vision_example(image_path, vision, "(auto)")
    return chat

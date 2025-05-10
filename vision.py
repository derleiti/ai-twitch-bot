import requests
import base64
import os

def get_latest_screenshot_path():
    # Hier könntest du deinen OBS-/Screenshot-Pfad einstellen
    screenshot_dir = "/tmp/screenshots"
    if not os.path.exists(screenshot_dir):
        return None

    screenshots = sorted([
        os.path.join(screenshot_dir, f)
        for f in os.listdir(screenshot_dir)
        if f.lower().endswith(('.png', '.jpg', '.jpeg'))
    ], key=os.path.getmtime, reverse=True)

    return screenshots[0] if screenshots else None

def get_vision_description(image_path):
    if not os.path.exists(image_path):
        return "Kein Bild gefunden."

    with open(image_path, "rb") as img_file:
        image_bytes = img_file.read()
        encoded_image = base64.b64encode(image_bytes).decode('utf-8')

    payload = {
        "model": "llava",  # ggf. "llava:7b" je nach Ollama
        "prompt": "Beschreibe das Bild möglichst präzise auf Deutsch.",
        "images": [encoded_image],
        "stream": False
    }

    try:
        response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=30)
        if response.ok:
            return response.json().get("response", "").strip()
        else:
            return f"Ollama-Fehler: {response.status_code}"
    except Exception as e:
        return f"Ollama-Ausnahme: {str(e)}"

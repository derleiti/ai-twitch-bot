import base64
import requests
import os

def get_vision_description(image_path, vision_model="llava"):
    if not os.path.isfile(image_path):
        return None

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

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
            return response.json().get("response", "").strip()
    except Exception as e:
        print(f"Fehler bei Vision-Modell: {e}")
    
    return None

import os
import subprocess
import json
from datetime import datetime
import re  # für Zusammenfassung

def run_llava_analysis(image_path):
    command = [
        "ollama", "run", "llava",
        f"Describe this image in detail: {image_path}"
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"Error: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return "LLaVA timeout"
    except Exception as e:
        return f"Exception: {str(e)}"

def save_analysis_result(image_path, analysis_text, output_file="vision_log.json"):
    timestamp = datetime.now().isoformat()
    entry = {
        "timestamp": timestamp,
        "image": image_path,
        "analysis": analysis_text
    }

    if os.path.exists(output_file):
        with open(output_file, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []

    data.append(entry)

    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

def summarize_llava_response(llava_text: str) -> str:
    """
    Macht aus der langen LLaVA-Antwort eine kurze Zusammenfassung mit Einschätzung.
    """
    # Auf 1-2 Sätze kürzen
    sentences = re.split(r'(?<=[.!?]) +', llava_text.strip())
    summary = ' '.join(sentences[:2]) if sentences else llava_text.strip()

    # Bewertung dranhängen
    labels = {
        "gun": "– Heftige Action",
        "dark": "– Düsterer Look",
        "funny": "– Lustige Szene",
        "menu": "– Spielmenü",
        "hud": "– HUD sichtbar",
        "text": "– Text erkennbar",
        "nothing": "– Kein relevanter Inhalt",
    }

    tag = "– Screenshot"
    for key, val in labels.items():
        if key in llava_text.lower():
            tag = val
            break

    return f"{summary} {tag}"

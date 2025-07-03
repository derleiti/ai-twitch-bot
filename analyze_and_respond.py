import os
import time
from bildanalyse import run_llava_analysis, save_analysis_result, summarize_llava_response

SCREENSHOTS_DIR = "screenshots"
ANALYSIS_LOG = "vision_log.json"

def analyze_latest_screenshot():
    try:
        # Neueste Bilddatei holen
        images = [f for f in os.listdir(SCREENSHOTS_DIR) if f.endswith((".png", ".jpg", ".jpeg"))]
        if not images:
            return "Kein Screenshot gefunden."

        latest_image = max(images, key=lambda f: os.path.getctime(os.path.join(SCREENSHOTS_DIR, f)))
        image_path = os.path.join(SCREENSHOTS_DIR, latest_image)

        # Analyse starten
        llava_result = run_llava_analysis(image_path)
        summarized = summarize_llava_response(llava_result)

        # Ergebnis speichern
        save_analysis_result(image_path, summarized, ANALYSIS_LOG)

        return summarized

    except Exception as e:
        return f"Analyse-Fehler: {str(e)}"

if __name__ == "__main__":
    while True:
        result = analyze_latest_screenshot()
        print(f"[LLaVA]: {result}")
        time.sleep(30)

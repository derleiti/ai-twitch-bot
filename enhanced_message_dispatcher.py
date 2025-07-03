import time
import os
import json
from bildanalyse import run_llava_analysis, save_analysis_result, summarize_llava_response
from twitch_ollama_bot import send_message as send_twitch
from youtube_chat_reader import send_message as send_youtube

SCREENSHOTS_DIR = "screenshots"
ANALYSIS_LOG = "vision_log.json"
GAME_STATE_FILE = "game_state.json"

def load_game_state():
    """
    Liest den Spielstatus aus game_state.json.
    """
    try:
        with open(GAME_STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def format_chat_message(llava_summary, game_state):
    """
    Kombiniert die Bildanalyse mit Game/Mood aus game_state.json.
    """
    parts = [f"[LLaVA]: {llava_summary}"]
    if game_state.get("game") or game_state.get("mood"):
        context = []
        if game_state.get("game"):
            context.append(f"Game: {game_state['game']}")
        if game_state.get("mood"):
            context.append(f"Mood: {game_state['mood']}")
        parts.append("[" + " | ".join(context) + "]")
    return " ".join(parts)

def analyze_and_dispatch():
    try:
        images = [f for f in os.listdir(SCREENSHOTS_DIR) if f.endswith((".png", ".jpg", ".jpeg"))]
        if not images:
            return

        latest_image = max(images, key=lambda f: os.path.getctime(os.path.join(SCREENSHOTS_DIR, f)))
        image_path = os.path.join(SCREENSHOTS_DIR, latest_image)

        llava_result = run_llava_analysis(image_path)
        summarized = summarize_llava_response(llava_result)

        save_analysis_result(image_path, summarized, ANALYSIS_LOG)

        game_state = load_game_state()
        chat_message = format_chat_message(summarized, game_state)

        send_twitch(chat_message)
        send_youtube(chat_message)

    except Exception as e:
        print(f"[Fehler bei Analyse & Dispatch]: {e}")

if __name__ == "__main__":
    while True:
        analyze_and_dispatch()
        time.sleep(30)

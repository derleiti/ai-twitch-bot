def generate_chat_comment(scene_description, retries=MAX_RETRIES):
    if not scene_description:
        return None
    
    # Versuche Content-Typ aus der Beschreibung zu extrahieren
    content_type = "allgemein"
    if "code" in scene_description.lower() or "programming" in scene_description.lower() or "editor" in scene_description.lower():
        content_type = "code"
    elif "browser" in scene_description.lower() or "website" in scene_description.lower() or "webpage" in scene_description.lower():
        content_type = "browser"
    elif "game" in scene_description.lower() or "playing" in scene_description.lower() or "videogame" in scene_description.lower():
        content_type = "game"
    elif "terminal" in scene_description.lower() or "command line" in scene_description.lower() or "console" in scene_description.lower():
        content_type = "terminal"
    elif "document" in scene_description.lower() or "text" in scene_description.lower() or "word" in scene_description.lower():
        content_type = "document"
    
    # Spezifische Prompts je nach erkanntem Inhaltstyp
    prompts = {
        "code": f"""Ein KI-Vision-Modell hat auf einem Screenshot Code oder eine Programmierumgebung erkannt:
\"{scene_description}\"

Formuliere als Twitch-Bot Zephyr eine witzige, knackige Antwort über diesen Code oder diese Programmierumgebung.
Mach einen coolen, lockeren Spruch, der für Programmierer witzig ist. Maximal 2 Sätze. Deutsch.""",

        "browser": f"""Ein KI-Vision-Modell hat auf einem Screenshot einen Browser oder eine Website erkannt:
\"{scene_description}\"

Formuliere als Twitch-Bot Zephyr eine witzige, knackige Antwort über diesen Webinhalt.
Mach einen coolen, lockeren Spruch über das, was im Browser zu sehen ist. Maximal 2 Sätze. Deutsch.""",

        "game": f"""Ein KI-Vision-Modell hat auf einem Screenshot ein Videospiel erkannt:
\"{scene_description}\"

Formuliere als Twitch-Bot Zephyr eine witzige, knackige Twitch-Antwort zum aktuellen Spielgeschehen.
Sprich wie ein Gamer und sei unterhaltsam. Maximal 2 Sätze. Deutsch.""",

        "terminal": f"""Ein KI-Vision-Modell hat auf einem Screenshot ein Terminal oder eine Konsole erkannt:
\"{scene_description}\"

Formuliere als Twitch-Bot Zephyr eine witzige, knackige Antwort über diese Terminal-Session.
Mach einen coolen Spruch für Linux/Shell-Enthusiasten. Maximal 2 Sätze. Deutsch.""",

        "document": f"""Ein KI-Vision-Modell hat auf einem Screenshot ein Textdokument erkannt:
\"{scene_description}\"

Formuliere als Twitch-Bot Zephyr eine witzige, knackige Antwort über dieses Dokument.
Sei kreativ und unterhaltsam bezüglich des Textinhalts. Maximal 2 Sätze. Deutsch.""",

        "allgemein": f"""Ein KI-Vision-Modell hat Folgendes auf einem Screenshot erkannt:
\"{scene_description}\"

Formuliere als Chat-Bot Zephyr eine knackige, witzige Twitch-Antwort zum aktuellen Inhalt.
Sei unterhaltsam und originell. Maximal 2 Sätze. Deutsch."""
    }
    
    # Auswahl des passenden Prompts
    prompt = prompts.get(content_type, prompts["allgemein"])
    
    print(f"🔍 Generiere {content_type}-Kommentar mit {CHAT_MODEL}...")
    
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
            
            # Rest der Funktion wie zuvor...

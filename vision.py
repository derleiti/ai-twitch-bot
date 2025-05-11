def identify_game(image_path):
    """
    Identifiziert das im Bild gezeigte Spiel.
    
    Args:
        image_path: Pfad zum Screenshot
        
    Returns:
        Name des identifizierten Spiels oder "Unbekannt"
    """
    if not os.path.exists(image_path):
        return "Unbekannt"
        
    try:
        with open(image_path, "rb") as img_file:
            image_bytes = img_file.read()
            encoded_image = base64.b64encode(image_bytes).decode('utf-8')

        # Spezifischerer Prompt zur Spielidentifikation
        prompt = """Erkenne das Videospiel auf diesem Screenshot. 
        Gib NUR den Namen des Spiels zurück, keine weiteren Informationen oder Beschreibungen.
        Falls du dir nicht sicher bist oder es kein Spiel ist, antworte nur mit "Unbekannt"."""

        payload = {
            "model": "llava",
            "prompt": prompt,
            "images": [encoded_image],
            "stream": False
        }

        response = requests.post("http://localhost:11434/api/generate", 
                                json=payload, 
                                timeout=30)
        if response.ok:
            game_name = response.json().get("response", "").strip()
            # Filtere zu lange oder zu allgemeine Antworten
            if len(game_name) > 50 or "ich kann nicht" in game_name.lower() or "schwer zu sagen" in game_name.lower():
                return "Unbekannt"
            return game_name
            
        return "Unbekannt"
        
    except Exception as e:
        print(f"Fehler bei Spielidentifikation: {str(e)}")
        return "Unbekannt"

def identify_content_type(image_path):
    """
    Identifiziert den Typ des angezeigten Inhalts im Screenshot.
    
    Args:
        image_path: Pfad zum Screenshot
        
    Returns:
        Dictionary mit Typ und Details des Inhalts
    """
    if not os.path.exists(image_path):
        return {"type": "unbekannt", "details": {}}
        
    try:
        with open(image_path, "rb") as img_file:
            image_bytes = img_file.read()
            encoded_image = base64.b64encode(image_bytes).decode('utf-8')

        prompt = """Analysiere diesen Screenshot und bestimme, was darauf zu sehen ist.
        Mögliche Kategorien sind:
        - Videospiel (wenn ja, welches?)
        - Code/Programmierumgebung (wenn ja, welche Sprache?)
        - Website/Browser (wenn ja, welcher Inhalt?)
        - Desktop/Betriebssystem (wenn ja, welches?)
        - Textdokument/Tabelle (wenn ja, welcher Inhalt?)
        - Terminal/Konsole
        - Video/Stream
        - Sonstiges

        Antwort im JSON-Format: 
        {"type": "kategorie", "details": {"name": "konkreter_name", "beschreibung": "kurze_beschreibung"}}"""

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
            result = response.json().get("response", "").strip()
            try:
                # Versuche JSON zu parsen
                import json
                content_info = json.loads(result)
                return content_info
            except:
                # Fallback wenn kein valides JSON zurückkommt
                return {
                    "type": "unbekannt", 
                    "details": {"beschreibung": result[:100] if result else "Keine Beschreibung"}
                }
            
        return {"type": "unbekannt", "details": {}}
        
    except Exception as e:
        print(f"Fehler bei Inhaltstyperkennung: {str(e)}")
        return {"type": "unbekannt", "details": {"fehler": str(e)}}

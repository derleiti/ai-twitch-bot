def llava_vision_analyze(image_path: str) -> dict:
    """
    Vision via Ollama (Qwen-VL/LLaVA) – zuerst /api/chat versuchen, bei 404 auf /api/generate zurückfallen.
    Liefert {"short_chat": "...", "long_call": "..."}.
    """
    b64 = _b64_image(image_path)

    system = (
        "Du bist ein Vision-Assistent für Gaming. Beschreibe prägnant, natürlich und ohne Aufzählungen. "
        "Antwortform NUR als JSON mit den Schlüsseln short_chat (2–5 kurze Sätze, <=320 Zeichen) und long_call (<=300 Zeichen). "
        "Keine Entschuldigungen, kein Meta-Talk."
    )
    user = (
        "Analysiere HUD/Status (HP/Mana/Ressourcen), Orientierung (Minimap/Quest) und Notables. "
        "Gib ausschließlich ein kompaktes JSON zurück."
    )

    def _chat_call() -> str:
        url = f"{OLLAMA_URL}/api/chat"
        body = {
            "model": VLM_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user, "images": [b64]},
            ],
            "options": {"temperature": 0.2, "top_p": 0.9},
        }
        r = requests.post(url, json=body, timeout=60)
        r.raise_for_status()
        return r.json().get("message", {}).get("content", "")

    def _generate_call() -> str:
        url = f"{OLLAMA_URL}/api/generate"
        prompt = system + "\n" + user
        body = {
            "model": VLM_MODEL,
            "prompt": prompt,
            "images": [b64],
            "stream": False,
            "options": {"temperature": 0.2, "top_p": 0.9},
        }
        r = requests.post(url, json=body, timeout=60)
        r.raise_for_status()
        j = r.json()
        return (j.get("response") or j.get("message", {}).get("content", "")).strip()

    # Erst /api/chat, bei 404 auf /api/generate
    try:
        content = _chat_call()
    except requests.HTTPError as e:
        if getattr(e.response, "status_code", None) == 404:
            log_info("VISION", "Ollama /api/chat nicht verfügbar → Fallback /api/generate")
            content = _generate_call()
        else:
            raise
    except Exception:
        content = _generate_call()

    content = _to_text(content).strip()
    m = re.search(r"\{.*\}", content, re.S)
    if m:
        try:
            out = json.loads(m.group(0))
        except Exception:
            out = {"short_chat": _clip(content, MAX_SHORT_CHAT_LEN), "long_call": _clip(content, 300)}
    else:
        out = {"short_chat": _clip(content, MAX_SHORT_CHAT_LEN), "long_call": _clip(content, 300)}

    out = {
        "short_chat": sanitize_short_chat(out.get("short_chat", "")),
        "long_call":  _clip(_to_text(out.get("long_call", "")), 300),
    }
    return out

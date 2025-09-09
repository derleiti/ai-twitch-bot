# -*- coding: utf-8 -*-
"""
Normalisiert Chat-Inhalte auf OpenAI/VL-Parts.
Erlaubt str | list[str] | list[dict] und gibt immer eine Parts-Liste zurück.
"""
from typing import Any, List, Dict

def to_parts(content: Any) -> List[Dict[str, Any]]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        if content and isinstance(content[0], dict) and "type" in content[0]:
            return content  # bereits Parts
        if content and isinstance(content[0], str):
            return [{"type": "text", "text": t} for t in content]
    return [{"type": "text", "text": ""}]


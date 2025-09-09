# -*- coding: utf-8 -*-
"""
llm_providers.py
Einheitliche Schnittstelle für Gemini, Mistral und lokale GPT-OSS (Ollama) – inkl. Rotations-Logik.
Priorität: AI_ORDER aus .env
Modus: "first" (Failover) oder "rotate" (Load-Balancing)
"""
from __future__ import annotations

import os
import json
import logging
from typing import List, Dict, Any, Optional
import requests

# .env automatisch laden
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

log = logging.getLogger(__name__)

def _first_text(messages: List[Dict[str,str]]) -> str:
    parts = []
    for m in messages:
        role = m.get("role","user")
        c = m.get("content","")
        if not isinstance(c, str):
            try:
                c = json.dumps(c, ensure_ascii=False)
            except Exception:
                c = str(c)
        if role == "system":
            parts.append(f"[System] {c}")
        elif role == "assistant":
            parts.append(f"[Assistant] {c}")
        else:
            parts.append(c)
    return "\n".join([p for p in parts if p]).strip()

def _req(method: str, url: str, **kw) -> requests.Response:
    timeout = kw.pop("timeout", (10, 60))
    return requests.request(method, url, timeout=timeout, **kw)

class BaseProvider:
    name: str = "base"
    def available(self) -> bool: return True
    def chat(self, messages: List[Dict[str,str]], temperature: float=0.3, max_tokens: int=512, **_) -> str: raise NotImplementedError

# ===== Provider-Implementierungen (Gemini, Mistral, Ollama) bleiben unverändert =====
class GeminiProvider(BaseProvider):
    name = "gemini"
    def __init__(self, api_key: Optional[str], model: str="gemini-1.5-flash"):
        self.api_key = (api_key or "").strip()
        self.model = model or "gemini-1.5-flash"
        self.base = "https://generativelanguage.googleapis.com/v1beta"
    def available(self) -> bool: return bool(self.api_key)
    def chat(self, messages: List[Dict[str,str]], temperature: float=0.3, max_tokens: int=512, **_) -> str:
        url = f"{self.base}/models/{self.model}:generateContent?key={self.api_key}"
        text = _first_text(messages)
        payload = {
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {"temperature": float(temperature), "maxOutputTokens": int(max_tokens)}
        }
        r = _req("POST", url, json=payload)
        r.raise_for_status()
        data = r.json()
        try:
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0]["content"]["parts"]
                txt = "".join([p.get("text","") for p in parts if isinstance(p, dict)])
                return txt.strip()
        except Exception:
            pass
        return json.dumps(data, ensure_ascii=False)

class MistralProvider(BaseProvider):
    name = "mistral"
    def __init__(self, api_key: Optional[str], model: str="mistral-large-latest", api_base: Optional[str]=None):
        self.api_key = (api_key or "").strip()
        self.model = model or "mistral-large-latest"
        self.base = (api_base or "https://api.mistral.ai").rstrip("/")
    def available(self) -> bool: return bool(self.api_key)
    def chat(self, messages: List[Dict[str,str]], temperature: float=0.3, max_tokens: int=512, **_) -> str:
        url = f"{self.base}/v1/chat/completions"
        payload = {"model": self.model, "messages": messages, "temperature": float(temperature), "max_tokens": int(max_tokens)}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        r = _req("POST", url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()

class OllamaProvider(BaseProvider):
    name = "gpt-oss"
    def __init__(self, base_url: str="http://127.0.0.1:11434", model: str="gpt-oss:latest"):
        self.base = (base_url or "http://127.0.0.1:11434").rstrip("/")
        self.model = model or "gpt-oss:latest"
    def available(self) -> bool:
        try:
            return _req("GET", f"{self.base}/api/tags", timeout=(3, 5)).status_code < 500
        except Exception:
            return False
    def chat(self, messages: List[Dict[str,str]], temperature: float=0.3, max_tokens: int=512, **_) -> str:
        url = f"{self.base}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "options": {"temperature": float(temperature), "num_predict": int(max_tokens)},
            "stream": False
        }
        r = _req("POST", url, json=payload); r.raise_for_status()
        data = r.json()
        return data["message"]["content"].strip()

# ===== ProviderChain mit Rotations-Logik =====
class ProviderChain:
    def __init__(self, providers: List[BaseProvider], mode: str="first"):
        self.providers = [p for p in providers if p.available()]
        self.mode = mode
        self.next_provider_index = 0 # Startet immer beim ersten Provider
        if not self.providers:
            log.error("Keine verfügbaren KI-Provider gefunden! Bitte .env prüfen.")

    @classmethod
    def from_env(cls) -> "ProviderChain":
        order = os.getenv("AI_ORDER", "gemini,mistral,gpt-oss")
        mode  = os.getenv("AI_MODE", "first") # Liest "first" oder "rotate"
        
        gem = GeminiProvider(os.getenv("GEMINI_API_KEY"), os.getenv("GEMINI_MODEL","gemini-1.5-flash"))
        mis = MistralProvider(os.getenv("MISTRAL_API_KEY"), os.getenv("MISTRAL_MODEL","mistral-large-latest"), os.getenv("MISTRAL_API_BASE"))
        oll = OllamaProvider(os.getenv("OLLAMA_URL","http://127.0.0.1:11434"), os.getenv("OLLAMA_TEXT_MODEL", os.getenv("OLLAMA_MODEL","gpt-oss:latest")))
        
        mapping = {"gemini": gem, "mistral": mis, "gpt-oss": oll, "ollama": oll}
        providers = [mapping[k] for k in [x.strip() for x in order.split(",")] if k.strip() in mapping]
        
        return cls(providers, mode)

    def chat(self, messages: List[Dict[str,str]], temperature: float=0.3, max_tokens: int=512, **kw) -> Optional[str]:
        if not self.providers:
            return None

        if self.mode == "rotate":
            # Startet die Suche beim nächsten geplanten Provider und geht die Liste durch
            start_index = self.next_provider_index
            # Baut eine Liste in der Reihenfolge, die wir testen wollen (z.B. [1, 2, 0] wenn wir bei Index 1 starten)
            providers_to_try = self.providers[start_index:] + self.providers[:start_index]
            
            for i, provider in enumerate(providers_to_try):
                log.info(f"[ProviderChain|rotate] Versuche Provider: {provider.name}")
                try:
                    response = provider.chat(messages, temperature, max_tokens, **kw)
                    # Erfolg! Merke dir den NÄCHSTEN für das nächste Mal.
                    current_provider_index_in_original_list = self.providers.index(provider)
                    self.next_provider_index = (current_provider_index_in_original_list + 1) % len(self.providers)
                    log.info(f"[ProviderChain|rotate] Erfolg mit {provider.name}. Nächster Provider ist {self.providers[self.next_provider_index].name}.")
                    return response
                except requests.exceptions.RequestException as e:
                    log.warning(f"[ProviderChain|rotate] Provider '{provider.name}' fehlgeschlagen: {e}")
                    continue # Versuche den nächsten in der Rotations-Reihenfolge
        
        else: # Standard "first" / Failover-Modus
            for provider in self.providers:
                log.info(f"[ProviderChain|first] Versuche Provider: {provider.name}")
                try:
                    return provider.chat(messages, temperature, max_tokens, **kw)
                except requests.exceptions.RequestException as e:
                    log.warning(f"[ProviderChain|first] Provider '{provider.name}' fehlgeschlagen: {e}")
                    continue

        log.error("[ProviderChain] Alle Provider sind fehlgeschlagen.")
        return None

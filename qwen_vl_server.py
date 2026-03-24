from contextlib import contextmanager
import os
import re
import base64
from io import BytesIO
import requests
from typing import List, Optional, Tuple, Any

import torch
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from transformers import AutoConfig, AutoProcessor, AutoModelForImageTextToText

# ========= Konfig =========
HF_MODEL_ID = os.getenv("QWEN_VL_MODEL", "Qwen/Qwen2.5-VL-3B-Instruct")
CLIENT_MODEL = "qwen2.5-vl"

_device = "cuda" if torch.cuda.is_available() else "cpu"
_dtype = torch.bfloat16 if _device == "cuda" else torch.float32

_app = app = FastAPI()

_model = None
_processor = None


def _ensure_loaded():
    global _model, _processor
    if _model is not None and _processor is not None:
        return

    load_kwargs = dict(
        torch_dtype=_dtype,
        trust_remote_code=True,
    )
    # Device-Placement
    if _device == "cuda":
        load_kwargs["device_map"] = "auto"

    _processor = AutoProcessor.from_pretrained(HF_MODEL_ID, trust_remote_code=True)
    _model = AutoModelForImageTextToText.from_pretrained(HF_MODEL_ID, **load_kwargs)
    # Greedy-safe defaults
    try:
        _model.generation_config.temperature = 1.0
        _model.generation_config.top_p = None
    except Exception:
        pass

    _model.eval()


# ========= Schemas (OpenAI-kompatibel) =========
class ImageURL(BaseModel):
    url: str


class ContentItem(BaseModel):
    type: str
    text: Optional[str] = None
    image_url: Optional[ImageURL] = None


class Message(BaseModel):
    role: str
    content: List[ContentItem]


class ChatCompletionsRequest(BaseModel):
    model: Optional[str] = Field(default=CLIENT_MODEL)
    messages: List[Message]
    temperature: Optional[float] = 0.2
    max_tokens: Optional[int] = 256


# ========= Hilfsfunktionen =========
def _normalize_messages(msgs: List[dict]) -> List[dict]:
    """Stellt sicher, dass content eine Liste aus {type,text|image_url} ist."""
    out = []
    for m in msgs:
        role = m.get("role", "user")
        content = m.get("content", [])
        if isinstance(content, dict):
            content = [content]
        elif isinstance(content, str):
            content = [{"type": "text", "text": content}]
        out.append({"role": role, "content": content})
    return out


def _extract_image_and_text(msgs: List[dict]) -> Tuple[Optional[List[Any]], str]:
    """Extrahiert Bilder (falls vorhanden) + Text (konkateniert). Data-URLs und HTTP/HTTPS werden unterstützt."""
    text_parts: List[str] = []
    images: List[Image.Image] = []

    def _load_image(u: str):
        try:
            dbg = os.getenv("QWEN_VL_DEBUG")
            if u.startswith("data:image"):
                # Data-URL (base64). Robust dekodieren: Whitespace raus, Padding justieren, dann hart decoden.
                try:
                    b64 = u.split(",", 1)[1].strip()
                except Exception as e:
                    if dbg: print(f"[qwen-vl] data-url split fail: {e}", flush=True)
                    return None
                b64 = "".join(b64.split())  # whitespace entfernen
                # Padding korrigieren
                pad = (-len(b64)) % 4
                if pad:
                    b64 += "=" * pad
                try:
                    raw = base64.b64decode(b64, validate=False)
                except Exception as e:
                    if dbg: print(f"[qwen-vl] base64 decode fail: {e}", flush=True)
                    return None
                try:
                    img = Image.open(BytesIO(raw))
                    img.load()  # dekompression auslösen
                    return img.convert("RGB")
                except Exception as e:
                    if dbg: print(f"[qwen-vl] PIL open fail: {e}", flush=True)
                    return None

            if u.startswith("http://") or u.startswith("https://"):
                # HTTP/HTTPS
                r = requests.get(u, timeout=10)
                r.raise_for_status()
                try:
                    img = Image.open(BytesIO(r.content))
                    img.load()
                    return img.convert("RGB")
                except Exception as e:
                    if dbg: print(f"[qwen-vl] HTTP PIL fail: {e}", flush=True)
                    return None

            if u.startswith("file://"):
                # Lokaler Dateipfad (nur lesen)
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(u)
                    # Bei file-URLs ist der Pfad in .path
                    local_path = parsed.path
                    if not local_path:
                        return None
                    # Sicherheit: Prüfung auf Directory Traversal
                    if '../' in local_path or '..\\' in local_path:
                        raise Exception('Invalid file path')
                    with open(local_path, 'rb') as f:
                        raw = f.read()
                    img = Image.open(BytesIO(raw))
                    img.load()
                    return img.convert("RGB")
                except Exception as e:
                    if dbg: print(f"[qwen-vl] file:// load fail: {e}", flush=True)
                    return None

            return None
        except Exception as e:
            if os.getenv("QWEN_VL_DEBUG"):
                print(f"[qwen-vl] _load_image fatal: {e}", flush=True)
            return None


    for m in msgs:
        for c in m.get("content", []):
            t = c.get("type")
            if t == "text" and c.get("text"):
                text_parts.append(str(c["text"]))
            elif t == "image_url" and c.get("image_url", {}).get("url"):
                img = _load_image(c["image_url"]["url"])
                if img is not None:
                    images.append(img)

    text = "\n".join(text_parts).strip()
    return (images if images else None, text)


def _as_pil_list(x: Any) -> Optional[List[Image.Image]]:
    if x is None:
        return None
    if isinstance(x, list):
        out = []
        for e in x:
            try:
                if isinstance(e, Image.Image):
                    out.append(e.convert("RGB"))
                elif isinstance(e, (bytes, bytearray)):
                    out.append(Image.open(BytesIO(e)).convert("RGB"))
            except Exception:
                pass
        return out or None
    if isinstance(x, (bytes, bytearray)):
        try:
            return [Image.open(BytesIO(x)).convert("RGB")]
        except Exception:
            return None
    if isinstance(x, Image.Image):
        return [x.convert("RGB")]
    return None




def _build_qwen_inputs(prompt: str, pil_list: Optional[List[Image.Image]]):
    """
    Baut für Qwen2.5-VL die richtigen Inputs:
    - Text über apply_chat_template (fügt Bild-Platzhalter in den Prompt ein)
    - images als 1er-Batch: [pil_list] oder None
    Videos unterstützen wir hier nicht (None).
    """
    messages = [{
        "role": "user",
        "content": (
            ([{"type": "image", "image": img} for img in (pil_list or [])] ) +
            [{"type": "text", "text": (prompt or "").strip() or "Beschreibe das Bild kurz."}]
        ),
    }]
    # Chat-Template anwenden (fügt die erforderlichen Bild-Platzhalter ein)
    try:
        text = _processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    except Exception:
        # Fallback: Minimaltext ohne Platzhalter – funktioniert nur, wenn keine Bilder vorliegen.
        text = (prompt or "").strip() or "Beschreibe das Bild kurz."
    # Für einen einzelnen Request erwartet der Prozessor eine Liste von Texten
    text_list = [text]
    # Images als Batch: Liste der Beispiele; für 1 Beispiel => [pil_list] oder None
    images_batch = [pil_list] if pil_list else None
    videos_batch = None
    return text_list, images_batch, videos_batch
def _generate(user_text: str,
              images: Optional[List[Image.Image]],
              temperature: float = 0.2,
              max_tokens: int = 256) -> str:
    """Bild+Text -> Text mit Qwen-VL, nur neu generierte Tokens decodiert."""
    _ensure_loaded()

    pil_list = _as_pil_list(images)
    prompt = user_text.strip() if user_text else "Beschreibe das Bild kurz."

    # Encode über Chat-Template + korrektes Images-Batching
    text_list, images_batch, videos_batch = _build_qwen_inputs(prompt, pil_list)
    inputs = _processor(
        text=text_list,
        images=images_batch,
        videos=videos_batch,
        padding=True,
        return_tensors="pt",
    )
    # auf Device
    inputs = {k: (v.to(_device) if hasattr(v, "to") else v) for k, v in inputs.items()}

    # Prompt-Länge merken
    input_len = None
    if "input_ids" in inputs and hasattr(inputs["input_ids"], "shape"):
        input_len = int(inputs["input_ids"].shape[-1])

    tok = getattr(_processor, "tokenizer", None)
    eos_id = (getattr(getattr(tok, "eos_token_id", None), "__int__", lambda: None)()  # falls obj
              if tok is not None else None)
    if eos_id is None and tok is not None:
        eos_id = getattr(tok, "eos_token_id", None)
    if eos_id is None and hasattr(getattr(_model, "config", None), "eos_token_id"):
        eos_id = getattr(_model.config, "eos_token_id", None)

    pad_id = None
    if tok is not None:
        pad_id = getattr(tok, "pad_token_id", None)
        if pad_id is None:
            pad_id = getattr(tok, "eos_token_id", None)
    if pad_id is None and hasattr(getattr(_model, "config", None), "pad_token_id"):
        pad_id = getattr(_model.config, "pad_token_id", None)
    if pad_id is None:
        pad_id = eos_id

    # Sampling-Parameter ableiten
    has_image = pil_list is not None and len(pil_list) > 0

    # Regel:
    # - Mit Bild: wir erlauben Sampling, aber NUR mit positiver Temperatur.
    #             Falls temperature<=0 oder None: greedy (do_sample=False), temp=None, top_p=None.
    # - Ohne Bild: klassisch greedy (deterministischer), temp=None, top_p=None.
    if has_image and (temperature is not None) and (float(temperature) > 0):
        do_sample = True
        temp = float(temperature)
        top_p = 0.9
    elif has_image:
        # Bild vorhanden, aber temperature<=0: Greedy statt Exception
        do_sample = False
        temp = None
        top_p = None
    else:
        # Kein Bild: deterministisch
        do_sample = False
        temp = None
        top_p = None

    # Generate
    with torch.no_grad():
        print(f"[qwen-vl] sampling={do_sample} temp={temp} top_p={top_p}", flush=True)
        out = _model.generate(
            **inputs,
            max_new_tokens=int(max_tokens or 256),
            do_sample=do_sample,
            temperature=temp,
            top_p=top_p,
            eos_token_id=eos_id,
            pad_token_id=pad_id,
        )

    # Nur NEU generierte Tokens decodieren
    if input_len is not None and out.shape[-1] > input_len:
        gen_only = out[0, input_len:]
    else:
        gen_only = out[0]

    out_text = (_processor.batch_decode(gen_only.unsqueeze(0), skip_special_tokens=True)[0].strip()
                if tok is None else tok.decode(gen_only, skip_special_tokens=True).strip())

    # Prompt-Echo entfernen
    prompt_text = user_text.strip() if isinstance(user_text, str) else ""
    if prompt_text and out_text.startswith(prompt_text):
        out_text = out_text[len(prompt_text):].lstrip()

    if prompt_text:
        first_line = prompt_text.splitlines()[0].strip()
        for lead in (first_line, first_line.rstrip("."), first_line + ":", first_line + ".", first_line + "?"):
            if out_text.startswith(lead):
                out_text = out_text[len(lead):].lstrip()

    return _postprocess_text(out_text, prompt_text)


# ========= Routes =========
@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [{"id": CLIENT_MODEL, "object": "model", "owned_by": "qwen-vl-bridge"}],
    }


@app.post("/v1/chat/completions")
async def chat_completions(req: Request):
    try:
        _ensure_loaded()
        payload = await req.json()
        data = ChatCompletionsRequest(**payload)

        raw_msgs = [m.model_dump() for m in data.messages]
        norm = _normalize_messages(raw_msgs)
        images, user_text = _extract_image_and_text(norm)

        image_requested = False
        try:
            image_requested = any(
                any((c.get('type') == 'image_url') for c in msg.get('content', []))
                for msg in norm if isinstance(msg, dict)
            )
        except Exception:
            pass
        if image_requested and (not images or len(images) == 0):
            return JSONResponse(content={
                'id': 'chatcmpl-qwen-vl-bridge',
                'object': 'chat.completion',
                'model': data.model or CLIENT_MODEL,
                'choices': [{
                    'index': 0,
                    'message': {'role':'assistant','content':'Ich konnte kein brauchbares Bild laden (zu klein/leer/nicht erreichbar).'},
                    'finish_reason':'stop'
                }],
            })

        out_text = _generate(
            user_text=user_text,
            images=images,
            temperature=float(data.temperature or 0.2),
            max_tokens=int(data.max_tokens or 256),
        )

        return JSONResponse(
            content={
                "id": "chatcmpl-qwen-vl-bridge",
                "object": "chat.completion",
                "model": data.model or CLIENT_MODEL,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": out_text},
                        "finish_reason": "stop",
                    }
                ],
            }
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": {"message": f"{type(e).__name__}: {e}", "type": "server_error"}},
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.getenv("QWEN_VL_HOST", "0.0.0.0"), port=int(os.getenv("QWEN_VL_PORT", "8010")))


def _postprocess_text(out_text: str, prompt_text: str) -> str:
    import re, string
    # Markdown-Bild-Markup entfernen
    out_text = re.sub(r'!\[[^\]]*\]\([^)]*\)\s*', '', out_text or '').strip()

    if not isinstance(out_text, str):
        return str(out_text or "").strip()

    # 1) Offensichtliche Meta-Zeilen entfernen
    meta_patterns = [
        r"(?i)^die antwort muss mindestens .*? w[öo]rter lang sein\.?$",
        r"(?i)^translate\b.*$",
        r"(?i)^sure,?\s*$",
    ]
    lines = [ln for ln in out_text.splitlines() if not any(re.search(p, ln.strip()) for p in meta_patterns)]
    out_text = "\n".join(lines).strip()

    # 2) Ein-Wort-Spezialfall: "Sag X in einem Wort"
    if isinstance(prompt_text, str):
        m = re.search(r'(?i)sag\s+([^\s\.\!\?":]+)\s+in\s+(?:einem|one)\s+wort', prompt_text)
        if m:
            target = m.group(1).strip(string.punctuation)
            if target:
                return target

    # 3) Falls der Prompt "in einem Wort" enthält, auf 1 Token kürzen
    if isinstance(prompt_text, str) and re.search(r"(?i)\bin (?:einem|one) wort\b", prompt_text):
        tok = out_text.strip().split()
        if tok:
            out_text = tok[0].strip(string.punctuation)

    return str(out_text or "").strip()


@contextmanager
def _temp_genconfig(model, **kw):
    cfg = getattr(model, "generation_config", None)
    if cfg is None:
        yield
        return
    old = {k: getattr(cfg, k, None) for k in kw}
    try:
        for k, v in kw.items():
            setattr(cfg, k, v)
        yield
    finally:
        for k, v in old.items():
            setattr(cfg, k, v)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}

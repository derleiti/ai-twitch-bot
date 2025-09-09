import os, time, base64, requests
from typing import Tuple, Optional

TIMEOUT_MS = int(os.getenv("HEALTH_TIMEOUT_MS", "1500"))
INC_QWEN = os.getenv("HEALTH_INCLUDE_QWEN", "true").lower() != "false"
INC_AUTH = os.getenv("HEALTH_INCLUDE_AUTH", "true").lower() != "false"
SHOW_ERR = os.getenv("HEALTH_SHOW_ERRORS", "false").lower() == "true"

def _ms() -> int:
    return int(time.time() * 1000)

def _tiny_png_b64() -> str:
    return base64.b64encode(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDATx^\x63\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    ).decode("ascii")

def check_qwen(base: str, model: str, timeout_ms: int = TIMEOUT_MS) -> Tuple[bool, Optional[int], Optional[str]]:
    try:
        # Allow override via ZEPHYR_* envs (optional)
        base = os.getenv("ZEPHYR_QWEN_BASE", base)
        model = os.getenv("ZEPHYR_QWEN_MODEL", model)
        try:
            timeout_ms = int(float(os.getenv("ZEPHYR_QWEN_TIMEOUT", str(timeout_ms/1000))) * 1000)
        except Exception:
            pass
        t0 = _ms()
        # OpenAI-compatible content parts (list of items), required by our Qwen bridge
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": [{"type": "text", "text": "respond with a single word"}]},
                {"role": "user",   "content": [{"type": "text", "text": "ping"}]},
            ],
            "max_tokens": 4,
            "temperature": 0.0,
        }
        r = requests.post(f"{base}/v1/chat/completions", json=payload, timeout=timeout_ms/1000)
        r.raise_for_status()
        _ = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        return True, _ms() - t0, None
    except Exception as e:
        tag = type(e).__name__.lower()
        return False, None, tag

def check_auth(base: str, timeout_ms: int = TIMEOUT_MS) -> Tuple[bool, Optional[int], Optional[str]]:
    try:
        t0 = _ms()
        r = requests.get(f"{base}/", timeout=timeout_ms/1000)
        r.raise_for_status()
        ok = r.json().get("service") == "auth"
        return (True if ok else False), (_ms()-t0 if ok else None), (None if ok else "bad_payload")
    except Exception as e:
        return False, None, type(e).__name__.lower()

def fmt_check(name: str, ok: bool, ms: Optional[int], err: Optional[str], show_err: Optional[bool] = None) -> str:
    if ok and ms is not None:
        return f"{name}: OK {ms}ms"
    show = SHOW_ERR if show_err is None else show_err
    if show and err:
        return f"{name}: ERR({err})"
    return f"{name}: ERR"

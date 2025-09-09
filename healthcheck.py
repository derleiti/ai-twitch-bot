import os, sys, json, base64, socket, requests
from pathlib import Path
try:
    # Load .env explicitly from repo root (sibling to this file)
    from dotenv import load_dotenv  # type: ignore
    DOTENV_PATH = (Path(__file__).resolve().parent / ".env")
    if DOTENV_PATH.exists():
        load_dotenv(dotenv_path=DOTENV_PATH)
except Exception:
    # Non-fatal in environments without python-dotenv
    pass

def ok(msg): print("✅", msg)
def bad(msg): print("❌", msg); return False

def check_qwen():
    base = os.getenv("QWEN_BASE","http://127.0.0.1:8010")
    # Normalize to API root ending with /v1
    api = base.rstrip("/")
    if not api.endswith("/v1"):
        api = f"{api}/v1"
    model = os.getenv("QWEN_MODEL","qwen-vl")
    # 1x1 PNG
    tiny_png = base64.b64encode(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDATx^\x63\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    ).decode("ascii")
    payload = {
        "model": model,
        "messages": [
            {"role":"system","content":[{"type":"text","text":"Respond with one short sentence."}]},
            {"role":"user","content":[
                {"type":"text","text":"Ping vision endpoint"},
                {"type":"image_url","image_url":{"url":f"data:image/png;base64,{tiny_png}"}}
            ]}
        ],
        "temperature":0.1
    }
    try:
        r = requests.post(f"{api}/chat/completions", json=payload, timeout=15)
        r.raise_for_status()
        _ = r.json()["choices"][0]["message"]["content"]
        ok(f"Qwen-VL reachable at {base}")
        return True
    except Exception as e:
        print(e); return bad("Qwen-VL check failed")

def check_auth():
    # Allow disabling via env to avoid false negatives in local runs
    include = os.getenv("HEALTH_INCLUDE_AUTH", "true").lower() != "false"
    if not include:
        ok("Auth check skipped (HEALTH_INCLUDE_AUTH=false)")
        return True
    base = os.getenv("AUTH_BASE_URL","http://127.0.0.1:8088")
    try:
        r = requests.get(f"{base}/", timeout=5)
        r.raise_for_status()
        js = r.json()
        if js.get("service") == "auth" and js.get("status") == "ok":
            ok(f"Auth service reachable at {base}")
            return True
        return bad("Auth service responded but not OK payload")
    except Exception as e:
        print(e); return bad("Auth service check failed")

def check_twitch_env():
    # Support both new and legacy keys (same logic as twitch_client)
    user = os.getenv("TWITCH_USERNAME") or os.getenv("BOT_USERNAME") or ""
    token = os.getenv("TWITCH_OAUTH_TOKEN") or os.getenv("OAUTH_TOKEN") or ""
    channel = os.getenv("TWITCH_CHANNEL") or os.getenv("CHANNEL") or ""
    if not channel:
        # python-dotenv treats leading '#' as comment; fall back to raw parse
        try:
            env_path = (Path(__file__).resolve().parent / ".env")
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    if not line or line.lstrip().startswith("#"):
                        continue
                    if line.startswith("CHANNEL=") and not os.getenv("TWITCH_CHANNEL"):
                        raw = line.split("=", 1)[1].strip()
                        if (raw.startswith("\"") and raw.endswith("\"")) or (raw.startswith("'") and raw.endswith("'")):
                            raw = raw[1:-1]
                        channel = raw
                        break
        except Exception:
            pass
    # Normalize channel
    channel = channel.strip()
    if channel and not channel.startswith("#"):
        channel = f"#{channel}"
    good = True
    if not user:
        good = bad("TWITCH_USERNAME missing (or BOT_USERNAME)")
    if not token.startswith("oauth:"):
        good = bad("TWITCH_OAUTH_TOKEN must start with 'oauth:' (or OAUTH_TOKEN)")
    if not channel:
        good = bad("TWITCH_CHANNEL missing (or CHANNEL)")
    if good:
        ok("Twitch env looks sane")
    return good

def check_formatter():
    try:
        import commentary_engine as ce
        s = "```json\n{\"x\":1}\n```\n" + ("Z"*600)
        out = ce.prepare_for_twitch(s)
        if "```" in out or len(out) > int(os.getenv("TWITCH_MAX_MESSAGE_LEN","500")):
            return bad("Formatter sanitation/clamp failed")
        ok("Formatter sanitation/clamp OK")
        return True
    except Exception as e:
        print(e); return bad("Formatter import failed")

def check_vision_lang():
    val = (os.getenv("VISION_LANG") or "de").strip().lower()
    if val.startswith("en"):
        ok("VISION_LANG=en (English)")
        return True
    if val.startswith("de") or val == "german":
        ok("VISION_LANG=de (Deutsch)")
        return True
    print(f"Note: Unknown VISION_LANG='{val}', defaulting to 'de' (Deutsch)")
    ok("VISION_LANG default applied (Deutsch)")
    return True

def check_commentary_lang():
    val = (os.getenv("COMMENTARY_LANG") or "de").strip().lower()
    if val.startswith("en"):
        ok("COMMENTARY_LANG=en (English)")
        return True
    if val.startswith("de") or val == "german":
        ok("COMMENTARY_LANG=de (Deutsch)")
        return True
    print(f"Note: Unknown COMMENTARY_LANG='{val}', defaulting to 'de' (Deutsch)")
    ok("COMMENTARY_LANG default applied (Deutsch)")
    return True

if __name__ == "__main__":
    failures = 0
    failures += 0 if check_qwen() else 1
    failures += 0 if check_auth() else 1
    failures += 0 if check_twitch_env() else 1
    failures += 0 if check_formatter() else 1
    failures += 0 if check_vision_lang() else 1
    failures += 0 if check_commentary_lang() else 1
    if failures == 0:
        print("\n🎯 healthcheck OK")
        sys.exit(0)
    print(f"\n⚠️ healthcheck FAILED ({failures} checks)") 
    sys.exit(1)

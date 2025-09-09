import os, subprocess

def cmd_health():
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "health_probe.sh"))
    if not os.path.exists(script):
        return "Health: Skript fehlt (scripts/health_probe.sh)."
    try:
        out = subprocess.check_output([script], stderr=subprocess.STDOUT, timeout=20, text=True)
        return f"✅ {out.strip()}"
    except subprocess.CalledProcessError as e:
        return f"❌ Health FAIL ({e.returncode}): {e.output.strip()}"
    except subprocess.TimeoutExpired:
        return "❌ Health TIMEOUT"


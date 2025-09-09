import time
from pathlib import Path
from screenshots.screenshot_manager import ingest, SCREENSHOT_DIR

if __name__ == "__main__":
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    for i in range(12):
        p = SCREENSHOT_DIR / f"seed_{i:02}.png"
        p.write_bytes(b"X" * (512 + i))
        print("ingest:", ingest(str(p), "seed@host"))
        time.sleep(0.01)


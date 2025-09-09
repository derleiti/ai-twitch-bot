import os, time, importlib
from pathlib import Path


def test_ringbuffer_prunes_and_dedup(tmp_path, monkeypatch):
    # Point the module to a temp dir BEFORE import
    monkeypatch.setenv("SCREENSHOT_DIR", str(tmp_path))
    monkeypatch.setenv("SCREENSHOT_MAX", "5")

    # Import after env is set so it picks up the temp dir
    import screenshots.screenshot_manager as sm
    importlib.reload(sm)

    # Seed 8 distinct files (unique sizes to avoid hash/size dedupe)
    paths = []
    for i in range(8):
        p = tmp_path / f"shot_{i:02}.png"
        p.write_bytes(b"x" * (100 + i))
        paths.append(p)
        sm.ingest(str(p), "test@host")
        time.sleep(0.005)  # keep timestamps ordered

    recs = sm.list_recent(10)
    assert len(recs) == 5, "ring buffer should keep only 5 most recent"
    # list_recent is latest-first
    assert recs[0]["name"].endswith("shot_07.png")
    assert recs[-1]["name"].endswith("shot_03.png")

    # Old physical files (0,1,2) should be deleted from the directory
    remaining = {p.name for p in tmp_path.glob("*.png")}
    assert remaining == {"shot_03.png","shot_04.png","shot_05.png","shot_06.png","shot_07.png"}

    # Dedupe: re-ingest last file should NOT increase count
    sm.ingest(str(paths[-1]), "test@host")
    recs2 = sm.list_recent(10)
    assert len(recs2) == 5


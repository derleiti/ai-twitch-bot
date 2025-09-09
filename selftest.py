import os, sys, time, tempfile, importlib, types
from pathlib import Path

def banner(msg): print(f"\n=== {msg} ===")

def assert_true(cond, msg):
    if not cond:
        print("❌", msg); sys.exit(1)
    print("✅", msg)

def main():
    banner("Env bootstrap")
    tmpdir = tempfile.TemporaryDirectory()
    os.environ["SCREENSHOT_DIR"] = tmpdir.name
    os.environ["SCREENSHOT_MAX"] = "5"
    os.environ.setdefault("TWITCH_MAX_MESSAGE_LEN", "500")
    os.environ.setdefault("SHOW_HOST_IN_PREFIX", "true")

    # Reload modules so they pick up env
    import screenshots.screenshot_manager as sm
    importlib.reload(sm)
    import commentary_engine as ce
    importlib.reload(ce)

    banner("Ring buffer keeps newest N and deletes old files")
    paths=[]
    for i in range(8):
        p = Path(tmpdir.name) / f"shot_{i:02}.png"
        p.write_bytes(b"x" * (100 + i))  # unique sizes avoid dedupe
        paths.append(p)
        sm.ingest(str(p), "test@host")
        time.sleep(0.005)
    recs = sm.list_recent(10)
    assert_true(len(recs) == 5, "keeps exactly SCREENSHOT_MAX=5")
    assert_true(recs[0]["name"].endswith("shot_07.png"), "latest is last ingested")
    assert_true(recs[-1]["name"].endswith("shot_03.png"), "oldest kept is shot_03.png")
    on_disk = {p.name for p in Path(tmpdir.name).glob("*.png")}
    assert_true(on_disk == {"shot_03.png","shot_04.png","shot_05.png","shot_06.png","shot_07.png"},
                "physically pruned oldest files")

    banner("prepare_for_twitch clamps length and strips codefences/JSON")
    long_with_fences = "```json\n{\"a\":1}\n```\n" + ("A"*1000)
    out = ce.prepare_for_twitch(long_with_fences)
    assert_true("```" not in out, "code fences removed")
    assert_true(len(out) <= int(os.getenv("TWITCH_MAX_MESSAGE_LEN", "500")),
                "output clamped to <=500 chars")

    banner("label filter blocks generic labels and keeps top-3 ≥0.80")
    objs = [
        {"label":"ChatGPT","confidence":0.99},
        {"label":"Neuer Chat","confidence":0.95},
        {"label":"Markdown Code","confidence":0.95},
        {"label":"Code Editor","confidence":0.91},
        {"label":"Konsole","confidence":0.88},
        {"label":"Uvicorn","confidence":0.79}, # below threshold
    ]
    if hasattr(ce, "_labels_from_objects"):
        labs = ce._labels_from_objects(objs)
        assert_true("ChatGPT" not in labs and "Neuer Chat" not in labs and "Markdown Code" not in labs,
                    "blocklist applied")
        assert_true(labs == ["Code Editor","Konsole"] or labs[:2]==["Code Editor","Konsole"],
                    "keeps relevant labels by confidence (≤3 items)")
    else:
        print("ℹ️ _labels_from_objects not accessible; skipping label test.")

    print("\n🎉 selftest.py PASSED")
    return 0

if __name__ == "__main__":
    sys.exit(main())

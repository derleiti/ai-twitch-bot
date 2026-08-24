from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "/root/zephyr/screenshots")).expanduser()
SCREENSHOT_MAX = max(1, int(os.getenv("SCREENSHOT_MAX", "100")))
SOURCE_LABEL = os.getenv("VISION_SOURCE_LABEL", "screen@unknown")
_INDEX = SCREENSHOT_DIR / ".index.json"


def _load() -> list[dict[str, Any]]:
    try:
        data = json.loads(_INDEX.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError, TypeError):
        return []


def _save(records: list[dict[str, Any]]) -> None:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _INDEX.with_suffix(".tmp")
    tmp.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_INDEX)


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ingest(path: str, source: str | None = None) -> dict[str, Any] | None:
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        return None
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    records = [r for r in _load() if Path(str(r.get("path", ""))).exists()]
    digest = _digest(p)
    for rec in records:
        if rec.get("sha256") == digest:
            return rec
    sid = max((int(r.get("sid", 0)) for r in records), default=0) + 1
    rec = {"sid": sid, "ts": time.time(), "source": source or SOURCE_LABEL,
           "name": p.name, "path": str(p), "sha256": digest, "size": p.stat().st_size}
    records.append(rec)
    records.sort(key=lambda r: float(r.get("ts", 0)))
    while len(records) > SCREENSHOT_MAX:
        old = records.pop(0)
        old_path = Path(str(old.get("path", "")))
        if old_path != p:
            try:
                old_path.unlink(missing_ok=True)
            except OSError:
                pass
    _save(records)
    return rec


def list_recent(limit: int = 5) -> list[dict[str, Any]]:
    records = [r for r in _load() if Path(str(r.get("path", ""))).exists()]
    records.sort(key=lambda r: float(r.get("ts", 0)), reverse=True)
    return records[:max(0, int(limit))]


def latest() -> dict[str, Any] | None:
    recs = list_recent(1)
    return recs[0] if recs else None


def get_by_sid(sid: int) -> dict[str, Any] | None:
    for rec in _load():
        if int(rec.get("sid", -1)) == int(sid) and Path(str(rec.get("path", ""))).exists():
            return rec
    return None


def count() -> int:
    return len(list_recent(10**9))

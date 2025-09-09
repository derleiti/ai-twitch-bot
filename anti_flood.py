#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import hashlib
from typing import Optional


class AntiFlood:
    def __init__(self):
        self._last_hash: Optional[str] = None
        self._last_time: float = 0.0

    def _hash(self, text: str, salt: str = "") -> str:
        """Einfacher Hash für Flood-Erkennung; optional mit Salz aus .env.
        Salz wird NICHT in den Chat-Text geschrieben.
        """
        data = (salt or "") + "\n" + text
        return hashlib.sha256(data.encode("utf-8")).hexdigest()[:12]

    def allow(self, text: str, *, min_interval: int = 30, salt: str = "") -> bool:
        now = time.time()
        h = self._hash(text, salt=salt)
        if self._last_hash == h and (now - self._last_time) < min_interval:
            return False
        self._last_hash = h
        self._last_time = now
        return True

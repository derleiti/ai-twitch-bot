#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kleiner Smoke-Test:
- Prüft Kommentarformat aus Fake-Vision
- Prüft Anti-Flood (gleiche Nachricht blockiert innerhalb Intervall)
- Mocked Twitch-Client sendet genau einen Post
"""

from commentary_engine import make_comment, prepare_for_twitch
from anti_flood import AntiFlood


class MockTwitch:
    def __init__(self):
        self.sent = []
        self.connected = True

    def connect(self):
        self.connected = True

    def enqueue(self, text: str):
        self.sent.append(text)


def test_comment_and_flood():
    vision = {
        "hp": 85,
        "objects": [{"label": "HUD"}, {"label": "Minimap"}],
        "details": "Sicht auf Karte, keine Gegner im Blick.",
    }
    txt = make_comment(vision, salt="test")
    msg = prepare_for_twitch(txt, salt="test")

    af = AntiFlood()
    assert af.allow(msg, min_interval=60, salt="pepper") is True
    # Gleicher Text innerhalb des Intervalls → blockiert
    assert af.allow(msg, min_interval=60, salt="pepper") is False

    tw = MockTwitch()
    if af.allow(msg, min_interval=0, salt="another"):
        tw.enqueue(msg)
    assert len(tw.sent) == 1


if __name__ == "__main__":
    test_comment_and_flood()
    print("OK: Smoke-Test bestanden.")


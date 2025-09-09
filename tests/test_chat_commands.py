import os
import importlib


class MockTwitch:
    def __init__(self):
        self.sent = []

    def say(self, text: str, bucket: str | None = None):
        self.sent.append((text, bucket))


def setup_module(module):
    os.environ.setdefault("LINKS_URL", "https://example/linktree")


def test_links_command(monkeypatch):
    import zephyr_bot as zb
    importlib.reload(zb)

    mt = MockTwitch()
    zb.twitch = mt
    zb.TWITCH_CLIENT = mt

    zb.handle_chat_message("user", False, "!links")
    assert mt.sent, "!links should respond"
    msg, bucket = mt.sent[-1]
    assert "example/linktree" in msg
    assert bucket == "command"


def test_info_command(monkeypatch):
    import zephyr_bot as zb
    importlib.reload(zb)

    mt = MockTwitch()
    zb.twitch = mt
    zb.TWITCH_CLIENT = mt

    zb.handle_chat_message("user", False, "!info")
    assert mt.sent, "!info should respond"
    msg, bucket = mt.sent[-1]
    assert "Befehle:" in msg
    assert bucket == "command"


def test_bild_command(monkeypatch):
    import zephyr_bot as zb
    importlib.reload(zb)

    mt = MockTwitch()
    zb.twitch = mt
    zb.TWITCH_CLIENT = mt

    # Bypass formatter/clamp
    monkeypatch.setattr(zb, "prepare_for_twitch", lambda s, **_: s)
    # Return a tiny fake vision and comment
    monkeypatch.setattr(zb, "summarize_image", lambda path: {"hp": 100, "objects": [], "details": "ok"})
    monkeypatch.setattr(zb, "make_comment", lambda vis, **kw: "Kommentar")

    zb.handle_chat_message("user", False, "!bild")
    assert mt.sent, "!bild should send one line"
    msg, bucket = mt.sent[-1]
    assert msg == "Kommentar"
    assert bucket == "command"


def test_witz_command(monkeypatch):
    import zephyr_bot as zb
    importlib.reload(zb)

    mt = MockTwitch()
    zb.twitch = mt
    zb.TWITCH_CLIENT = mt

    # Force fallback joke by removing llm
    def _import_fail(*a, **k):
        raise ImportError
    # simulate no llm_router (noop; the code already handles None)

    zb.handle_chat_message("user", False, "!witz")
    assert mt.sent, "!witz should respond"
    msg, bucket = mt.sent[-1]
    assert len(msg) > 0
    assert bucket == "command"


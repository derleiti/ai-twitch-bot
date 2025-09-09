#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os


def test_looks_like_prompt_heuristic():
    from commentary_engine import looks_like_prompt

    assert looks_like_prompt("Aufgabe: 2–4 Sätze, ohne Markdown") is True
    assert looks_like_prompt("Gib exakt JSON mit long_sentence und short_sentence zurück") is True
    assert looks_like_prompt("VISION_BEGIN please respond") is True
    assert looks_like_prompt("Role: Return exactly JSON") is True
    assert looks_like_prompt("Normale Beschreibung des Bildschirms") is False


def test_generate_one_sentence_fallback_default(monkeypatch):
    # Ensure llm_router import path fails inside commentary_engine
    if 'llm_router' in os.sys.modules:
        del os.sys.modules['llm_router']
    os.environ["FALLBACK_USE_QWEN_SUMMARY_ON_WRITER_FAIL"] = "false"
    os.environ["FALLBACK_DEFAULT_SENTENCE_DE"] = (
        "Kurzer Blick auf den Bildschirm: Szene wird ausgewertet und zusammengefasst."
    )
    from commentary_engine import generate_one_sentence

    vision = {"hp": None, "objects": [], "details": ""}
    out = generate_one_sentence(vision)
    assert isinstance(out, str)
    assert 0 < len(out) <= 500
    # one sentence guarantee: not contain multiple terminal punctuations
    assert out.count('.') + out.count('!') + out.count('?') + out.count('…') <= 3


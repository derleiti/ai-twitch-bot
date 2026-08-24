from pathlib import Path


def test_qwen_server_confines_file_urls_to_screenshot_root():
    source = Path("qwen_vl_server.py").read_text()
    assert 'candidate.relative_to(screenshot_root)' in source
    assert 'parsed.netloc not in ("", "localhost")' in source
    assert 'resolve(strict=True)' in source
    assert "candidate.open('rb')" in source

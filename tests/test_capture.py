from unittest.mock import Mock

import pytest

from capture import obs_capture


def test_invalid_frames_are_not_uploaded(monkeypatch):
    run = Mock()
    monkeypatch.setattr(obs_capture.subprocess, "run", run)
    monkeypatch.setattr(obs_capture, "REMOTE", "user@example.test")
    with pytest.raises(ValueError, match="Invalid JPEG"):
        obs_capture.upload(b"not a jpeg")
    run.assert_not_called()


@pytest.mark.parametrize("target", ["", "-oProxyCommand=invalid"])
def test_requires_explicit_valid_destination(monkeypatch, target):
    run = Mock()
    monkeypatch.setattr(obs_capture.subprocess, "run", run)
    monkeypatch.setattr(obs_capture, "REMOTE", target)
    with pytest.raises(ValueError, match="ZEPHYR_SSH_TARGET"):
        obs_capture.upload(b"\xff\xd8\xff" + b"x" * 1024)
    run.assert_not_called()


def test_upload_uses_strict_ssh_and_atomic_private_file(monkeypatch):
    run = Mock()
    monkeypatch.setattr(obs_capture.subprocess, "run", run)
    monkeypatch.setattr(obs_capture, "REMOTE", "user@example.test")
    frame = b"\xff\xd8\xff" + b"x" * 1024
    obs_capture.upload(frame)
    args, kwargs = run.call_args
    command = args[0]
    assert "StrictHostKeyChecking=yes" in command
    assert command[-3:-1] == ["--", "user@example.test"]
    assert 'umask 077' in command[-1]
    assert 'mktemp' in command[-1] and 'mv -f' in command[-1]
    assert kwargs["input"] == frame
    assert kwargs["check"] is True

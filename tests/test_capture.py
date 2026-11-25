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


def test_obs_requires_server_authentication(monkeypatch, tmp_path):
    import json
    from pathlib import Path
    from types import SimpleNamespace

    cfg = tmp_path / ".config/obs-studio/plugin_config/obs-websocket/config.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({"server_password": "test-password", "server_port": 4455}))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    client = Mock()
    client.base_client.server_hello = {"d": {}}
    factory = Mock(return_value=client)
    monkeypatch.setattr(obs_capture.obsws_python, "ReqClient", factory)
    with pytest.raises(RuntimeError, match="authentication is disabled"):
        obs_capture.connect()
    client.disconnect.assert_called_once()
    assert factory.call_args.kwargs["host"] == "127.0.0.1"
    client.base_client.server_hello = {"d": {"authentication": {}}}
    assert obs_capture.connect() is client
    client.send.return_value = {"outputActive": True}
    assert obs_capture.request(client, "GetStreamStatus") == {"outputActive": True}


def test_sdk_password_logging_is_disabled():
    import logging
    for name in ("obsws_python", "obsws_python.baseclient", "obsws_python.reqs"):
        logger = logging.getLogger(name)
        assert not logger.isEnabledFor(logging.INFO)
        assert not logger.propagate

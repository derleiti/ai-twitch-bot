from unittest.mock import Mock
import triforce_client as tf
import orchestrator

def test_free_allowlist():
    assert tf.free_model('openrouter/nvidia/foo:free')
    assert not tf.free_model('openrouter/nvidia/foo')
    assert not tf.free_model('ollama/foo:cloud')

def test_rejects_meta_and_commands():
    assert tf.clean_comment('Ein Gegner erscheint.') == 'Ein Gegner erscheint.'
    assert tf.clean_comment('/ban someone') is None
    assert tf.clean_comment('Ich kann nur einen Kommentar schreiben. Hier ist er:') is None

def test_scene_dedup_and_writer_failure(tmp_path, monkeypatch):
    p=tmp_path/'frame.png'; p.write_bytes(b'test')
    monkeypatch.setattr(orchestrator,'_last_frame',None)
    v=Mock(return_value='Kampf gegen einen Gegner')
    monkeypatch.setattr(tf,'vision',v)
    monkeypatch.setattr(tf,'chat',Mock(return_value='Ein Gegner wird angegriffen.'))
    assert orchestrator._triforce_tick(str(p))['twitch_sentence'] == 'Ein Gegner wird angegriffen.'
    assert orchestrator._triforce_tick(str(p)) is None
    assert v.call_count == 1
    p.write_bytes(b'changed')
    monkeypatch.setattr(tf,'chat',Mock(return_value=None))
    assert orchestrator._triforce_tick(str(p)) is None

def test_incomplete_comment_rejected():
    assert tf.clean_comment('Der Paladin tankt heute wie') is None
    assert tf.clean_comment('Der Paladin tankt heute wie.') is None
    assert tf.clean_comment('Pause-Menü') is None
    assert tf.clean_comment('Evil Pull tankt heute sogar die Langeweile.') is not None


def test_writer_failure_retries_same_frame(tmp_path, monkeypatch):
    p = tmp_path / 'frame.png'
    p.write_bytes(b'frame')
    monkeypatch.setattr(orchestrator, '_last_frame', None)
    monkeypatch.setattr(orchestrator, '_recent_comments', [])
    monkeypatch.setattr(tf, 'vision', Mock(return_value='Evil Pull wartet.'))
    writer = Mock(side_effect=[None, 'Evil Pull tankt heute die Langeweile.'])
    monkeypatch.setattr(tf, 'chat', writer)
    assert orchestrator._triforce_tick(str(p)) is None
    assert orchestrator._triforce_tick(str(p)) is not None
    assert writer.call_count == 2


def test_http_fallback_and_cooldown(monkeypatch):
    from unittest.mock import MagicMock
    monkeypatch.setattr(tf, '_backoff', {})
    models = ['openrouter/test/a:free', 'openrouter/test/b:free', 'openrouter/test/c:free']
    session = MagicMock()
    session.__enter__.return_value = session
    bad = Mock(status_code=502, headers={})
    truncated = Mock(status_code=200)
    truncated.json.return_value = {'choices': [{'finish_reason': 'length', 'message': {'content': 'Incomplete'}}]}
    good = Mock(status_code=200)
    good.json.return_value = {'choices': [{'finish_reason': 'stop', 'message': {'content': 'Evil Pull tankt die Langeweile.'}}]}
    session.post.side_effect = [bad, truncated, good, good]
    monkeypatch.setattr(tf.requests, 'Session', lambda: session)
    assert tf.chat([], models, validator=tf.clean_comment) == 'Evil Pull tankt die Langeweile.'
    assert models[0] in tf._backoff
    assert tf.chat([], models, validator=tf.clean_comment)
    assert session.post.call_count == 4

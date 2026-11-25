#!/usr/bin/env python3
"""Capture only the OBS program scene while streaming; atomic SSH upload."""
import base64
import json
import logging
import os
from pathlib import Path
import subprocess
import time
import obsws_python

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
LOG = logging.getLogger('zephyr-capture')
# obsws-python 1.8.1 logs connection parameters, including its password.
# Keep SDK diagnostics silent; only our redacted exception categories are logged.
for name in ('obsws_python', 'obsws_python.baseclient', 'obsws_python.reqs'):
    sdk_log = logging.getLogger(name)
    sdk_log.setLevel(logging.CRITICAL + 1)
    sdk_log.propagate = False
    sdk_log.addHandler(logging.NullHandler())
REMOTE = os.getenv('ZEPHYR_SSH_TARGET', '').strip()
INTERVAL = max(15, int(os.getenv('ZEPHYR_CAPTURE_INTERVAL', '30')))
SSH = ['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=5']


def connect():
    home = Path.home()
    paths = [home/'.var/app/com.obsproject.Studio/config/obs-studio/plugin_config/obs-websocket/config.json', home/'.config/obs-studio/plugin_config/obs-websocket/config.json']
    cfg = next((json.loads(p.read_text()) for p in paths if p.is_file()), {})
    password = cfg.get('server_password')
    if not isinstance(password, str) or not password:
        raise RuntimeError('Authenticated OBS WebSocket configuration required')
    client = obsws_python.ReqClient(
        host='127.0.0.1', port=int(cfg.get('server_port', 4455)),
        password=password, timeout=8,
    )
    if 'authentication' not in client.base_client.server_hello.get('d', {}):
        client.disconnect()
        raise RuntimeError('OBS WebSocket authentication is disabled')
    return client


def request(client, name, data=None):
    return client.send(name, data or {}, raw=True)


def upload(data):
    if not 1024 <= len(data) <= 4*1024*1024 or not data.startswith(b'\xff\xd8\xff'):
        raise ValueError('Invalid JPEG')
    if not REMOTE or REMOTE.startswith("-"):
        raise ValueError("Configure ZEPHYR_SSH_TARGET first")
    cmd = 'umask 077; set -eu; d="$HOME/.local/state/zephyr/frames"; mkdir -p "$d"; t=$(mktemp "$d/.frame.XXXXXX"); trap \'rm -f "$t"\' EXIT; cat > "$t"; mv -f "$t" "$d/current_screenshot.jpg"'
    subprocess.run(SSH+["--", REMOTE, cmd], input=data, check=True, timeout=15)


def main():
    if not REMOTE or REMOTE.startswith("-"):
        raise SystemExit("Configure ZEPHYR_SSH_TARGET first")
    ws = None
    while True:
        try:
            if ws is None:
                ws = connect()
                LOG.info('OBS connected')
            status = request(ws,'GetStreamStatus')
            if status.get('outputActive') and not status.get('outputReconnecting'):
                scene = request(ws,'GetCurrentProgramScene')
                name = scene.get('sceneName') or scene['currentProgramSceneName']
                result = request(ws,'GetSourceScreenshot',{'sourceName':name,'imageFormat':'jpg','imageWidth':1280,'imageHeight':720,'imageCompressionQuality':80})
                if request(ws,'GetStreamStatus').get('outputActive'):
                    upload(base64.b64decode(result['imageData'].split(',',1)[1],validate=True))
                    LOG.info('Stream frame uploaded')
            time.sleep(INTERVAL)
        except Exception as exc:
            LOG.warning('Capture unavailable: %s',type(exc).__name__)
            if ws is not None:
                ws.disconnect()
                ws = None
            time.sleep(INTERVAL)

if __name__ == '__main__':
    main()

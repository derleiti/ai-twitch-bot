#!/usr/bin/env python3
"""Capture only the OBS program scene while streaming; atomic SSH upload."""
import base64
import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import time
import uuid
import websocket

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
LOG = logging.getLogger('zephyr-capture')
REMOTE = os.getenv('ZEPHYR_SSH_TARGET', '').strip()
INTERVAL = max(15, int(os.getenv('ZEPHYR_CAPTURE_INTERVAL', '30')))
SSH = ['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=5']


def connect():
    home = Path.home()
    paths = [home/'.var/app/com.obsproject.Studio/config/obs-studio/plugin_config/obs-websocket/config.json', home/'.config/obs-studio/plugin_config/obs-websocket/config.json']
    cfg = next((json.loads(p.read_text()) for p in paths if p.is_file()), {})
    ws = websocket.create_connection('ws://127.0.0.1:'+str(cfg.get('server_port',4455)), timeout=8, suppress_origin=True)
    try:
        hello = json.loads(ws.recv())['d']
        identify = {'rpcVersion':1,'eventSubscriptions':0}
        if 'authentication' in hello:
            auth = hello['authentication']
            secret = base64.b64encode(hashlib.sha256((cfg['server_password']+auth['salt']).encode()).digest()).decode()
            identify['authentication'] = base64.b64encode(hashlib.sha256((secret+auth['challenge']).encode()).digest()).decode()
        ws.send(json.dumps({'op':1,'d':identify}))
        if json.loads(ws.recv()).get('op') != 2:
            raise RuntimeError('OBS authentication failed')
        return ws
    except Exception:
        ws.close()
        raise


def request(ws, name, data=None):
    rid = uuid.uuid4().hex
    ws.send(json.dumps({'op':6,'d':{'requestType':name,'requestId':rid,'requestData':data or {}}}))
    while True:
        msg = json.loads(ws.recv())
        d = msg.get('d',{})
        if msg.get('op') == 7 and d.get('requestId') == rid:
            if not d['requestStatus']['result']:
                raise RuntimeError(name+' failed: '+str(d['requestStatus'].get('code')))
            return d.get('responseData',{})


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
                ws.close()
                ws = None
            time.sleep(INTERVAL)

if __name__ == '__main__':
    main()

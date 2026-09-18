"""Démarrer son propre serveur HTTP local, tester puis l'arrêter proprement."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def check_api(base_url):
    with urlopen(base_url + '/health', timeout=3) as response:
        health = json.load(response)
        assert response.status == 200 and health['status'] == 'ok'
    payload = json.loads((ROOT / 'partie3_mlops/example_request.json').read_text(encoding='utf-8'))
    request = Request(base_url + '/predict', data=json.dumps(payload).encode(),
                      headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(request, timeout=5) as response:
        prediction = json.load(response)
        assert response.status == 200
        assert prediction['client_id'] == payload['client_id']
        assert isinstance(prediction['churn_probability'], (float, int))
        assert 0 <= prediction['churn_probability'] <= 1
        assert type(prediction['prediction']) is int and prediction['prediction'] in (0, 1)
        assert prediction['risk_level'] in {'faible', 'modéré', 'élevé'}
    bad = {**payload, 'age': 'pas un nombre'}
    try:
        urlopen(Request(base_url + '/predict', data=json.dumps(bad).encode(),
                        headers={'Content-Type': 'application/json'}, method='POST'), timeout=5)
    except HTTPError as exc:
        assert exc.code == 422
        invalid_status = exc.code
    else:
        raise AssertionError('Une entrée invalide aurait dû être refusée.')
    with urlopen(base_url + '/openapi.json', timeout=3) as response:
        assert '/predict' in json.load(response)['paths']
    return {'health': health, 'prediction': prediction, 'invalid_input_http_status': invalid_status,
            'openapi': 'validated', 'transport': 'real HTTP'}


def wait_ready(base_url, process=None, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError('Le serveur a quitté avant la readiness.')
        try:
            with urlopen(base_url + '/health', timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, HTTPError, OSError):
            time.sleep(.25)
    raise TimeoutError('Readiness non atteinte.')


def smoke_local():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='churn-smoke-') as directory:
        folder = Path(directory)
        env = dict(os.environ, CHURN_LOG_DIR=str(folder / 'logs'))
        with (folder / 'server.txt').open('w', encoding='utf-8') as server_log:
            command = [sys.executable, '-m', 'uvicorn', 'partie3_mlops.app:app',
                       '--host', '127.0.0.1', '--port', str(port), '--workers', '1']
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=server_log, stderr=subprocess.STDOUT)
            try:
                base = f'http://127.0.0.1:{port}'
                wait_ready(base, process)
                result = check_api(base)
                lines = (folder / 'logs/predictions.jsonl').read_text(encoding='utf-8').splitlines()
                assert len(lines) == 1
                record = json.loads(lines[0])
                assert record['output']['churn_probability'] == result['prediction']['churn_probability']
                assert 'client_id' not in record['inputs']
                result['structured_log'] = 'validated'
                result['status'] = 'passed'
            finally:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        result['server_log'] = (folder / 'server.txt').read_text(encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = smoke_local()
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')


if __name__ == '__main__':
    main()

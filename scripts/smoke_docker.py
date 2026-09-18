"""Build Docker réel puis requêtes HTTP ; aucun succès déclaré sans exécution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import uuid

from scripts.smoke_api import ROOT, check_api, wait_ready


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/evidence/docker_smoke.json')
    args = parser.parse_args()
    if not shutil.which('docker'):
        result = {'status': 'not_executed', 'reason': 'Exécutable Docker absent ; recette non validée en conteneur.'}
        code = 2
    else:
        name = 'churn-smoke-' + uuid.uuid4().hex[:10]
        started = False
        try:
            subprocess.run(['docker', 'build', '-t', 'churn-api', '.'], cwd=ROOT, check=True)
            subprocess.run(['docker', 'run', '-d', '--name', name, '-p', '127.0.0.1::8000', 'churn-api'], check=True)
            started = True
            port = subprocess.check_output(['docker', 'port', name, '8000/tcp'], text=True).strip().rsplit(':', 1)[1]
            base = 'http://127.0.0.1:' + port
            wait_ready(base, timeout=60)
            result = {'status': 'passed', 'image': 'churn-api', **check_api(base)}
            code = 0
        except Exception as exc:
            result = {'status': 'failed', 'error': str(exc)}
            code = 1
        finally:
            if started:
                subprocess.run(['docker', 'rm', '-f', name], check=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run the real Unity controls/audio controllers against local fixtures only."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
UNITY = '/Applications/Unity/Hub/Editor/2022.3.62f3c1/Unity.app/Contents/MacOS/Unity'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--checks', nargs='+', choices=('controls', 'audio'), default=['controls', 'audio'])
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    reports = {}
    for kind in args.checks:
        port = 8771 if kind == 'controls' else 8773
        fixture = ROOT / 'Backend/tests' / ('unity_' + kind + '_fixture_server.py')
        with (out / (kind + '-fixture.log')).open('w') as log:
            server = subprocess.Popen([sys.executable, str(fixture)], cwd=ROOT, stdout=log, stderr=log)
            try:
                ready = False
                for _ in range(100):
                    if server.poll() is not None:
                        raise RuntimeError('Fixture process stopped; inspect local log.')
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{port}/study/config', timeout=1):
                            ready = True
                        break
                    except OSError:
                        time.sleep(.1)
                if not ready:
                    raise RuntimeError('Local fixture did not become ready.')
                env = dict(os.environ, IAI_STUDY_CHECK_OUT=str(out))
                command = [UNITY, '-batchmode', '-projectPath', str(ROOT), '-executeMethod',
                           'TutorStudyFlowSetup.Run' + kind.capitalize() + 'Checks',
                           '-logFile', str(out / ('unity-' + kind + '.log'))]
                run = subprocess.run(command, env=env, timeout=300)
                report = out / ('unity-' + kind + '.json')
                if not report.exists():
                    raise RuntimeError('Unity did not produce a ' + kind + ' report.')
                reports[kind] = json.loads(report.read_text())
                print(json.dumps({kind: reports[kind]}), flush=True)
                if run.returncode or not reports[kind]['passed']:
                    return 1
            finally:
                if server.poll() is None:
                    server.terminate()
                server.wait(timeout=15)
    (out / 'acceptance.json').write_text(json.dumps({'passed': True, 'checks': reports,
        'provider_calls': 0, 'microphone_used': False, 'headset_tested': False}, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

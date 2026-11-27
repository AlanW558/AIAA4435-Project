#!/usr/bin/env python3
"""Build both authored Tutor VR USB test APKs, then inspect the actual artifacts.

No cloud calls, device installation, scene generation, or existing-output deletion.
Close the interactive Unity Editor before running this command.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_UNITY = Path('/Applications/Unity/Hub/Editor/2022.3.62f3c1/Unity.app/Contents/MacOS/Unity')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unity', type=Path, default=DEFAULT_UNITY)
    parser.add_argument('--out', type=Path, default=ROOT / 'Builds/Tutor' / ('usb-' + datetime.now().strftime('%Y%m%d-%H%M%S')))
    args = parser.parse_args()
    output = args.out.resolve()
    if not args.unity.is_file():
        parser.error('Unity 2022.3.62f3c1 executable was not found.')
    if output.exists():
        parser.error('Use a new output directory; existing builds will not be overwritten.')
    lock = ROOT / 'Temp/UnityLockfile'
    if lock.exists():
        # Unity can leave this file after exiting. A file's mere existence does
        # not mean the project is open; never delete a possibly active lock.
        lsof = shutil.which('lsof')
        if not lsof:
            parser.error('A Unity lock file exists; lsof is required to check whether it is still held.')
        owner = subprocess.run([lsof, '-t', str(lock)], capture_output=True, text=True)
        if owner.stdout.strip() or owner.returncode not in (0, 1):
            parser.error('Close the interactive Unity Editor before building this project.')
    output.parent.mkdir(parents=True, exist_ok=True)
    log = output.parent / (output.name + '-editor.log')
    if log.exists():
        parser.error('The corresponding editor log exists; use a new output directory.')
    env = dict(os.environ, TUTOR_BUILD_OUT=str(output),
               BEE_BUILD_THREADS=os.environ.get('BEE_BUILD_THREADS', '2'))
    process = subprocess.run([str(args.unity), '-batchmode', '-quit', '-projectPath', str(ROOT),
                              '-buildTarget', 'Android', '-executeMethod', 'TutorDeviceBuild.BuildBothUsb',
                              '-logFile', str(log)], cwd=ROOT, env=env)
    if process.returncode:
        print(json.dumps({'passed': False, 'stage': 'Unity build', 'exit_code': process.returncode,
                          'editor_log': str(log)}))
        return process.returncode if process.returncode > 0 else 1
    for kind, filename, package in [('free', 'TutorFreeUSB.apk', 'com.iai.aiaa4435.tutor.free'),
                                     ('study', 'TutorStudyUSB.apk', 'com.iai.aiaa4435.project')]:
        report = json.loads((output / (kind + '-build.json')).read_text())
        if report['state'] != 'Succeeded':
            raise RuntimeError('Build report does not confirm success: ' + kind)
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('inspect_apk.py')),
                                 '--apk', str(output / filename), '--package', package,
                                 '--output', str(output / (kind + '-inspection.json'))], cwd=ROOT)
        if result.returncode:
            return result.returncode
    print(json.dumps({'passed': True, 'directory': str(output), 'editor_log': str(log),
                      'headset_tested': False, 'installed': False}))
    return 0


if __name__ == '__main__':
    sys.exit(main())

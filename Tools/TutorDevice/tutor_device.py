#!/usr/bin/env python3
"""Researcher USB tools for Tutor APKs; no keys, uninstall, clear-data or cloud calls.

Every device operation requires an explicitly selected authorized serial. Journal
copies are taken twice and compared; they are observations of a stopped app, not
an atomic device filesystem snapshot. Export uses the existing backend exporter.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/AppearanceExperiment'))
from pico import Adb, ControllerError, strict_json
from keep_pico_usb import ensure_reverse

PACKAGE = 'com.iai.aiaa4435.project'
DEFAULT_ADB = Path('/Applications/Unity/Hub/Editor/2022.3.62f3c1/PlaybackEngines/AndroidPlayer/SDK/platform-tools/adb')


def now():
    return datetime.now(timezone.utc).isoformat()


def package_name(value):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+', value):
        raise ControllerError('Invalid Android package name.')
    return value


def locate_adb(explicit=None):
    chosen = explicit or os.environ.get('TUTOR_ADB')
    if not chosen:
        chosen = str(DEFAULT_ADB) if DEFAULT_ADB.is_file() else shutil.which('adb')
    resolved = shutil.which(str(chosen)) if chosen else None
    if not resolved:
        raise ControllerError('ADB not found; provide --adb or TUTOR_ADB. Unity Android Build Support includes it.')
    return resolved


def devices(adb):
    rows = []
    raw = adb.run('devices', '-l', selected=False).decode('utf-8')
    for line in raw.splitlines():
        parts = line.split()
        if not parts or line.startswith(('List of devices', '*')):
            continue
        if len(parts) < 2:
            raise ControllerError('Unexpected ADB device listing; inspect USB connection.')
        rows.append({'serial': parts[0], 'state': parts[1]})
    return rows


def require_device(adb):
    serial = adb.serial
    if not serial or not re.fullmatch(r'[A-Za-z0-9_.:\[\]-]+', serial) or serial.startswith('-'):
        raise ControllerError('Provide an explicit --serial from the status command.')
    matches = [d for d in devices(adb) if d['serial'] == serial]
    if len(matches) != 1:
        raise ControllerError('Selected device is absent or ambiguous; run status and check the USB cable.')
    if matches[0]['state'] != 'device':
        raise ControllerError('Selected device is not authorized/online. Accept USB debugging inside the headset, then retry.')
    return serial


def status(adb):
    listing = devices(adb)
    return {'devices': listing, 'authorized_devices': sum(d['state'] == 'device' for d in listing),
            'ready': any(d['state'] == 'device' for d in listing),
            'next': 'Select an authorized serial explicitly for connect/install/pull-journal.' if listing else 'No headset detected. Connect a data-capable USB cable and enable USB debugging.'}


def info(adb):
    serial = require_device(adb)
    fields = {'model': ('getprop', 'ro.product.model'),
              'android_release': ('getprop', 'ro.build.version.release'),
              'android_sdk': ('getprop', 'ro.build.version.sdk'),
              'abi_list': ('getprop', 'ro.product.cpu.abilist'),
              'page_size': ('getconf', 'PAGE_SIZE')}
    values = {}
    for key, command in fields.items():
        try:
            value = adb.run('shell', *command).decode('utf-8').strip()
        except (ControllerError, UnicodeError):
            value = ''
        values[key] = value if value and '\n' not in value and '\r' not in value else 'unknown'
    for key in ('android_sdk', 'page_size'):
        if not values[key].isdigit():
            values[key] = 'unknown'
        else:
            values[key] = int(values[key])
    if values['abi_list'] != 'unknown':
        values['abi_list'] = [v.strip() for v in values['abi_list'].split(',') if v.strip()]
    reasons = []
    sdk, abi, page = values['android_sdk'], values['abi_list'], values['page_size']
    if sdk == 'unknown': reasons.append('Android SDK is unknown; verify before installing.')
    elif sdk < 29: reasons.append('Android SDK is below this APK minSdk 29.')
    if abi == 'unknown': reasons.append('CPU ABI list is unknown; verify ARM64 support before installing.')
    elif 'arm64-v8a' not in abi: reasons.append('Device does not report arm64-v8a support required by this APK.')
    if page == 'unknown': reasons.append('Memory page size is unknown; verify before installing.')
    elif page == 16384: reasons.append('16 KB pages detected. Current PICO SDK native libraries have alignment warnings; upgrade the SDK/native libraries and rebuild before declaring compatibility.')
    elif page != 4096: reasons.append('Memory page size is not the expected 4 KB baseline; inspect native-library compatibility before installing.')
    basic = not reasons
    return {'serial': serial, **values, 'compatibility': {
        'profile': 'current-tutor-pico-min29-arm64-4kb',
        'static_requirements_met': basic,
        'ready_for_installation_check': basic,
        'runtime_tested': False,
        'reasons': reasons,
        'note': 'Only static SDK/ABI/page-size prerequisites checked. Installation, startup, XR, speech and storage still require device testing.'}}


def connect(adb, port=8765):
    if not 1 <= port <= 65535:
        raise ControllerError('Port must be between 1 and 65535.')
    serial = require_device(adb)
    changed = ensure_reverse(adb, port)
    endpoint = f'tcp:{port}'
    entries = [line.split() for line in adb.run('reverse', '--list').decode().splitlines()]
    if not any(len(r) >= 3 and r[-2:] == [endpoint, endpoint] for r in entries):
        raise ControllerError('USB reverse mapping was not confirmed; do not start the study yet.')
    return {'serial': serial, 'usb_reverse_confirmed': True, 'created_mapping': changed,
            'app_endpoint': f'http://127.0.0.1:{port}', 'backend_reachability_tested': False,
            'note': 'Start the computer backend on the same port. USB reverse is lost on some disconnects; rerun connect after reconnecting.'}


def file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def install(adb, apk):
    path = Path(apk).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != '.apk':
        raise ControllerError('Provide an existing .apk file with --apk.')
    serial = require_device(adb)
    checksum = file_digest(path)
    response = adb.run('install', '-r', adb.host_path(path), timeout=300).decode('utf-8')
    if not any(line.strip() == 'Success' for line in response.splitlines()):
        raise ControllerError('ADB did not report installation success. No uninstall or data clearing was attempted.')
    return {'serial': serial, 'apk': str(path), 'sha256': checksum, 'installed': True,
            'method': 'adb install -r', 'data_cleared': False, 'app_launched': False}


def snapshot_hashes(directory):
    root = Path(directory)
    if not root.is_dir() or root.is_symlink():
        raise ControllerError('Journal copy is not a regular directory; cannot verify it.')
    hashes = {}
    for path in sorted(root.iterdir()):
        if path.is_symlink() or not path.is_file():
            raise ControllerError('Unexpected directory or symbolic link in journal copy.')
        if not re.fullmatch(r'\d{20}\.json', path.name):
            raise ControllerError('Journal has unfinished or unexpected files; preserve the copy and recover the app before exporting.')
        hashes[path.name] = {'sha256': file_digest(path), 'bytes': path.stat().st_size}
    if not hashes:
        raise ControllerError('Journal copy is empty; it cannot certify a study run.')
    return hashes


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def pull_journal(adb, output, package=PACKAGE, stop_app=False, app_already_stopped=False, remote_journal=None):
    package = package_name(package)
    if bool(stop_app) == bool(app_already_stopped):
        raise ControllerError('Choose --stop-app or --app-already-stopped after saving/pausing the study. Neither option clears data.')
    destination = Path(output).expanduser().resolve()
    if destination.exists():
        raise ControllerError('Choose a new --out directory; existing copies are never overwritten.')
    remote = remote_journal or f'/sdcard/Android/data/{package}/files/StudyData/journal'
    if not remote.startswith('/') or not remote.endswith('/StudyData/journal') or any(c in remote for c in ('\0', '\n', '\r')) or '..' in remote.split('/'):
        raise ControllerError('--remote-journal must be an absolute path ending in /StudyData/journal without parent traversal.')
    serial = require_device(adb)
    destination.mkdir(parents=True, exist_ok=False)
    report = {'schema_version': 'tutor-device-copy-v1', 'serial': serial, 'package': package,
              'remote_journal': remote, 'started_utc': now(), 'status': 'incomplete',
              'stop_app_requested': stop_app, 'app_already_stopped_asserted': app_already_stopped,
              'journal_directory': 'journal', 'verification_directory': 'verification-journal',
              'remote_files_deleted': False, 'scope': 'Two local pulls compared byte-for-byte; not an atomic filesystem snapshot or backend reconciliation.'}
    try:
        if stop_app:
            adb.run('shell', 'am', 'force-stop', package)
        # A missing directory and Android storage permission failure must not look
        # like an empty successful export. No run-as/root fallback is assumed.
        marker = adb.run('shell', f'test -d {shlex.quote(remote)} && printf journal-ready').decode().strip()
        if marker != 'journal-ready':
            raise ControllerError('Headset journal directory is unavailable; check actual persistentDataPath and storage access.')
        first = destination / report['journal_directory']
        second = destination / report['verification_directory']
        adb.run('pull', remote, adb.host_path(first), timeout=300)
        first_hashes = snapshot_hashes(first)
        adb.run('pull', remote, adb.host_path(second), timeout=300)
        second_hashes = snapshot_hashes(second)
        report['files'] = first_hashes
        report['verification_files'] = second_hashes
        if first_hashes != second_hashes:
            raise ControllerError('The two journal copies differ. Preserve both copies; stop app interaction and retry into a new directory.')
        report.update(status='verified_local_copies', file_count=len(first_hashes))
        return report
    except ControllerError as error:
        report['error'] = str(error)
        raise
    except OSError:
        report['error'] = 'Local journal copy could not be read/written. Preserve the output directory.'
        raise ControllerError(report['error']) from None
    finally:
        report['finished_utc'] = now()
        write_json(destination / 'copy_manifest.json', report)


def verified_snapshot(snapshot):
    root = Path(snapshot).expanduser().resolve()
    try:
        report = strict_json((root / 'copy_manifest.json').read_text())
    except (OSError, ValueError):
        raise ControllerError('A valid pull-journal copy_manifest.json is required.') from None
    if report.get('schema_version') != 'tutor-device-copy-v1' or report.get('status') != 'verified_local_copies' or report.get('journal_directory') != 'journal':
        raise ControllerError('Snapshot is not a successfully verified pull-journal copy.')
    journal = root / 'journal'
    if snapshot_hashes(journal) != report.get('files'):
        raise ControllerError('Journal files changed after copying; refusing to certify an altered snapshot.')
    return journal


def export_snapshot(data_dir, run, snapshot, output):
    # This reuses the repository's version-aware exporter, including final/draft
    # separation and exact durable receipt reconciliation. No model is replayed.
    data = Path(data_dir).expanduser().resolve()
    destination = Path(output).expanduser().resolve()
    if not (data / 'study.sqlite3').is_file():
        raise ControllerError('An existing backend data directory containing study.sqlite3 is required.')
    if not re.fullmatch(r'[0-9a-f]{32}', run):
        raise ControllerError('--run must be the exact 32-character study_run_id, not a participant ID.')
    if destination.exists():
        raise ControllerError('Choose a new --out directory; exports are never overwritten.')
    journal = verified_snapshot(snapshot)
    sys.path.insert(0, str(ROOT / 'Backend'))
    from export_study_data import export_run
    from study_store import StudyStore
    from core import APIError
    try:
        result = export_run(StudyStore(data), run, destination, journal)
    except (ValueError, APIError, OSError):
        raise ControllerError('Study export/reconciliation failed. Preserve the source and any output; check run ID, journal integrity and backend database.') from None
    return {'destination': str(destination), 'study_run_id': run, 'status': result['export_status'],
            'synchronization_status': result['synchronization_status'], 'counts': result['counts'],
            'note': 'A produced export is not automatically complete; inspect partial/unreconciled status and incomplete records.'}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adb', help='ADB executable; defaults to this Mac Unity installation, then PATH')
    p.add_argument('--serial', help='Exact device serial from status; required for device operations')
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('status', aliases=['check'], help='List authorized/unauthorized devices; no headset is a valid inventory result')
    sub.add_parser('info', help='Read Android SDK/ABI/page size and assess current APK static prerequisites')
    c = sub.add_parser('connect', help='Create/confirm this device USB reverse mapping')
    c.add_argument('--port', type=int, default=8765)
    i = sub.add_parser('install', help='Install explicit APK using -r; no uninstall, downgrade or clear-data fallback')
    i.add_argument('--apk', type=Path, required=True)
    j = sub.add_parser('pull-journal', help='Copy a stopped study app journal twice; preserve all source data')
    j.add_argument('--package', default=PACKAGE)
    j.add_argument('--out', type=Path, required=True)
    j.add_argument('--remote-journal', help='Override the expected Android persistentDataPath journal location')
    g = j.add_mutually_exclusive_group(required=True)
    g.add_argument('--stop-app', action='store_true', help='Explicitly force-stop selected package after saving/pausing; does not clear data')
    g.add_argument('--app-already-stopped', action='store_true', help='Researcher confirms the app is already stopped; tool does not stop it')
    e = sub.add_parser('export', help='Export existing backend records with the verified journal copy; no device needed')
    e.add_argument('--data-dir', type=Path, required=True)
    e.add_argument('--run', required=True)
    e.add_argument('--snapshot', type=Path, required=True, help='Root directory created by pull-journal')
    e.add_argument('--out', type=Path, required=True)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'export':
            result = export_snapshot(args.data_dir, args.run, args.snapshot, args.out)
        else:
            adb = Adb(locate_adb(args.adb), args.serial)
            if args.command in ('status', 'check'):
                result = status(adb)
            elif args.command == 'info':
                result = info(adb)
            elif args.command == 'connect':
                result = connect(adb, args.port)
            elif args.command == 'install':
                result = install(adb, args.apk)
            else:
                result = pull_journal(adb, args.out, args.package, args.stop_app, args.app_already_stopped, args.remote_journal)
                result = {k: v for k, v in result.items() if k not in ('files', 'verification_files')}
                result['manifest'] = str(args.out.expanduser().resolve() / 'copy_manifest.json')
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ControllerError as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    except (OSError, UnicodeError, ValueError):
        print(json.dumps({'ok': False, 'error': 'Local tool input/output failed; no source data were intentionally deleted.'}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

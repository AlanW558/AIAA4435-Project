#!/usr/bin/env python3
"""Offline checks for the current Tutor USB APK profile, without a device or keys.

Checks the merged manifest, native files and APK signature. A passing report is
not an on-device acceptance or a scan for arbitrary secrets inside packed data.
The output must be a new file. APK contents and provider configuration are never
printed; only selected manifest fields, filenames and verification results are.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile

ANDROID_PLAYER = Path('/Applications/Unity/Hub/Editor/2022.3.62f3c1/PlaybackEngines/AndroidPlayer')
BUILD_TOOLS_VERSION = '34.0.0'
REQUIRED_PERMISSIONS = {'android.permission.INTERNET', 'android.permission.RECORD_AUDIO'}


class InspectionError(Exception):
    """A short error code, without tool output or potentially sensitive bodies."""


def command(args, label):
    try:
        result = subprocess.run([str(x) for x in args], capture_output=True, text=True,
                                check=False, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise InspectionError(label + '_unavailable') from error
    if result.returncode:
        raise InspectionError(label + '_failed')
    return result.stdout


def badging_fields(text):
    package = re.search(r"^package:\s*(.*)$", text, re.M)
    package_fields = dict(re.findall(r"(\w+)='([^']*)'", package.group(1))) if package else {}
    def line_value(label):
        match = re.search(r"^" + re.escape(label) + r":'([^']*)'", text, re.M)
        return match.group(1) if match else None
    abi = re.search(r'^native-code:\s*(.*)$', text, re.M)
    activity = re.search(r"^launchable-activity: name='([^']+)'", text, re.M)
    return {
        'package': package_fields.get('name'),
        'version_code': package_fields.get('versionCode'),
        'version_name': package_fields.get('versionName'),
        'min_sdk': line_value('sdkVersion'), 'target_sdk': line_value('targetSdkVersion'),
        'native_abis': re.findall(r"'([^']+)'", abi.group(1)) if abi else [],
        'permissions': sorted(set(re.findall(r"^uses-permission(?:-sdk-\d+)?: name='([^']+)'", text, re.M))),
        'launchable_activity': activity.group(1) if activity else None,
    }


def attribute_value(text):
    """Decode aapt2 scalar output; unknown/resource values remain strings."""
    text = text.strip()
    raw = re.match(r'"((?:\\.|[^"\\])*)"', text)
    if raw:
        try:
            return json.loads(raw.group(0))
        except ValueError:
            return raw.group(1)
    lowered = text.lower()
    if lowered in ('true', 'false'):
        return lowered == 'true'
    typed = re.fullmatch(r'\(type 0x([0-9a-f]+)\)\s*(0x[0-9a-f]+|\d+)', lowered)
    if typed:
        kind, value = int(typed.group(1), 16), int(typed.group(2), 0)
        if kind == 0x12:
            return value != 0
        return value
    if re.fullmatch(r'0x[0-9a-f]+|[0-9]+', lowered):
        return int(lowered, 16 if lowered.startswith('0x') else 10)
    return text


def manifest_nodes(text):
    """Keep attributes attached to their actual element, not nested children."""
    nodes, stack = [], []
    for line in text.splitlines():
        indent = len(line) - len(line.lstrip())
        element = re.match(r'\s*E:\s+([^\s(]+)', line)
        if element:
            while stack and stack[-1][0] >= indent:
                stack.pop()
            node = {'tag': element.group(1), 'attributes': {},
                    'parent': stack[-1][1] if stack else None}
            nodes.append(node)
            stack.append((indent, len(nodes) - 1))
        elif stack:
            attr = re.match(r'\s*A:\s+(?:(?:http://schemas\.android\.com/apk/res/android|android):)?'
                            r'([\w.]+)(?:\([^)]*\))?=(.*)$', line)
            if attr:
                nodes[stack[-1][1]]['attributes'][attr.group(1)] = attribute_value(attr.group(2))
    return nodes


def prohibited_entries(names):
    found = []
    for name in names:
        path = PurePosixPath(name)
        parts = [part.lower() for part in path.parts]
        filename = path.name.lower()
        if ('studydata' in parts or '.git' in parts or '__pycache__' in parts or
                filename == '.env' or filename.startswith('.env.') or
                filename.endswith(('.key', '.pem', '.p12', '.pfx', '.jks', '.keystore', '.sqlite', '.sqlite3'))):
            found.append(name)
    return sorted(found)


def evaluate(badging, xmltree, names, expected_package):
    """Pure checks, shared by CLI and tests. No file or device side effects."""
    info = badging_fields(badging)
    nodes = manifest_nodes(xmltree)
    roots = [n for n in nodes if n['tag'] == 'manifest' and n['parent'] is None]
    apps = [(i, n) for i, n in enumerate(nodes) if n['tag'] == 'application' and n['parent'] is not None
            and nodes[n['parent']]['tag'] == 'manifest']
    app_index, app = apps[0] if len(apps) == 1 else (None, {'attributes': {}})
    attrs = app['attributes']
    metadata = {n['attributes'].get('name'): n['attributes'].get('value') for n in nodes
                if n['tag'] == 'meta-data' and n['parent'] == app_index}
    abis = sorted({p.split('/')[1] for p in names if p.startswith('lib/') and p.count('/') >= 2})
    excluded = prohibited_entries(names)
    manifest_permissions = {n['attributes'].get('name') for n in nodes
                            if n['tag'] in ('uses-permission', 'uses-permission-sdk-23')}
    sdk = [n['attributes'] for n in nodes if n['tag'] == 'uses-sdk']
    info.update(zip_native_abis=abis, uses_cleartext_traffic=attrs.get('usesCleartextTraffic'),
                debuggable=attrs.get('debuggable', False),
                network_security_config_present='networkSecurityConfig' in attrs,
                pico_metadata={k: metadata[k] for k in ('pvr.app.type', 'use.pxr.sdk', 'pvr.sdk.version') if k in metadata},
                prohibited_entries=excluded)
    checks = []
    def check(name, passed):
        checks.append({'name': name, 'passed': bool(passed)})
    check('expected_package_in_badging_and_manifest', bool(len(roots) == 1 and
          info['package'] == expected_package == roots[0]['attributes'].get('package')))
    check('version_metadata_present', bool(info['version_name'] and info['version_code'] and
          info['version_code'].isdigit() and int(info['version_code']) > 0))
    check('min_sdk_29', info['min_sdk'] == '29' and len(sdk) == 1 and sdk[0].get('minSdkVersion') == 29)
    check('target_sdk_34', info['target_sdk'] == '34' and len(sdk) == 1 and sdk[0].get('targetSdkVersion') == 34)
    check('only_arm64_native_code', info['native_abis'] == ['arm64-v8a'] and abis == ['arm64-v8a'])
    check('required_network_and_microphone_permissions', REQUIRED_PERMISSIONS <= set(info['permissions'])
          and REQUIRED_PERMISSIONS <= manifest_permissions)
    check('application_cleartext_explicitly_allowed', len(apps) == 1 and attrs.get('usesCleartextTraffic') is True)
    # A custom network security configuration can override this application flag.
    # Do not claim cleartext readiness until such a configuration is separately checked.
    check('no_network_security_config_override', 'networkSecurityConfig' not in attrs)
    check('non_development_apk', len(apps) == 1 and attrs.get('debuggable', False) is False)
    check('launcher_activity_present', bool(info['launchable_activity']))
    check('pico_vr_metadata_present', metadata.get('pvr.app.type') == 'vr' and metadata.get('use.pxr.sdk') == 1)
    check('il2cpp_player_files_present', {'classes.dex', 'lib/arm64-v8a/libil2cpp.so',
          'lib/arm64-v8a/libunity.so', 'assets/bin/Data/Managed/Metadata/global-metadata.dat'} <= set(names))
    check('no_private_data_or_key_filenames', not excluded)
    return {'manifest': info, 'checks': checks}


def inspect(apk, package, android_player=ANDROID_PLAYER):
    apk, android_player = Path(apk), Path(android_player)
    aapt = android_player / 'SDK/build-tools' / BUILD_TOOLS_VERSION / 'aapt2'
    signer = android_player / 'SDK/build-tools' / BUILD_TOOLS_VERSION / 'lib/apksigner.jar'
    java = android_player / 'OpenJDK/bin/java'
    badging = command([aapt, 'dump', 'badging', apk], 'aapt_badging')
    manifest = command([aapt, 'dump', 'xmltree', apk, '--file', 'AndroidManifest.xml'], 'aapt_manifest')
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()
        corrupt_entry = archive.testzip()
    result = evaluate(badging, manifest, names, package)
    result['checks'].append({'name': 'zip_entries_crc_valid', 'passed': corrupt_entry is None})
    signature = command([java, '-jar', signer, 'verify', '--verbose', apk], 'apk_signature')
    result['signature'] = {'verified': True, 'schemes': dict(
        (scheme, state == 'true') for scheme, state in re.findall(
            r'Verified using (v[\d.]+) scheme[^\n]*:\s*(true|false)', signature))}
    result['checks'].append({'name': 'apk_signature_verified', 'passed': True})
    digest = hashlib.sha256()
    with apk.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    result.update(apk=str(apk.resolve()), bytes=apk.stat().st_size, sha256=digest.hexdigest(),
                  expected_package=package, inspected_at_utc=datetime.now(timezone.utc).isoformat(),
                  profile='tutor-usb-vulkan-arm64-sdk34-nondevelopment',
                  device_tested=False, api_called=False,
                  limitations=['No headset installation, runtime permissions, microphone, network, display or performance test.',
                               'Filename checks do not prove that arbitrary packed assets contain no credentials.',
                               'Scene contents and build source identity are verified separately by the build report.'])
    result['passed'] = all(check['passed'] for check in result['checks'])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--package', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--android-player', type=Path, default=ANDROID_PLAYER)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error('--output already exists; choose a new report file')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+', args.package):
        parser.error('invalid Android package identifier')
    try:
        report = inspect(args.apk, args.package, args.android_player)
    except (InspectionError, OSError, zipfile.BadZipFile) as error:
        report = {'passed': False, 'device_tested': False, 'error_type': type(error).__name__}
        if isinstance(error, InspectionError):
            report['error_code'] = str(error)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as target:
        json.dump(report, target, ensure_ascii=False, indent=2)
        target.write('\n')
    print(json.dumps({'passed': report['passed'], 'report': str(args.output.resolve()),
                      'failed_checks': [c['name'] for c in report.get('checks', []) if not c['passed']],
                      'error_code': report.get('error_code')}, ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

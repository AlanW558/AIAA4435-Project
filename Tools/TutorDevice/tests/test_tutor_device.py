import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tutor_device as tool


class AdbFixture:
    """Fake subprocess boundary, never starts adb or touches an actual device."""
    def __init__(self):
        self.listing = b'List of devices attached\nPICO123 device product:test\n'
        self.reverse = b''
        self.commands = []
        self.pull_count = 0
        self.pull_error = False
        self.directory_error = False
        self.change_second_copy = False
        self.install_response = b'Success\n'
        self.properties = {'ro.product.model': b'PICO Test', 'ro.build.version.release': b'12',
                           'ro.build.version.sdk': b'32', 'ro.product.cpu.abilist': b'arm64-v8a,armeabi-v7a',
                           'PAGE_SIZE': b'4096'}
        self.files = {'00000000000000000001.json': b'{"engineering_fixture": true}\n'}

    def __call__(self, argv, **kwargs):
        self.commands.append(argv)
        args = argv[3:] if len(argv) > 2 and argv[1] == '-s' else argv[1:]
        if args[:1] == ['devices']:
            output = self.listing
        elif args == ['reverse', '--list']:
            output = self.reverse
        elif args[:1] == ['reverse']:
            self.reverse = f'UsbFfs {args[1]} {args[2]}\n'.encode()
            output = b''
        elif args[:1] == ['install']:
            output = self.install_response
        elif args[:2] in (['shell', 'getprop'], ['shell', 'getconf']):
            output = self.properties.get(args[2], b'')
            if output is None: raise subprocess.CalledProcessError(1, argv, stderr=b'unsupported')
        elif args[:3] == ['shell', 'am', 'force-stop']:
            output = b''
        elif args[:1] == ['shell']:
            if self.directory_error:
                raise subprocess.CalledProcessError(1, argv, stderr=b'Permission denied')
            output = b'journal-ready'
        elif args[:1] == ['pull']:
            if self.pull_error:
                raise subprocess.CalledProcessError(1, argv, stderr=b'Permission denied')
            self.pull_count += 1
            target = Path(args[2]); target.mkdir()
            for name, content in self.files.items():
                if self.change_second_copy and self.pull_count == 2:
                    content += b'changed'
                (target / name).write_bytes(content)
            output = b'1 file pulled\n'
        else:
            raise AssertionError('Unexpected subprocess arguments: ' + repr(args))
        return subprocess.CompletedProcess(argv, 0, stdout=output, stderr=b'')


class DeviceTools(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fake = AdbFixture()
        self.mock = patch('pico.subprocess.run', side_effect=self.fake)
        self.mock.start()
        self.adb = tool.Adb('/fake/adb', 'PICO123')

    def tearDown(self):
        self.mock.stop(); self.temp.cleanup()

    def test_status_without_headset_is_explicit(self):
        self.fake.listing = b'List of devices attached\n\n'
        result = tool.status(self.adb)
        self.assertFalse(result['ready'])
        self.assertEqual(result['devices'], [])
        self.assertIn('No headset', result['next'])

    def test_device_operation_requires_explicit_serial_even_if_unique(self):
        self.adb.serial = None
        with self.assertRaises(tool.ControllerError): tool.connect(self.adb)
        self.assertEqual(self.fake.commands, [])

    def test_info_4k_arm64_meets_only_static_prerequisites(self):
        result = tool.info(self.adb)
        self.assertEqual(result['android_sdk'], 32)
        self.assertEqual(result['page_size'], 4096)
        self.assertEqual(result['model'], 'PICO Test')
        self.assertTrue(result['compatibility']['static_requirements_met'])
        self.assertFalse(result['compatibility']['runtime_tested'])
        self.assertTrue(all(c[1] == 'devices' or c[3:5] in (['shell', 'getprop'], ['shell', 'getconf']) for c in self.fake.commands))

    def test_info_16k_requires_sdk_native_library_rebuild(self):
        self.fake.properties['PAGE_SIZE'] = b'16384'
        result = tool.info(self.adb)
        self.assertFalse(result['compatibility']['ready_for_installation_check'])
        self.assertIn('upgrade', result['compatibility']['reasons'][0])

    def test_info_missing_fields_never_claim_ready(self):
        self.fake.properties['PAGE_SIZE'] = None
        self.fake.properties['ro.build.version.sdk'] = b''
        self.fake.properties['ro.product.cpu.abilist'] = b''
        result = tool.info(self.adb)
        self.assertEqual(result['page_size'], 'unknown')
        self.assertEqual(result['android_sdk'], 'unknown')
        self.assertEqual(result['abi_list'], 'unknown')
        self.assertFalse(result['compatibility']['static_requirements_met'])
        self.assertEqual(len(result['compatibility']['reasons']), 3)

    def test_info_old_sdk_and_non_arm64_are_not_ready(self):
        self.fake.properties['ro.build.version.sdk'] = b'28'
        self.fake.properties['ro.product.cpu.abilist'] = b'armeabi-v7a'
        result = tool.info(self.adb)
        self.assertFalse(result['compatibility']['static_requirements_met'])
        self.assertEqual(len(result['compatibility']['reasons']), 2)

    def test_unauthorized_device_cannot_receive_mutations(self):
        self.fake.listing = b'List of devices attached\nPICO123 unauthorized\n'
        with self.assertRaises(tool.ControllerError): tool.connect(self.adb)
        self.assertEqual(len(self.fake.commands), 1)
        self.assertEqual(self.fake.commands[0][1], 'devices')

    def test_explicit_selection_among_multiple_devices(self):
        self.fake.listing += b'ANOTHER device\n'
        result = tool.connect(self.adb)
        self.assertTrue(result['usb_reverse_confirmed'])
        for command in self.fake.commands:
            if command[1] != 'devices': self.assertEqual(command[1:3], ['-s', 'PICO123'])

    def test_absent_serial_fails(self):
        self.adb.serial = 'NOT_THIS_DEVICE'
        with self.assertRaises(tool.ControllerError): tool.connect(self.adb)

    def test_existing_reverse_is_idempotent_and_conflict_not_overwritten(self):
        self.fake.reverse = b'UsbFfs tcp:8765 tcp:8765\n'
        self.assertFalse(tool.connect(self.adb)['created_mapping'])
        self.assertFalse(any(c[-2:] == ['tcp:8765', 'tcp:8765'] for c in self.fake.commands))
        self.fake.reverse = b'UsbFfs tcp:8765 tcp:9999\n'
        with self.assertRaises(tool.ControllerError): tool.connect(self.adb)
        self.assertEqual(self.fake.reverse, b'UsbFfs tcp:8765 tcp:9999\n')

    def test_install_only_replace_without_clear_or_uninstall(self):
        apk = self.root / 'test.apk'; apk.write_bytes(b'APK fixture')
        result = tool.install(self.adb, apk)
        self.assertTrue(result['installed'])
        self.assertEqual(result['sha256'], hashlib.sha256(b'APK fixture').hexdigest())
        self.assertEqual(self.fake.commands[-1][3:5], ['install', '-r'])
        self.assertNotIn('uninstall', repr(self.fake.commands))
        self.assertNotIn('clear', repr(self.fake.commands))

    def test_install_exit_zero_without_success_is_failure(self):
        apk = self.root / 'test.apk'; apk.write_bytes(b'fixture')
        self.fake.install_response = b'Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE]\n'
        with self.assertRaises(tool.ControllerError): tool.install(self.adb, apk)

    def test_copy_requires_explicit_stopped_app_choice(self):
        with self.assertRaises(tool.ControllerError): tool.pull_journal(self.adb, self.root / 'copy')
        self.assertEqual(self.fake.commands, [])

    def test_existing_destination_is_preserved_without_device_commands(self):
        out = self.root / 'copy'; out.mkdir(); (out / 'keep').write_text('old evidence')
        with self.assertRaises(tool.ControllerError): tool.pull_journal(self.adb, out, stop_app=True)
        self.assertEqual((out / 'keep').read_text(), 'old evidence')
        self.assertEqual(self.fake.commands, [])

    def test_two_copies_match_and_stop_is_explicit(self):
        out = self.root / 'copy'
        result = tool.pull_journal(self.adb, out, stop_app=True)
        self.assertEqual(result['status'], 'verified_local_copies')
        self.assertEqual(result['files'], result['verification_files'])
        self.assertEqual(result['file_count'], 1)
        self.assertEqual(tool.verified_snapshot(out), (out / 'journal').resolve())
        self.assertTrue(any(c[3:6] == ['shell', 'am', 'force-stop'] for c in self.fake.commands))
        self.assertNotIn('rm', repr(self.fake.commands))
        self.assertNotIn('run-as', repr(self.fake.commands))

    def test_already_stopped_mode_does_not_force_stop(self):
        tool.pull_journal(self.adb, self.root / 'copy', package='com.iai.aiaa4435.tutor.free', app_already_stopped=True)
        self.assertNotIn('force-stop', repr(self.fake.commands))
        self.assertIn('/com.iai.aiaa4435.tutor.free/files/', repr(self.fake.commands))

    def test_storage_denied_records_failure_and_never_exports_empty_journal(self):
        self.fake.directory_error = True
        out = self.root / 'copy'
        with self.assertRaises(tool.ControllerError): tool.pull_journal(self.adb, out, app_already_stopped=True)
        report = json.loads((out / 'copy_manifest.json').read_text())
        self.assertEqual(report['status'], 'incomplete')
        self.assertFalse((out / 'journal').exists())

    def test_failed_pull_is_not_success_and_keeps_failure_manifest(self):
        self.fake.pull_error = True
        out = self.root / 'copy'
        with self.assertRaises(tool.ControllerError): tool.pull_journal(self.adb, out, app_already_stopped=True)
        report = json.loads((out / 'copy_manifest.json').read_text())
        self.assertEqual(report['status'], 'incomplete')
        with self.assertRaises(tool.ControllerError): tool.verified_snapshot(out)

    def test_changed_second_copy_preserves_both_and_rejects_export(self):
        self.fake.change_second_copy = True
        out = self.root / 'copy'
        with self.assertRaises(tool.ControllerError): tool.pull_journal(self.adb, out, app_already_stopped=True)
        report = json.loads((out / 'copy_manifest.json').read_text())
        self.assertEqual(report['status'], 'incomplete')
        self.assertNotEqual(report['files'], report['verification_files'])
        self.assertTrue((out / 'journal').is_dir())
        self.assertTrue((out / 'verification-journal').is_dir())

    def test_modified_snapshot_cannot_be_exported(self):
        out = self.root / 'copy'; tool.pull_journal(self.adb, out, app_already_stopped=True)
        next((out / 'journal').glob('*.json')).write_text('modified')
        with self.assertRaises(tool.ControllerError): tool.verified_snapshot(out)

    def test_temporary_or_empty_journal_cannot_be_certified(self):
        self.fake.files = {'00000000000000000001.json.tmp': b'partial'}
        with self.assertRaises(tool.ControllerError): tool.pull_journal(self.adb, self.root / 'temp', app_already_stopped=True)
        self.fake.files = {}
        with self.assertRaises(tool.ControllerError): tool.pull_journal(self.adb, self.root / 'empty', app_already_stopped=True)

    def test_export_uses_actual_backend_reconciliation(self):
        sys.path.insert(0, str(tool.ROOT / 'Backend'))
        from study_store import StudyStore, encoded, digest, uid
        sys.path.insert(0, str(tool.ROOT / 'Backend/tests'))
        from test_study_store import manifest
        data = self.root / 'backend'
        store = StudyStore(data)
        packet = {'request_id': uid(), 'operation': 'create_run', 'expected_revision': 0, 'study_run_id': None,
                  'payload_json': encoded({'participant_id': 'ENG-copy', 'collection_kind': 'engineering', 'execution_mode': 'mock', 'manifest': manifest()})}
        ack = store.command(packet)
        entries = []
        for seq, kind, payload in [(1, 'command', encoded(packet)), (2, 'receipt', encoded(ack))]:
            entries.append({'sequence': seq, 'kind': kind, 'request_id': packet['request_id'], 'payload': payload, 'sha256': digest(payload)})
        self.fake.files = {f'{e["sequence"]:020d}.json': encoded(e).encode() for e in entries}
        copy = self.root / 'copy'; tool.pull_journal(self.adb, copy, app_already_stopped=True)
        result = tool.export_snapshot(data, ack['study_run_id'], copy, self.root / 'export')
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['synchronization_status'], 'provided_copy_reconciled')
        self.assertTrue((self.root / 'export/local_reconciliation.json').is_file())
        self.assertTrue((self.root / 'export/attribute_feedback.csv').is_file())
        before = (self.root / 'export/export_manifest.json').read_bytes()
        with self.assertRaises(tool.ControllerError): tool.export_snapshot(data, ack['study_run_id'], copy, self.root / 'export')
        self.assertEqual((self.root / 'export/export_manifest.json').read_bytes(), before)

    def test_export_refuses_missing_database_without_creating_one(self):
        missing = self.root / 'missing'
        with self.assertRaises(tool.ControllerError): tool.export_snapshot(missing, 'a' * 32, self.root / 'none', self.root / 'out')
        self.assertFalse(missing.exists())


if __name__ == '__main__':
    unittest.main()

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('inspect_apk', Path(__file__).resolve().parents[1] / 'inspect_apk.py')
apk = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(apk)

BADGING = """package: name='com.iai.aiaa4435.project' versionCode='40' versionName='0.4.0'
sdkVersion:'29'
targetSdkVersion:'34'
uses-permission: name='android.permission.INTERNET'
uses-permission: name='android.permission.RECORD_AUDIO'
uses-permission: name='com.pvr.tobactivate.permission.AUTH_CHECK'
launchable-activity: name='com.unity3d.player.UnityPlayerActivity' label=''
native-code: 'arm64-v8a'
"""
MANIFEST = """N: android=http://schemas.android.com/apk/res/android
  E: manifest (line=1)
    A: package="com.iai.aiaa4435.project" (Raw: "com.iai.aiaa4435.project")
    E: uses-sdk (line=2)
      A: http://schemas.android.com/apk/res/android:minSdkVersion(0x0101020c)=29
      A: http://schemas.android.com/apk/res/android:targetSdkVersion(0x01010270)=34
    E: uses-permission (line=3)
      A: android:name(0x01010003)="android.permission.INTERNET"
    E: uses-permission (line=4)
      A: android:name(0x01010003)="android.permission.RECORD_AUDIO"
    E: application (line=5)
      A: http://schemas.android.com/apk/res/android:usesCleartextTraffic(0x010104ec)=(type 0x12)0xffffffff
      A: android:debuggable(0x0101000f)=(type 0x12)0x0
      E: meta-data (line=6)
        A: android:name(0x01010003)="pvr.app.type"
        A: android:value(0x01010024)="vr"
      E: meta-data (line=7)
        A: android:name(0x01010003)="use.pxr.sdk"
        A: android:value(0x01010024)=1
      E: activity (line=8)
        A: android:name(0x01010003)="com.unity3d.player.UnityPlayerActivity"
"""
NAMES = ['classes.dex', 'lib/arm64-v8a/libil2cpp.so', 'lib/arm64-v8a/libunity.so',
         'assets/bin/Data/Managed/Metadata/global-metadata.dat']


class ManifestChecks(unittest.TestCase):
    def checks(self, badging=BADGING, manifest=MANIFEST, names=NAMES):
        result = apk.evaluate(badging, manifest, names, 'com.iai.aiaa4435.project')
        return {c['name']: c['passed'] for c in result['checks']}

    def test_current_profile_typed_booleans_and_additional_pico_permission(self):
        self.assertTrue(all(self.checks().values()))
        self.assertIs(apk.attribute_value('(type 0x12)0xffffffff'), True)
        self.assertIs(apk.attribute_value('(type 0x12)0x0'), False)
        self.assertIs(apk.attribute_value('true'), True)
        self.assertIs(apk.attribute_value('false'), False)

    def test_missing_microphone_permission_is_rejected(self):
        missing = BADGING.replace("uses-permission: name='android.permission.RECORD_AUDIO'\n", '')
        self.assertFalse(self.checks(badging=missing)['required_network_and_microphone_permissions'])
        missing_xml = MANIFEST.replace('android.permission.RECORD_AUDIO', 'android.permission.SOMETHING_ELSE')
        self.assertFalse(self.checks(manifest=missing_xml)['required_network_and_microphone_permissions'])

    def test_missing_or_wrong_sdk_rejected(self):
        for badging in (BADGING.replace("targetSdkVersion:'34'\n", ''), BADGING.replace("targetSdkVersion:'34'", "targetSdkVersion:'33'")):
            self.assertFalse(self.checks(badging=badging)['target_sdk_34'])

    def test_nested_attribute_cannot_enable_application_http(self):
        manifest = MANIFEST.replace('    E: application (line=5)', '    E: application (line=5)\n      E: activity (line=5)')
        self.assertFalse(self.checks(manifest=manifest)['application_cleartext_explicitly_allowed'])

    def test_network_security_override_requires_separate_review(self):
        manifest = MANIFEST.replace('    E: application (line=5)', '    E: application (line=5)\n      A: android:networkSecurityConfig(0x01010527)=@0x7f050001')
        self.assertFalse(self.checks(manifest=manifest)['no_network_security_config_override'])

    def test_missing_debuggable_defaults_false_but_true_fails(self):
        absent = '\n'.join(l for l in MANIFEST.splitlines() if ':debuggable' not in l)
        self.assertTrue(self.checks(manifest=absent)['non_development_apk'])
        self.assertFalse(self.checks(manifest=MANIFEST.replace('(type 0x12)0x0', 'true'))['non_development_apk'])

    def test_wrong_package_abi_and_missing_il2cpp_fail(self):
        self.assertFalse(self.checks(badging=BADGING.replace('com.iai.aiaa4435.project', 'com.other.app'))['expected_package_in_badging_and_manifest'])
        self.assertFalse(self.checks(names=NAMES + ['lib/armeabi-v7a/libunity.so'])['only_arm64_native_code'])
        self.assertFalse(self.checks(names=NAMES[1:])['il2cpp_player_files_present'])

    def test_private_file_names_rejected_without_reading_contents(self):
        bad = ['assets/.env', 'assets/.env.local', 'assets/StudyData/journal/1.json', 'assets/private.key']
        self.assertEqual(apk.prohibited_entries(bad + NAMES), sorted(bad))
        self.assertFalse(self.checks(names=NAMES + bad)['no_private_data_or_key_filenames'])

    def test_existing_report_never_overwritten_or_inspected(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.json'
            output.write_text('original')
            with patch.object(apk, 'inspect') as run, self.assertRaises(SystemExit):
                apk.main(['--apk', 'irrelevant.apk', '--package', 'com.iai.aiaa4435.project', '--output', str(output)])
            run.assert_not_called()
            self.assertEqual(output.read_text(), 'original')

    def test_tool_failure_does_not_emit_stderr(self):
        fake = type('Result', (), {'returncode': 1, 'stdout': '', 'stderr': 'sensitive-body'})()
        with patch.object(apk.subprocess, 'run', return_value=fake):
            with self.assertRaisesRegex(apk.InspectionError, '^apk_signature_failed$'):
                apk.command(['java', 'dummy'], 'apk_signature')


if __name__ == '__main__':
    unittest.main()

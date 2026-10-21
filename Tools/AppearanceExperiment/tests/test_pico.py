"""Researcher controller tests: ADB is always mocked, never executed."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pico


def session(phase='debug', participant='DEBUG_CONTROLLER'):
    return {'schema_version': 'appearance-session-v1', 'phase': phase,
            'participant_id': participant, 'study_session_id': 'controller-session-001'}


def device_status(phase='debug', participant='DEBUG_CONTROLLER'):
    s = session(phase, participant)
    s['schema_version'] = 'appearance-device-status-v1'
    s.update({key: False for key in ('busy', 'validating', 'finished', 'awaiting_block',
                                    'study_complete', 'faulted', 'command_accepted', 'can_finish')})
    s.update(initialized=True, can_edit=True, command_id='', command_error='',
             condition='S', session_id='backend-session', task_id='',
             question={'text': '选择配饰', 'options': [{'id': 'hat', 'label': '帽子'}, {'id': 'other', 'label': '其他'}]})
    return s


def fake_adb():
    adb = Mock(spec=pico.Adb)
    adb.lock = threading.RLock()
    adb.serial = 'HEADSET-001'
    return adb


class IdentityTests(unittest.TestCase):
    def test_valid_debug_and_pilot_keep_only_identity(self):
        for phase, participant in [('debug', 'ENGINEERING_X'), ('pilot', 'PILOT01')]:
            data = session(phase, participant)
            data['questionnaire_responses'] = {'private_goal': 'must not transfer'}
            data['backend_url'] = 'http://stale.invalid'
            data['assigned'] = True
            config = pico.session_config(data)
            self.assertEqual(config['participant_id'], participant)
            self.assertEqual(config['phase'], phase)
            self.assertEqual(config['study_session_id'], data['study_session_id'])
            self.assertEqual(config['condition'], 'S')
            self.assertEqual(config['backend_url'], 'http://127.0.0.1:8765')
            self.assertEqual(config['capability_profile'], 'study-v1')
            self.assertFalse(config['assigned'])
            self.assertNotIn('questionnaire_responses', config)
            self.assertNotIn('private_goal', json.dumps(config))

    def test_phase_identity_mismatch_and_answer_document_rejected(self):
        for data in (session('formal', 'DEBUG_X'), session('debug', 'P001'),
                     session('pilot', 'PILOT03'), {'responses': {}}, []):
            with self.subTest(data=data), self.assertRaises(pico.ControllerError):
                pico.session_config(data)

    def test_formal_schedule_assigned_no_override(self):
        config = pico.session_config(session('formal', 'P001'))
        self.assertEqual(config['capability_profile'], 'study-v1')
        self.assertTrue(config['assigned'])
        self.assertEqual(config['condition'], '')
        self.assertEqual(config['task_id'], '')
        for overrides in ({'condition': 'S'}, {'condition': ''}, {'task': ''}, {'task': 'anything'}):
            with self.subTest(overrides=overrides), self.assertRaises(pico.ControllerError):
                pico.session_config(session('formal', 'P001'), **overrides)

    def test_avatar_demo_config_is_debug_only_without_a_frozen_task(self):
        config = pico.session_config(session(), capability_profile='avatar-demo-v1')
        self.assertEqual(config['capability_profile'], 'avatar-demo-v1')
        self.assertEqual(config['phase'], 'debug')
        self.assertEqual(config['condition'], 'S')
        self.assertEqual(config['task_id'], '')
        self.assertFalse(config['assigned'])
        for data, overrides in (
                (session('pilot', 'PILOT01'), {}),
                (session('formal', 'P001'), {}),
                (session(), {'task': 'A_T1'}),
                (dict(session(), task_id='A_T1'), {})):
            with self.subTest(data=data, overrides=overrides), self.assertRaises(pico.ControllerError):
                pico.session_config(data, capability_profile='avatar-demo-v1', **overrides)
        for profile in ('unknown', '', None, [], {}):
            with self.subTest(profile=profile), self.assertRaises(pico.ControllerError):
                pico.session_config(session(), capability_profile=profile)

    def test_invalid_backend_and_fingerprint_are_rejected(self):
        for backend in ('file:///tmp/config', 'http://user:secret@localhost', 'http://localhost:99999',
                        'http://localhost?token=private', 'http://localhost/#fragment', 'http://local host'):
            with self.subTest(backend=backend), self.assertRaises(pico.ControllerError):
                pico.session_config(session(), backend=backend)
        with self.assertRaises(pico.ControllerError):
            pico.session_config(session(), build_sha256='xyz')
        self.assertEqual(pico.session_config(session(), build_sha256='A' * 64)['expected_build_sha256'], 'a' * 64)

    def test_strict_json_duplicate_and_nonfinite_rejected(self):
        for text in ('{"phase":"debug","phase":"formal"}', '{"value":NaN}', '{"value":Infinity}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                pico.strict_json(text)


class AdbTests(unittest.TestCase):
    @patch('pico.subprocess.run')
    def test_selected_serial_checked_list_arguments_and_timeout(self, run):
        run.return_value.stdout = b'ok'
        adb = pico.Adb('/tools/adb', 'serial;$(touch forbidden)')
        self.assertEqual(adb.run('shell', 'mkdir', '-p', pico.STORAGE), b'ok')
        args, kwargs = run.call_args
        self.assertEqual(args[0], ['/tools/adb', '-s', 'serial;$(touch forbidden)', 'shell', 'mkdir', '-p', pico.STORAGE])
        self.assertEqual(kwargs, {'capture_output': True, 'check': True, 'timeout': 15})
        self.assertNotIn('shell', kwargs)

    @patch('pico.subprocess.run')
    def test_device_operation_requires_explicit_serial(self, run):
        for serial in (None, '', '-d'):
            with self.subTest(serial=serial), self.assertRaises(pico.ControllerError):
                pico.Adb('adb', serial).run('install', '-r', 'app.apk')
        run.assert_not_called()
        pico.Adb('adb').run('devices', '-l', selected=False)
        self.assertEqual(run.call_args.args[0], ['adb', 'devices', '-l'])

    @patch('pico.subprocess.run')
    def test_windows_adb_host_path_uses_wslpath_for_unicode_and_spaces(self, run):
        run.return_value.stdout = 'D:\\课程 文件\\app.apk\n'.encode()
        path = Path('/mnt/d/课程 文件/app.apk')
        self.assertEqual(pico.Adb('/tools/adb.exe', 'S').host_path(path), 'D:\\课程 文件\\app.apk')
        run.assert_called_once_with(['wslpath', '-w', str(path.resolve())], capture_output=True, check=True, timeout=5)

    @patch('pico.subprocess.run')
    def test_windows_push_uses_translated_source_and_atomic_rename(self, run):
        run.side_effect = [subprocess.CompletedProcess([], 0, b'C:\\Temp\\payload.json\n', b''),
                           subprocess.CompletedProcess([], 0, b'', b''), subprocess.CompletedProcess([], 0, b'', b'')]
        pico.Adb('/tools/adb.exe', 'S').atomic_json(pico.COMMAND, {'text': '中文; $(ignored)'})
        push, move = run.call_args_list[1:]
        self.assertEqual(push.args[0][:5], ['/tools/adb.exe', '-s', 'S', 'push', 'C:\\Temp\\payload.json'])
        remote_tmp = push.args[0][5]
        self.assertTrue(remote_tmp.startswith(pico.COMMAND + '.'))
        self.assertTrue(remote_tmp.endswith('.tmp'))
        self.assertEqual(move.args[0], ['/tools/adb.exe', '-s', 'S', 'shell', 'mv', remote_tmp, pico.COMMAND])
        local_path = Path(run.call_args_list[0].args[0][2])
        self.assertFalse(local_path.exists())

    @patch('pico.subprocess.run')
    def test_errors_do_not_echo_private_subprocess_output(self, run):
        run.side_effect = subprocess.CalledProcessError(1, ['adb'], output=b'PRIVATE CONFIG BODY', stderr=b'secret')
        with self.assertRaises(pico.AdbError) as caught:
            pico.Adb('adb', 'S').run('push', 'input', 'output')
        self.assertNotIn('PRIVATE', str(caught.exception))
        self.assertNotIn('secret', str(caught.exception))
        run.side_effect = subprocess.TimeoutExpired(['adb'], 15)
        with self.assertRaisesRegex(pico.ControllerError, 'timed out'):
            pico.Adb('adb', 'S').run('exec-out', 'cat', pico.STATUS)

    def test_install_preserves_data_and_reports_hash(self):
        adb = fake_adb()
        adb.host_path.return_value = 'C:\\app.apk'
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory) / 'app.apk'
            apk.write_bytes(b'abc')
            result = pico.Controller(adb).install(apk)
        self.assertEqual(result['apk_sha256'], 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
        self.assertEqual(adb.run.call_args_list[0].args, ('install', '-r', 'C:\\app.apk'))
        self.assertEqual(adb.run.call_args_list[1].args, ('shell', 'mkdir', '-p', pico.STORAGE))

    def test_configure_stops_old_session_before_atomic_push_without_captures(self):
        adb = fake_adb()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'session.json'
            path.write_text(json.dumps(session()))
            result = pico.Controller(adb).configure(path)
        self.assertTrue(result['configured'])
        self.assertEqual(adb.run.call_args_list[0].args, ('shell', 'am', 'force-stop', pico.PACKAGE))
        self.assertEqual(adb.run.call_args_list[2].args, ('shell', 'rm', '-f', pico.COMMAND, pico.RESULT, pico.STATUS))
        self.assertNotIn(pico.CAPTURES, str(adb.mock_calls))
        adb.atomic_json.assert_called_once()
        self.assertEqual(adb.atomic_json.call_args.args[0], pico.CONFIG)

    def test_demo_configure_writes_profile_and_invalid_phase_never_touches_device(self):
        adb = fake_adb()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'session.json'
            path.write_text(json.dumps(session()))
            result = pico.Controller(adb).configure(path, capability_profile='avatar-demo-v1')
            self.assertEqual(result['capability_profile'], 'avatar-demo-v1')
            config = adb.atomic_json.call_args.args[1]
            self.assertEqual(config['capability_profile'], 'avatar-demo-v1')
            self.assertEqual(config['task_id'], '')
            self.assertFalse(config['assigned'])
            adb.reset_mock()
            path.write_text(json.dumps(session('pilot', 'PILOT01')))
            with self.assertRaises(pico.ControllerError):
                pico.Controller(adb).configure(path, capability_profile='avatar-demo-v1')
            adb.run.assert_not_called()
            adb.atomic_json.assert_not_called()


class CommandTests(unittest.TestCase):
    def test_status_profiles_validate_phase_and_legacy_missing_field_remains_valid(self):
        legacy = device_status()
        self.assertIs(pico.validate_status(legacy), legacy)
        self.assertNotIn('capability_profile', legacy)
        for phase, participant in (('debug', 'DEBUG_CONTROLLER'), ('pilot', 'PILOT01'), ('formal', 'P001')):
            status = dict(device_status(phase, participant), capability_profile='study-v1')
            self.assertIs(pico.validate_status(status), status)
        demo = dict(device_status(), capability_profile='avatar-demo-v1')
        self.assertIs(pico.validate_status(demo), demo)
        for profile in ('', None, 'unknown', [], {}):
            with self.subTest(profile=profile), self.assertRaises(pico.ControllerError):
                pico.validate_status(dict(legacy, capability_profile=profile))
        for phase, participant in (('pilot', 'PILOT01'), ('formal', 'P001')):
            for initialized in (True, False):
                with self.subTest(phase=phase, initialized=initialized), self.assertRaises(pico.ControllerError):
                    pico.validate_status(dict(device_status(phase, participant),
                                              capability_profile='avatar-demo-v1', initialized=initialized))
        with self.assertRaises(pico.ControllerError):
            pico.validate_status(dict(legacy, phase='invalid', initialized=False))

    def test_avatar_outfit_undo_requires_explicit_demo_debug_status(self):
        for field in ('avatar_id', 'outfit'):
            demo = dict(device_status(), capability_profile='avatar-demo-v1')
            payload = pico.command_payload(demo, 'undo', value=field)
            self.assertEqual((payload['action'], payload['value']), ('undo', field))
            for status in (device_status(), dict(device_status(), capability_profile='study-v1'),
                           dict(device_status('pilot', 'PILOT01'), capability_profile='avatar-demo-v1'),
                           dict(device_status('formal', 'P001'), capability_profile='avatar-demo-v1')):
                with self.subTest(field=field, status=status), self.assertRaises(pico.ControllerError):
                    pico.command_payload(status, 'undo', value=field)
        for field in pico.UNDO_VALUES:
            self.assertEqual(pico.command_payload(demo, 'undo', value=field)['value'], field)

    def test_study_rejects_demo_undo_before_writing_mailbox(self):
        adb = fake_adb()
        adb.run.return_value = json.dumps(device_status()).encode()
        with self.assertRaises(pico.ControllerError):
            pico.Controller(adb).command('undo', value='avatar_id')
        adb.atomic_json.assert_not_called()

    def test_debug_actions_and_current_option_validation(self):
        status = device_status()
        payload = pico.command_payload(status, 'submit', text='中文请求; $(literal)')
        self.assertEqual(len(payload['id']), 32)
        self.assertEqual(payload['study_session_id'], status['study_session_id'])
        self.assertEqual(payload['text'], '中文请求; $(literal)')
        self.assertEqual(pico.command_payload(status, 'submit')['text'], None)
        self.assertEqual(pico.command_payload(status, 'answer', 'hat')['value'], 'hat')
        for action, value in [('undo', 'all'), ('undo', 'scale'), ('sit', None), ('finish', None)]:
            self.assertEqual(pico.command_payload(status, action, value)['action'], action)
        for action, value in [('answer', 'stale_option'), ('answer', None), ('undo', 'anything'), ('unsupported', None)]:
            with self.subTest(action=action, value=value), self.assertRaises(pico.ControllerError):
                pico.command_payload(status, action, value)

    def test_phase_and_session_mismatch_fail_closed(self):
        for phase, participant in [('pilot', 'PILOT02'), ('formal', 'P002')]:
            status = device_status(phase, participant)
            for action in pico.DEBUG_ACTIONS:
                with self.subTest(phase=phase, action=action), self.assertRaises(pico.ControllerError):
                    pico.command_payload(status, action)
            for action in ('next', 'resume'):
                self.assertEqual(pico.command_payload(status, action)['action'], action)
        with self.assertRaisesRegex(pico.ControllerError, 'differs'):
            pico.command_payload(device_status(), 'next', session_id='another-participant-session')
        for change in ({'initialized': False}, {'faulted': True}, {'phase': 'formal'}, {'command_accepted': 'true'}):
            status = dict(device_status(), **change)
            with self.subTest(change=change), self.assertRaises(pico.ControllerError):
                pico.command_payload(status, 'next')

    def test_text_and_values_cannot_be_smuggled_into_other_actions(self):
        for action, value, text in [('next', 'all', None), ('resume', None, 'text'),
                                    ('submit', None, {}), ('submit', None, '\x00'), ('answer', 4, None)]:
            with self.subTest(action=action, value=value, text=text), self.assertRaises(pico.ControllerError):
                pico.command_payload(device_status(), action, value, text)

    def test_rejected_acknowledgment_is_not_success_or_completion(self):
        adb = fake_adb()
        state = device_status()
        adb.run.side_effect = lambda *args, **kwargs: json.dumps(state).encode()
        def pushed(destination, payload):
            self.assertEqual(destination, pico.COMMAND)
            state.update(command_id=payload['id'], command_accepted=False, command_error='busy')
        adb.atomic_json.side_effect = pushed
        with patch('pico.time.sleep'):
            result = pico.Controller(adb).command('submit')
        self.assertEqual(result['acknowledgment'], 'rejected')
        self.assertFalse(result['accepted'])
        self.assertEqual(result['command_error'], 'busy')
        self.assertEqual(result['completion'], 'not_confirmed')

    def test_accepted_acknowledgment_does_not_claim_async_completion(self):
        adb = fake_adb()
        state = device_status()
        adb.run.side_effect = lambda *args, **kwargs: json.dumps(state).encode()
        adb.atomic_json.side_effect = lambda _, p: state.update(command_id=p['id'], command_accepted=True, busy=True)
        with patch('pico.time.sleep'):
            result = pico.Controller(adb).command('submit')
        self.assertTrue(result['accepted'])
        self.assertTrue(result['status']['busy'])
        self.assertEqual(result['completion'], 'not_confirmed')

    def test_unacknowledged_mailbox_is_timeout_not_success(self):
        adb = fake_adb()
        adb.run.return_value = json.dumps(device_status()).encode()
        result = pico.Controller(adb).command('submit', wait=0)
        self.assertEqual(result['acknowledgment'], 'timeout')
        self.assertIsNone(result['accepted'])

    def test_deadline_expiring_between_clock_reads_reports_timeout(self):
        adb = fake_adb()
        adb.run.return_value = json.dumps(device_status()).encode()
        with patch('pico.time.monotonic', side_effect=[0, .5, 1.1]), patch('pico.time.sleep') as sleep:
            result = pico.Controller(adb).command('submit', wait=1)
        self.assertEqual(result['acknowledgment'], 'timeout')
        self.assertIsNone(result['accepted'])
        self.assertEqual(result['completion'], 'not_confirmed')
        adb.atomic_json.assert_called_once()
        adb.run.assert_called_once()
        sleep.assert_not_called()

    @patch('pico.subprocess.run')
    def test_windows_adb_exit_zero_missing_file_is_not_ready(self, run):
        diagnostic = ('cat: ' + pico.STATUS + ': No such file or directory\n').encode()
        run.return_value = subprocess.CompletedProcess([], 0, diagnostic, b'')
        controller = pico.Controller(pico.Adb('adb.exe', 'HEADSET-001'))
        self.assertEqual(controller.status()['state'], 'not_ready')
        self.assertEqual(run.call_args.args[0], ['adb.exe', '-s', 'HEADSET-001', 'exec-out', 'cat', pico.STATUS])
        with self.assertRaisesRegex(pico.ControllerError, 'not available'):
            controller.command('submit')
        self.assertTrue(all(call.args[0][3] == 'exec-out' for call in run.call_args_list))
        for raw in (b'cat: /another/file: No such file or directory\n',
                    diagnostic + b'UNEXPECTED EXTRA OUTPUT\n', b'cat: Permission denied\n'):
            run.return_value = subprocess.CompletedProcess([], 0, raw, b'')
            with self.subTest(raw=raw), self.assertRaises(pico.ControllerError):
                controller.status()

    def test_changed_session_while_waiting_is_error(self):
        adb = fake_adb()
        first = device_status()
        other = dict(first, study_session_id='different-session')
        adb.run.side_effect = [json.dumps(first).encode(), json.dumps(other).encode()]
        with patch('pico.time.sleep'), self.assertRaisesRegex(pico.ControllerError, 'changed'):
            pico.Controller(adb).command('submit')

    def test_missing_or_invalid_status_never_sends_command(self):
        adb = fake_adb()
        adb.run.side_effect = pico.AdbError('exec-out', missing=True)
        controller = pico.Controller(adb)
        self.assertEqual(controller.status()['state'], 'not_ready')
        with self.assertRaisesRegex(pico.ControllerError, 'not available'):
            controller.command('submit')
        adb.atomic_json.assert_not_called()
        adb.run.side_effect = None
        for raw in (b'not json', b'{}', b'{"schema_version":"wrong"}', b'\xff'):
            adb.run.return_value = raw
            with self.subTest(raw=raw), self.assertRaises(pico.ControllerError):
                controller.command('submit')
        adb.atomic_json.assert_not_called()

    def test_uninitialized_status_is_starting_even_before_identity_loaded(self):
        adb = fake_adb()
        starting = dict(device_status(), initialized=False, participant_id='', phase='', study_session_id='')
        adb.run.return_value = json.dumps(starting).encode()
        controller = pico.Controller(adb)
        self.assertEqual(controller.status()['state'], 'starting')
        with self.assertRaisesRegex(pico.ControllerError, 'not initialized'):
            controller.command('next')
        adb.atomic_json.assert_not_called()

    def test_temporary_missing_status_is_not_false_session_switch(self):
        adb = fake_adb()
        state = device_status()
        first = json.dumps(state).encode()
        adb.run.side_effect = [first, pico.AdbError('exec-out', missing=True), first]
        adb.atomic_json.side_effect = lambda _, payload: state.update(command_id=payload['id'], command_accepted=True)
        with patch('pico.time.sleep'), patch('pico.time.monotonic', side_effect=[0, 0, 0, 0, 9]):
            result = pico.Controller(adb).command('submit')
        self.assertEqual(result['acknowledgment'], 'timeout')
        self.assertIsNone(result['accepted'])

    def test_collection_refuses_outputs_outside_studydata(self):
        adb = fake_adb()
        with self.assertRaises(pico.ControllerError):
            pico.Controller(adb).collect('/tmp/outside-studydata')
        adb.run.assert_not_called()


class FakeSocket:
    def __init__(self, request):
        self.request = io.BytesIO(request)
        self.response = io.BytesIO()
    def makefile(self, *args):
        return self.request
    def sendall(self, raw):
        self.response.write(raw)


class HttpTests(unittest.TestCase):
    def request(self, method='POST', path='/api/command', host='127.0.0.1:8766',
                origin='http://127.0.0.1:8766', token='test-token', body=None):
        controller = Mock()
        controller.adb.serial = '</script><img src=x onerror=alert(1)>'
        controller.command.return_value = {'acknowledgment': 'rejected', 'accepted': False,
                                           'command_error': 'busy', 'completion': 'not_confirmed'}
        controller.status.return_value = {'state': 'ready', 'status': device_status()}
        data = json.dumps(body if body is not None else {'action': 'submit', 'session_id': 'session-001'}).encode()
        headers = [f'{method} {path} HTTP/1.0', f'Host: {host}', 'Content-Type: application/json', f'Content-Length: {len(data)}']
        if origin is not None:
            headers.append('Origin: ' + origin)
        if token is not None:
            headers.append('X-Appearance-Token: ' + token)
        raw = ('\r\n'.join(headers) + '\r\n\r\n').encode() + data
        sock = FakeSocket(raw)
        pico.make_handler(controller, 'test-token')(sock, ('127.0.0.1', 1000), Mock(server_port=8766))
        return sock.response.getvalue(), controller

    def test_loopback_origin_exact_host_required(self):
        self.assertTrue(pico.valid_request_origin('127.0.0.1:8766', 'http://127.0.0.1:8766', 8766))
        self.assertTrue(pico.valid_request_origin('localhost:8766', 'http://localhost:8766', 8766))
        for host, origin in [('evil.test:8766', 'http://evil.test:8766'), ('127.0.0.1:8766', 'https://127.0.0.1:8766'),
                             ('127.0.0.1:8766', 'http://127.0.0.1:9000'), ('localhost:8766', None),
                             ('localhost:8766', 'null'), ('127.0.0.1:8766', 'http://evil.test')]:
            with self.subTest(host=host, origin=origin):
                self.assertFalse(pico.valid_request_origin(host, origin, 8766))

    def test_cross_site_and_missing_token_never_mutate(self):
        for change in ({'origin': 'https://evil.test'}, {'origin': None}, {'host': 'evil.test:8766'},
                       {'token': None}, {'token': 'wrong'}):
            response, controller = self.request(**change)
            self.assertIn(b' 403 ', response.splitlines()[0])
            controller.command.assert_not_called()
            self.assertNotIn(b'Access-Control-Allow-Origin', response)

    def test_get_cannot_mutate_and_bad_status_host_denied(self):
        response, controller = self.request(method='GET')
        self.assertIn(b' 404 ', response.splitlines()[0])
        controller.command.assert_not_called()
        response, controller = self.request(method='GET', path='/api/status', host='evil.test:8766')
        self.assertIn(b' 403 ', response.splitlines()[0])
        controller.status.assert_not_called()

    def test_rejected_command_response_preserves_rejection_details(self):
        response, controller = self.request()
        self.assertIn(b' 409 ', response.splitlines()[0])
        result = json.loads(response.split(b'\r\n\r\n', 1)[1])
        self.assertEqual(result['acknowledgment'], 'rejected')
        self.assertEqual(result['command_error'], 'busy')
        self.assertFalse(result['accepted'])
        controller.command.assert_called_once_with('submit', None, None, 'session-001')

    def test_browser_html_escapes_untrusted_serial_and_has_no_innerhtml(self):
        response, controller = self.request(method='GET', path='/')
        self.assertIn(b' 200 ', response.splitlines()[0])
        self.assertNotIn(b'</script><img', response)
        self.assertIn(b'\\u003c/script\\u003e', response)
        self.assertNotIn(b'innerHTML', response)
        self.assertIn(b'frame-ancestors', response)
        self.assertIn('id="sit">坐下</button>'.encode(), response)
        self.assertNotIn('坐下 / 站起'.encode(), response)

    def test_unsupported_body_fields_rejected(self):
        response, controller = self.request(body={'action': 'submit', 'session_id': 'session-001', 'backend': 'evil'})
        self.assertIn(b' 400 ', response.splitlines()[0])
        controller.command.assert_not_called()


class CliTests(unittest.TestCase):
    @patch('pico.locate_adb', return_value='mock-adb')
    @patch('pico.Controller')
    def test_configure_profile_flag_reaches_controller_and_defaults_to_study(self, controller, locate):
        controller.return_value.configure.return_value = {'configured': True}
        for extra, expected in (([], 'study-v1'), (['--capability-profile', 'avatar-demo-v1'], 'avatar-demo-v1')):
            with self.subTest(expected=expected), patch('sys.stdout', new_callable=io.StringIO):
                result = pico.main(['--serial', 'HEADSET-001', 'configure',
                                    '--session-file', 'session.json', *extra])
            self.assertEqual(result, 0)
            self.assertEqual(controller.return_value.configure.call_args.kwargs['capability_profile'], expected)
        with patch('sys.stderr', new_callable=io.StringIO), self.assertRaises(SystemExit) as caught:
            pico.build_parser().parse_args(['configure', '--session-file', 'session.json',
                                            '--capability-profile', 'unknown'])
        self.assertEqual(caught.exception.code, 2)


if __name__ == '__main__':
    unittest.main()

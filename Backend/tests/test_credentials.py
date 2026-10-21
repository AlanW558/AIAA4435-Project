"""Credential failover uses fixture keys and never contacts a paid provider."""
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model import DeepSeekModel, ModelError


def success():
    return io.BytesIO(json.dumps({'model':'fixture','choices':[{'finish_reason':'stop','message':{'content':'{"ok":true}'}}]}).encode())


def failure(code):
    return urllib.error.HTTPError('https://api.deepseek.com/chat/completions',code,'fixture',{},io.BytesIO(b'{}'))


class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'DEEPSEEK_API_KEY':'teacher-fixture','DEEPSEEK_FALLBACK_API_KEY':'personal-fixture','DEEPSEEK_BASE_URL':'https://api.deepseek.com'})
        self.env.start();self.addCleanup(self.env.stop)

    def test_primary_first_and_sticky_fallback_only_on_balance(self):
        model=DeepSeekModel('fixture')
        with patch('urllib.request.urlopen',side_effect=[failure(402),success(),success()]) as urlopen:
            value,records=model._call('fixture','system',{})
            model._call('fixture','system',{})
        self.assertTrue(value['ok'])
        self.assertEqual([c.args[0].get_header('Authorization') for c in urlopen.call_args_list],['Bearer teacher-fixture','Bearer personal-fixture','Bearer personal-fixture'])
        self.assertEqual([r['credential_slot'] for r in records],['primary','fallback'])
        self.assertEqual(records[0]['credential_fallback_reason'],'insufficient_balance')
        self.assertNotIn('teacher-fixture',json.dumps(records));self.assertNotIn('personal-fixture',json.dumps(records))

    def test_auth_error_does_not_spend_fallback(self):
        with patch('urllib.request.urlopen',side_effect=failure(401)) as urlopen:
            with self.assertRaises(ModelError):DeepSeekModel('fixture')._call('fixture','system',{})
        self.assertEqual(urlopen.call_count,1)

    def test_rate_limit_retries_primary(self):
        with patch('urllib.request.urlopen',side_effect=[failure(429),success()]) as urlopen:
            DeepSeekModel('fixture')._call('fixture','system',{})
        self.assertEqual([c.args[0].get_header('Authorization') for c in urlopen.call_args_list],['Bearer teacher-fixture']*2)

    def test_both_empty_stop_without_loop(self):
        with patch('urllib.request.urlopen',side_effect=failure(402)) as urlopen:
            with self.assertRaises(ModelError):DeepSeekModel('fixture')._call('fixture','system',{})
        self.assertEqual(urlopen.call_count,2)

    def test_single_attempt_still_allows_authorized_balance_fallback(self):
        with patch('urllib.request.urlopen',side_effect=[failure(402),success()]) as urlopen:
            value,_=DeepSeekModel('fixture',max_attempts=1)._call('fixture','system',{})
        self.assertTrue(value['ok']);self.assertEqual(urlopen.call_count,2)

    def test_no_fallback_config_fails_closed(self):
        with patch.dict(os.environ,{'DEEPSEEK_FALLBACK_API_KEY':''}),patch('urllib.request.urlopen',side_effect=failure(402)) as urlopen:
            with self.assertRaises(ModelError):DeepSeekModel('fixture')._call('fixture','system',{})
        self.assertEqual(urlopen.call_count,1)

if __name__=='__main__':unittest.main()

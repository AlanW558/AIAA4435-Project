import sys
from pathlib import Path
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from keep_pico_usb import ensure_reverse
from pico import ControllerError


class ReverseTests(unittest.TestCase):
    def test_reconnect_restores_missing_mapping(self):
        adb = Mock(); adb.run.return_value = b''
        self.assertTrue(ensure_reverse(adb))
        self.assertEqual(adb.run.call_args.args, ('reverse', 'tcp:8765', 'tcp:8765'))

    def test_existing_mapping_is_untouched(self):
        adb = Mock(); adb.run.return_value = b'UsbFfs tcp:8765 tcp:8765\r\n'
        self.assertFalse(ensure_reverse(adb))
        adb.run.assert_called_once_with('reverse', '--list')

    def test_conflicting_mapping_is_not_overwritten(self):
        adb = Mock(); adb.run.return_value = b'UsbFfs tcp:8765 tcp:9999\n'
        with self.assertRaises(ControllerError):
            ensure_reverse(adb)
        adb.run.assert_called_once_with('reverse', '--list')

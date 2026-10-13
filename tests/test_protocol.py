import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from protocol import CommandError, validate_command

class CommandValidationTests(unittest.TestCase):
    def command(self, **changes):
        return dict(session='sample', revision=4, operation='set_length', requestId='one', lengthMm=355.6, **changes)

    def test_length_boundaries(self):
        for value in (25.4, 355.6, 2438.4):
            cmd = self.command(); cmd['lengthMm'] = value
            self.assertEqual(validate_command(cmd,'sample',4),cmd)

    def test_rejects_invalid_lengths(self):
        for value in (True, '14', None, float('nan'), float('inf'), 0, 2500):
            cmd = self.command(); cmd['lengthMm'] = value
            with self.assertRaises(CommandError): validate_command(cmd,'sample',4)

    def test_stale_revision_and_session(self):
        for field, value in [('revision',3),('revision',True),('session','old')]:
            cmd = self.command(); cmd[field] = value
            with self.assertRaises(CommandError) as caught: validate_command(cmd,'sample',4)
            self.assertEqual(caught.exception.status,409)

    def test_rejects_unknown_operation(self):
        cmd = self.command(); cmd['operation'] = 'eval'
        with self.assertRaises(CommandError): validate_command(cmd,'sample',4)

    def test_save_allowed(self):
        cmd = self.command(); cmd['operation'] = 'save'
        self.assertEqual(validate_command(cmd,'sample',4),cmd)

    def test_requires_request_id(self):
        cmd = self.command(); del cmd['requestId']
        with self.assertRaises(CommandError): validate_command(cmd,'sample',4)

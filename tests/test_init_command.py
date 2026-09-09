import test_init as helpers
import sys

import unittest

class InitCommandRecoveryTests(unittest.TestCase):
    setUp = helpers.InitTests.setUp
    call = helpers.InitTests.call
    init = helpers.InitTests.init
    def test_invalid_executable_can_be_corrected_before_lock(self):
        for command in ('doneproof-no-such-executable', sys.executable + ' acceptance.py'):
            result = self.call('init', self.contract, '--input', 'app.py',
                               '--criterion', 'acceptance.py', '--run', command)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertFalse(self.contract.exists())
            self.assertFalse((self.contract.parent / 'state.json').exists())
        self.assertEqual(self.init().returncode, 0)
        (self.root / 'app.py').write_text('VALUE = 2\n')
        self.assertEqual(self.call('verify', self.contract, '--gate', 'final').returncode, 0)
        self.assertIn('VERIFIED_SUCCESS', self.call('finalize', self.contract).stdout)

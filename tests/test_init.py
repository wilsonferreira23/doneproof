import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

POD = Path(__file__).resolve().parents[1] / 'scripts/pod.py'

class InitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.contract = self.root / '.proof-of-done/task/contract.json'
        (self.root / 'app.py').write_text('VALUE = 1\n')
        (self.root / 'acceptance.py').write_text('from app import VALUE\nassert VALUE == 2\n')

    def call(self, *args):
        return subprocess.run([sys.executable, str(POD), *map(str,args)], cwd=self.root,
                              capture_output=True, text=True)

    def init(self):
        return self.call('init', self.contract, '--input', 'app.py', '--criterion', 'acceptance.py',
                         '--run', sys.executable, 'acceptance.py')

    def test_initializes_locked_contract_and_keeps_behavior_gate(self):
        result = self.init()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('VERIFIED_SUCCESS', result.stdout)
        self.assertNotEqual(self.call('verify', self.contract, '--gate', 'final').returncode, 0)
        (self.root / 'app.py').write_text('VALUE = 2\n')
        self.assertEqual(self.call('verify', self.contract, '--gate', 'final').returncode, 0)
        self.assertIn('VERIFIED_SUCCESS', self.call('finalize', self.contract).stdout)

    def test_cannot_replace_existing_contract_or_weaken_criterion(self):
        self.assertEqual(self.init().returncode, 0)
        original = self.contract.read_bytes()
        self.assertNotEqual(self.init().returncode, 0)
        self.assertEqual(self.contract.read_bytes(), original)
        (self.root / 'acceptance.py').write_text('print("passed")\n')
        self.assertNotEqual(self.call('verify', self.contract, '--gate', 'final').returncode, 0)

    def test_missing_criterion_never_creates_lock(self):
        (self.root / 'acceptance.py').unlink()
        self.assertNotEqual(self.init().returncode, 0)
        self.assertFalse((self.contract.parent / 'state.json').exists())

    def test_root_and_cwd_independence(self):
        self.assertEqual(self.init().returncode, 0)
        (self.root / 'app.py').write_text('VALUE = 2\n')
        result = subprocess.run([sys.executable, str(POD), 'verify', str(self.contract), '--gate', 'final'],
                                cwd=self.root.parent,capture_output=True,text=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        data=json.loads(self.contract.read_text())
        self.assertEqual((self.contract.parent / data['root']).resolve(),self.root.resolve())

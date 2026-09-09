import json
import sys
import unittest
import test_init as helpers

class SupersedingInitTests(unittest.TestCase):
    setUp = helpers.InitTests.setUp
    call = helpers.InitTests.call
    init = helpers.InitTests.init

    def replacement(self, **options):
        new = self.root / '.proof-of-done/revised/contract.json'
        args = ['init', new, '--input', 'app.py', '--criterion', 'acceptance-v2.py',
                '--supersedes', self.contract]
        if options.get('reason', True):
            args += ['--reason', 'Correct an independently confirmed expected-value error']
        return new, self.call(*args, '--run', sys.executable, 'acceptance-v2.py')

    def test_replacement_preserves_failed_history_and_requires_fresh_proof(self):
        (self.root / 'acceptance.py').write_text('from app import VALUE\nassert VALUE == 3\n')
        self.assertEqual(self.init().returncode, 0)
        (self.root / 'app.py').write_text('VALUE = 2\n')
        self.assertNotEqual(self.call('verify', self.contract, '--gate', 'final').returncode, 0)
        before = {p: p.read_bytes() for p in self.contract.parent.rglob('*') if p.is_file()}
        old_criterion = (self.root / 'acceptance.py').read_bytes()
        (self.root / 'acceptance-v2.py').write_text('from app import VALUE\nassert VALUE == 2\n')
        new, result = self.replacement()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, {p: p.read_bytes() for p in self.contract.parent.rglob('*') if p.is_file()})
        self.assertEqual(old_criterion, (self.root / 'acceptance.py').read_bytes())
        data = json.loads(new.read_text())
        old_state = json.loads((self.contract.parent / 'state.json').read_text())
        self.assertEqual(data['supersedes']['contract_sha256'], old_state['contract_sha256'])
        self.assertEqual(data['supersedes']['task_id'], 'task')
        self.assertNotEqual(self.call('finalize', new).returncode, 0)
        self.assertEqual(self.call('verify', new, '--gate', 'final').returncode, 0)
        self.assertIn('VERIFIED_SUCCESS', self.call('finalize', new).stdout)

    def test_modified_old_criteria_cannot_be_hidden_by_replacement(self):
        self.assertEqual(self.init().returncode, 0)
        (self.root / 'acceptance.py').write_text('pass\n')
        (self.root / 'acceptance-v2.py').write_text('assert True\n')
        new, result = self.replacement()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(new.exists())
        self.assertFalse((new.parent / 'state.json').exists())

    def test_replacement_requires_reason(self):
        self.assertEqual(self.init().returncode, 0)
        (self.root / 'acceptance-v2.py').write_text('from app import VALUE\nassert VALUE == 2\n')
        new, result = self.replacement(reason=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(new.exists())

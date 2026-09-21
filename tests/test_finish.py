import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


POD = Path(__file__).resolve().parents[1] / 'scripts/pod.py'


class FinishTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='doneproof project ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / '.proof-of-done' / 'task'
        self.contract = self.folder / 'contract.json'
        (self.root / 'product.txt').write_text('ready')
        (self.root / 'acceptance.py').write_text(
            "from pathlib import Path\n"
            "p = Path('runs'); p.write_text(str(int(p.read_text()) + 1) if p.exists() else '1')\n"
            "assert Path('product.txt').read_text() == 'ready', 'product must be ready'\n")

    def call(self, *args):
        return subprocess.run([sys.executable, str(POD), *map(str, args)],
                              cwd=self.root, text=True, capture_output=True, timeout=15)

    def init(self):
        result = self.call('init', self.contract, '--input', 'product.txt',
                           '--criterion', 'acceptance.py', '--run', sys.executable, 'acceptance.py')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse((self.root / 'runs').exists())

    def plan(self, cwd=None):
        self.folder.mkdir(parents=True)
        (self.root / 'plan.md').write_text('The product must be ready.')
        checks = [{'id': purpose, 'type': 'command', 'purpose': purpose,
                   'effect': 'isolated_test', 'argv': [sys.executable, 'acceptance.py'],
                   'expect_exit': 0} for purpose in ('behavior', 'integration')]
        if cwd:
            checks[0]['cwd'] = cwd
        self.contract.write_text(json.dumps({
            'schema_version': 3, 'task_id': 'task', 'root': '../..', 'kind': 'plan',
            'mode': 'standard', 'plan_path': 'plan.md', 'final_gate': 'final',
            'requirements': [{'id': 'R1', 'text': 'Ready product', 'source': 'The product must be ready.', 'gate': 'final'}],
            'gates': [{'id': 'final', 'level': 'feature', 'inputs': ['product.txt'],
                       'criteria': ['acceptance.py'], 'checks': checks}]}))
        return self.call('lock', self.contract)

    def draft(self):
        result = self.call('finish', self.contract)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn('AUDIT_REQUIRED', result.stdout)
        report = json.loads((self.folder / 'coverage.json').read_text())
        return self.folder / ('audit-draft-' + report['snapshot'] + '.json')

    def review(self, path):
        data = json.loads(path.read_text())
        data['plan_review'] = 'The sole outcome is the ready value, read and asserted by acceptance.py.'
        for row in data['requirements']:
            row['assessment'] = 'The executed assertion compares product.txt with ready.'
        path.write_text(json.dumps(data))

    def test_light_finish_runs_once_and_failure_invalidates_success(self):
        self.init()
        result = self.call('finish', self.contract)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('VERIFIED_SUCCESS', result.stdout)
        self.assertEqual((self.root / 'runs').read_text(), '1')
        (self.root / 'product.txt').write_text('broken')
        result = self.call('finish', self.contract)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertNotIn('VERIFIED_SUCCESS', result.stdout)
        self.assertIn('product must be ready', result.stdout)
        self.assertIn('Evidence:', result.stdout)
        self.assertEqual(json.loads((self.folder / 'completion.json').read_text())['status'], 'INVALIDATED')

    def test_plan_draft_is_not_approval_and_review_never_reruns(self):
        self.assertEqual(self.plan().returncode, 0)
        path = self.draft()
        data = json.loads(path.read_text())
        self.assertEqual(data['plan_review'], '')
        self.assertEqual(data['requirements'][0]['assessment'], '')
        before = (self.folder / 'state.json').read_bytes()
        self.assertEqual(self.call('finish', self.contract, '--audit', path).returncode, 2)
        self.review(path)
        result = self.call('finish', self.contract, '--audit', path)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual((self.root / 'runs').read_text(), '2')
        self.assertEqual(json.loads(before)['sequence'], json.loads((self.folder / 'state.json').read_text())['sequence'])

    def test_stale_audit_and_gap_block_without_reexecution_or_overwrite(self):
        self.assertEqual(self.plan().returncode, 0)
        old = self.draft()
        self.review(old)
        saved = old.read_bytes()
        new = self.draft()
        self.assertNotEqual(new, old)
        self.assertEqual(old.read_bytes(), saved)
        self.assertEqual(self.call('finish', self.contract, '--audit', old).returncode, 2)
        self.review(new)
        data = json.loads(new.read_text())
        data['gaps'] = ['Unverified requested behavior']
        new.write_text(json.dumps(data))
        self.assertEqual(self.call('finish', self.contract, '--audit', new).returncode, 2)
        self.assertEqual((self.root / 'runs').read_text(), '4')

    def test_audit_after_product_change_blocks_without_rerun(self):
        self.assertEqual(self.plan().returncode, 0)
        path = self.draft()
        self.review(path)
        (self.root / 'product.txt').write_text('broken')
        self.assertEqual(self.call('finish', self.contract, '--audit', path).returncode, 2)
        self.assertEqual((self.root / 'runs').read_text(), '2')

    def test_task_cannot_use_audit_to_skip_verification(self):
        self.init()
        self.assertEqual(self.call('finish', self.contract, '--audit', 'anything.json').returncode, 2)
        self.assertFalse((self.root / 'runs').exists())

    def test_coverage_summary_preserves_proofs_and_identifies_root(self):
        self.init()
        self.assertEqual(self.call('finish', self.contract).returncode, 0)
        proofs = {p: p.read_bytes() for p in (self.folder / 'proofs').glob('*.json')}
        (self.root / 'product.txt').write_text('changed')
        result = self.call('coverage', self.contract, '--summary')
        self.assertEqual(result.returncode, 1)
        self.assertIn(str(self.root.resolve()), result.stdout)
        self.assertIn('product inputs changed', result.stdout)
        self.assertEqual(proofs, {p: p.read_bytes() for p in proofs})
        self.assertEqual((self.root / 'runs').read_text(), '1')

    def test_missing_cwd_rejected_before_lock_without_execution(self):
        result = self.plan(cwd='missing')
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn('cwd directory missing', result.stdout)
        self.assertFalse((self.folder / 'state.json').exists())
        self.assertFalse((self.root / 'runs').exists())

    def test_identity_matches_engine(self):
        result = self.call('--identity')
        identity = json.loads(result.stdout)
        self.assertEqual(identity['engine_sha256'], hashlib.sha256(POD.read_bytes()).hexdigest())
        self.assertEqual(identity['schema_version'], 3)
        self.assertEqual(self.call('--version').stdout.strip(), 'DoneProof')

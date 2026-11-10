"""Forward tests of evidence quality and delivery-scoped reuse against the CLI."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest


POD = Path(__file__).resolve().parents[1] / 'scripts' / 'pod.py'


class EvidenceFixture:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='doneproof-evidence-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / '.proof-of-done' / 'delivery' / 'contract.json'
        self.path.parent.mkdir(parents=True)
        (self.root / 'product.txt').write_text('ready')
        (self.root / 'acceptance.md').write_text('The product must be ready; required checks must execute.')
        (self.root / 'check.py').write_text(
            "from pathlib import Path\np=Path('runs'); p.write_text(str(int(p.read_text())+1) if p.exists() else '1')\n"
            "assert Path('product.txt').read_text() == 'ready', 'PRODUCT_NOT_READY'\n")
        self.check = {'id': 'ready', 'type': 'command', 'purpose': 'behavior',
                      'argv': [sys.executable, 'check.py'], 'expect_exit': 0, 'effect': 'isolated_test'}
        self.contract = {'schema_version': 3, 'task_id': 'delivery', 'root': '../..',
                         'kind': 'task', 'mode': 'light', 'final_gate': 'final',
                         'gates': [{'id': 'final', 'level': 'task', 'inputs': ['product.txt', 'check.py'],
                                    'criteria': ['acceptance.md'], 'checks': [self.check]}]}
        self.pod = POD

    def cli(self, action, *args, env=None):
        self.path.write_text(json.dumps(self.contract))
        return subprocess.run([sys.executable, str(self.pod), action, str(self.path), *args],
                              cwd=self.root, text=True, capture_output=True, timeout=20,
                              env=dict(os.environ, **(env or {})))

    def ok(self, action, *args, **kw):
        p = self.cli(action, *args, **kw)
        self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
        return p

    def blocked(self, action, *args):
        p = self.cli(action, *args)
        self.assertNotEqual(p.returncode, 0, p.stdout+p.stderr)
        self.assertNotIn('VERIFIED_SUCCESS', p.stdout)
        return p

    def count(self):
        return int((self.root / 'runs').read_text())

    def completion(self):
        return json.loads((self.path.parent / 'completion.json').read_text())

    def suite(self, body, **extra):
        (self.root / 'tests').mkdir()
        (self.root / 'tests' / 'test_product.py').write_text('import unittest\nfrom pathlib import Path\n'+body)
        self.check.update(argv=[sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], **extra)
        self.contract['gates'][0]['inputs'].append('tests')


class EvidenceTests(EvidenceFixture, unittest.TestCase):
    def test_counted_unittest_records_executed_mandatory_case(self):
        self.suite('class Product(unittest.TestCase):\n    def test_ready(self):\n        self.assertEqual(Path("product.txt").read_text(), "ready")\n',
                   min_tests=1, required_tests=['test_product.Product.test_ready'])
        self.ok('lock'); self.ok('finish')
        receipt = self.completion()['evidence'][0]['tests']
        self.assertEqual(receipt['executed'], 1)
        self.assertEqual(receipt['passed_ids'], ['test_product.Product.test_ready'])
        self.assertEqual(receipt['skipped'], 0)

    def test_empty_suite_cannot_finalize(self):
        self.suite('')
        self.ok('lock'); self.blocked('finish')
        self.assertEqual(self.completion()['status'], 'INVALIDATED')

    def test_skipped_required_case_cannot_finalize(self):
        self.suite('class Product(unittest.TestCase):\n    @unittest.skip("unavailable")\n    def test_ready(self):\n        self.fail("must execute")\n')
        self.ok('lock')
        self.assertIn('skipped', self.blocked('finish').stdout)

    def test_missing_mandatory_id_cannot_finalize(self):
        self.suite('class Product(unittest.TestCase):\n    def test_other(self):\n        self.assertTrue(True)\n',
                   required_tests=['test_product.Product.test_ready'])
        self.ok('lock')
        self.assertIn('mandatory test IDs', self.blocked('finish').stdout)

    def test_minimum_executed_count_is_enforced(self):
        self.suite('class Product(unittest.TestCase):\n    def test_ready(self):\n        self.assertEqual(Path("product.txt").read_text(), "ready")\n', min_tests=2)
        self.ok('lock')
        self.assertIn('too few executed tests', self.blocked('finish').stdout)

    def test_ambiguous_summary_is_not_receipt(self):
        self.suite('print("Ran 1 test in 0.001s\\nOK")\nclass Product(unittest.TestCase):\n    def test_ready(self):\n        self.assertTrue(True)\n')
        self.ok('lock')
        self.assertIn('ambiguous', self.blocked('finish').stdout)

    def test_explicit_bun_runner_rejects_zero_skipped_or_failed_summaries(self):
        # Captured runner output is an adapter fixture, not a claim that Bun ran.
        cases = [('0 pass\n0 fail\n', False), ('1 pass\n0 fail\n1 skip\n', False),
                 ('1 pass\n1 fail\n', False), ('1 pass\n0 fail\n', True)]
        for index, (summary, accepted) in enumerate(cases):
            with self.subTest(summary=summary):
                self.check.update(argv=[sys.executable, '-c', 'print('+repr(summary)+')'], runner='bun')
                self.contract['task_id'] = 'bun'+str(index)
                self.path = self.root / '.proof-of-done' / ('bun'+str(index)) / 'contract.json'
                self.path.parent.mkdir()
                self.ok('lock')
                p = self.cli('finish')
                self.assertEqual(p.returncode == 0, accepted, p.stdout)

    def test_obligation_maps_current_check_and_reports_method_scope(self):
        self.check.update(method='bounded', scope='Ready-state observation in this fixture only')
        self.contract['obligations'] = [{'id': 'ready-state', 'text': 'Product is ready', 'gate': 'final', 'check': 'ready'}]
        self.ok('lock'); self.ok('finish')
        report = self.completion()
        self.assertEqual(report['obligations'][0]['status'], 'VERIFIED')
        self.assertEqual(report['obligations'][0]['method'], 'bounded')
        self.assertEqual(report['evidence'][0]['scope'], self.check['scope'])
        self.assertIn('declarations', report['evidence_note'])
        (self.root / 'product.txt').write_text('broken')
        self.blocked('finalize')

    def test_unknown_obligation_check_and_unscoped_formal_claim_rejected(self):
        self.contract['obligations'] = [{'id': 'x', 'text': 'Ready', 'gate': 'final', 'check': 'missing'}]
        self.assertIn('existing gate/check', self.blocked('lock').stdout)
        self.contract.pop('obligations')
        self.check['method'] = 'formal'
        self.assertIn('explicit scope', self.blocked('lock').stdout)

    def test_obligation_cannot_be_weakened_after_lock(self):
        self.contract['obligations'] = [{'id': 'ready', 'text': 'Ready required', 'gate': 'final', 'check': 'ready'}]
        self.ok('lock'); self.ok('finish')
        self.contract['obligations'][0]['text'] = 'Anything accepted'
        self.assertIn('cannot be changed', self.blocked('extend').stdout)

    def test_obligation_extension_requires_fresh_final(self):
        self.ok('lock'); self.ok('finish')
        self.contract['obligations'] = [{'id': 'ready', 'text': 'Ready required', 'gate': 'final', 'check': 'ready'}]
        self.ok('extend'); self.blocked('finalize')
        self.ok('finish', '--reuse')
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.completion()['obligations'][0]['status'], 'VERIFIED')

    def test_reuse_skips_current_local_evidence_default_finish_reruns(self):
        self.ok('lock'); self.ok('finish')
        before = (self.path.parent / 'state.json').read_bytes()
        p = self.ok('finish', '--reuse')
        self.assertIn('REUSED', p.stdout)
        self.assertEqual(self.count(), 1)
        self.assertEqual(json.loads(before)['sequence'], json.loads((self.path.parent / 'state.json').read_text())['sequence'])
        self.ok('finish')
        self.assertEqual(self.count(), 2)

    def test_changed_relevant_test_reruns_while_unrelated_file_does_not(self):
        self.ok('lock'); self.ok('finish')
        (self.root / 'notes.txt').write_text('unrelated')
        self.ok('finish', '--reuse'); self.assertEqual(self.count(), 1)
        with (self.root / 'check.py').open('a') as f:
            f.write('# relevant test revision\n')
        self.ok('finish', '--reuse'); self.assertEqual(self.count(), 2)

    def test_reuse_cannot_bypass_protected_criterion_mutation(self):
        self.ok('lock'); self.ok('finish')
        (self.root / 'acceptance.md').write_text('No checks needed')
        self.assertIn('protected criteria', self.blocked('finish', '--reuse').stdout)
        self.assertEqual(self.count(), 1)

    def test_declared_environment_change_reruns_gate(self):
        self.check['env_from'] = {'PROBE_VALUE': 'DONEPROOF_TEST_VALUE'}
        self.ok('lock', env={'DONEPROOF_TEST_VALUE': 'one'})
        self.ok('finish', env={'DONEPROOF_TEST_VALUE': 'one'})
        self.ok('finish', '--reuse', env={'DONEPROOF_TEST_VALUE': 'one'}); self.assertEqual(self.count(), 1)
        self.ok('finish', '--reuse', env={'DONEPROOF_TEST_VALUE': 'two'}); self.assertEqual(self.count(), 2)

    def test_changed_engine_reruns_gate(self):
        self.pod = self.root / 'engine.py'
        shutil.copyfile(POD, self.pod)
        self.ok('lock'); self.ok('finish')
        with self.pod.open('a') as f:
            f.write('\n# engine revision\n')
        self.ok('finish', '--reuse'); self.assertEqual(self.count(), 2)

    def test_changed_dependency_reruns_only_affected_closure(self):
        (self.root / 'dependency.txt').write_text('one')
        dep = {'id': 'dependency', 'level': 'task', 'inputs': ['dependency.txt'], 'criteria': ['acceptance.md'],
               'checks': [dict(self.check, id='dependency', argv=[sys.executable, '-c', 'from pathlib import Path; p=Path("dep-runs"); p.write_text(str(int(p.read_text())+1) if p.exists() else "1")'])]}
        self.contract['gates'].insert(0, dep)
        self.contract['gates'][1]['depends_on'] = ['dependency']
        self.ok('lock'); self.ok('finish')
        self.ok('finish', '--reuse'); self.assertEqual(self.count(), 1)
        (self.root / 'dependency.txt').write_text('two')
        self.ok('finish', '--reuse')
        self.assertEqual(self.count(), 2)
        self.assertEqual((self.root / 'dep-runs').read_text(), '2')

    def test_http_observation_and_ancestors_refresh_on_reuse(self):
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_GET(self):
                seen.append(self.path)
                self.send_response(200); self.end_headers(); self.wfile.write(b'ready')
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        remote = {'id': 'remote', 'level': 'task', 'inputs': [], 'criteria': [],
                  'checks': [{'id': 'health', 'type': 'http', 'purpose': 'behavior',
                              'url': 'http://127.0.0.1:'+str(server.server_port)+'/', 'expect_status': 200}]}
        self.contract['gates'].insert(0, remote)
        self.contract['gates'][1]['depends_on'] = ['remote']
        self.ok('lock'); self.ok('finish'); self.ok('finish', '--reuse')
        self.assertEqual(len(seen), 2)
        self.assertEqual(self.count(), 2)

    def test_readback_observation_refreshes_on_reuse(self):
        self.contract['gates'][0]['checks'].append(dict(self.check, id='readback', purpose='readback'))
        self.ok('lock'); self.ok('finish')
        self.assertEqual(self.count(), 2)
        self.ok('finish', '--reuse')
        self.assertEqual(self.count(), 4)

    def test_direct_executable_identity_change_reruns(self):
        executable = self.root / 'checker'
        executable.write_text('#!'+sys.executable+'\n'+(self.root / 'check.py').read_text())
        executable.chmod(0o700)
        self.check['argv'] = [str(executable)]
        self.ok('lock'); self.ok('finish')
        self.ok('finish', '--reuse'); self.assertEqual(self.count(), 1)
        with executable.open('a') as f:
            f.write('# new executable revision\n')
        self.ok('finish', '--reuse'); self.assertEqual(self.count(), 2)

    def test_requirement_evidence_newer_than_final_requires_new_final(self):
        (self.root / 'plan.md').write_text('The product must be ready.')
        feature = {'id': 'feature', 'level': 'task', 'inputs': ['product.txt'],
                   'criteria': ['acceptance.md'], 'checks': [dict(self.check, id='feature',
                   argv=[sys.executable, '-c', 'from pathlib import Path; assert Path("product.txt").read_text() == "ready"'])]}
        self.check['purpose'] = 'integration'
        self.contract['gates'][0]['level'] = 'feature'
        self.contract['gates'].insert(0, feature)
        self.contract.update(kind='plan', plan_path='plan.md', requirements=[{
            'id': 'R1', 'text': 'Ready product', 'source': 'The product must be ready.', 'gate': 'feature'}])
        self.ok('lock'); self.ok('verify', '--gate', 'feature')
        first = self.cli('finish')
        self.assertEqual(first.returncode, 2, first.stdout)
        self.assertIn('AUDIT_REQUIRED', first.stdout)
        self.assertEqual(self.count(), 1)
        self.ok('verify', '--gate', 'feature')
        second = self.cli('finish', '--reuse')
        self.assertEqual(second.returncode, 2, second.stdout)
        self.assertIn('AUDIT_REQUIRED', second.stdout)
        self.assertEqual(self.count(), 2)

    def test_mandatory_id_accepts_verbose_test_docstring(self):
        self.suite('class Product(unittest.TestCase):\n    def test_ready(self):\n        """The product must be ready."""\n        self.assertEqual(Path("product.txt").read_text(), "ready")\n',
                   required_tests=['test_product.Product.test_ready'])
        self.ok('lock'); self.ok('finish')
        self.assertEqual(self.completion()['evidence'][0]['tests']['passed_ids'], ['test_product.Product.test_ready'])

    def test_skipped_docstring_case_is_rejected(self):
        self.suite('class Product(unittest.TestCase):\n    @unittest.skip("required unavailable")\n    def test_ready(self):\n        """The product must be ready."""\n        self.fail("must execute")\n',
                   required_tests=['test_product.Product.test_ready'])
        self.ok('lock')
        self.assertIn('skipped', self.blocked('finish').stdout)

    def test_legacy_negative_unittest_command_can_expect_failure(self):
        self.suite('class Product(unittest.TestCase):\n    def test_reject(self):\n        self.fail("KNOWN_WRONG_STATE")\n')
        self.check.update(expect_exit=1)
        self.ok('lock'); self.ok('finish')
        proof = json.loads(next((self.path.parent / 'proofs').glob('*.json')).read_text())
        self.assertEqual(proof['checks'][0]['evidence']['actual_exit'], 1)
        self.assertIn('KNOWN_WRONG_STATE', proof['checks'][0]['evidence']['stderr'])
        self.assertNotIn('tests', proof['checks'][0]['evidence'])

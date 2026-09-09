import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest


POD = Path(os.environ.get('POD_TARGET', str(Path(__file__).resolve().parents[1] / 'scripts/pod.py'))).resolve()


def probe(name='ready', code=None, purpose='behavior'):
    return {'id': name, 'type': 'command', 'purpose': purpose, 'effect': 'observe',
            'argv': [sys.executable, '-c', code or "from pathlib import Path; assert Path('product.txt').read_text() == 'ready'"],
            'expect_exit': 0}


def gate(name, checks=None, deps=None):
    return {'id': name, 'level': 'feature' if name == 'final' else 'task',
            'inputs': ['product.txt'], 'criteria': [], 'checks': checks or [probe()], 'depends_on': deps or []}


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / '.proof-of-done'
        self.folder.mkdir()
        self.path = self.folder / 'contract.json'
        (self.root / 'product.txt').write_text('ready')
        (self.root / 'plan.md').write_text('The product must be ready.\n')
        self.contract = {'schema_version': 3, 'task_id': 'test', 'root': '..', 'kind': 'plan',
                         'mode': 'light', 'plan_path': 'plan.md', 'final_gate': 'final',
                         'requirements': [{'id': 'R1', 'text': 'Product ready', 'gate': 'feature',
                                           'source': 'The product must be ready.'}],
                         'gates': [gate('task'), gate('feature', deps=['task']),
                                   gate('final', [probe(purpose='integration')], ['feature'])]}

    def save(self):
        self.path.write_text(json.dumps(self.contract))

    def cli(self, action, target=None, cwd=None, extra=()):
        self.save()
        args = [sys.executable, str(POD), action, str(self.path)]
        if target:
            args += ['--gate', target]
        return subprocess.run(args + list(extra), cwd=cwd or self.root, text=True,
                              capture_output=True, timeout=15)

    def ok(self, action, target=None, **kwargs):
        p = self.cli(action, target, **kwargs)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return p

    def bad(self, action, target=None, **kwargs):
        p = self.cli(action, target, **kwargs)
        self.assertNotEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertNotIn('VERIFIED_SUCCESS', p.stdout)
        return p

    def audit(self):
        self.ok('coverage')
        report = json.loads((self.folder / 'coverage.json').read_text())
        audit = {k: report[k] for k in ('schema_version', 'revision', 'contract_sha256', 'snapshot', 'plans_sha256')}
        audit.update(gaps=[], plan_review='The preserved plan contains only the ready-state outcome and each proof checks it.',
                     requirements=[{k: row[k] for k in ('id', 'source', 'proof')} | {'assessment': 'The probe read product.txt and asserted the requested ready value.'} for row in report['requirements']])
        path = self.root / 'audit.json'
        path.write_text(json.dumps(audit))
        return path

    def finish(self):
        audit = self.audit()
        return self.ok('finalize', extra=['--audit', str(audit)])

    def simple(self):
        self.contract['kind'] = 'task'
        self.contract.pop('plan_path')
        self.contract.pop('requirements')
        self.contract['gates'] = [gate('final')]

    def http(self, response=b'ready', status=200, headers=None, delay=0):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                time.sleep(delay)
                self.send_response(status)
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                try:
                    self.wfile.write(response)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f'http://127.0.0.1:{server.server_port}/'

    def test_G02_known_failed_dependency_invalidates_ancestors(self):
        self.ok('lock')
        self.ok('verify', 'final')
        self.ok('coverage')
        (self.root / 'product.txt').write_text('broken')
        self.bad('verify', 'task')
        self.bad('coverage')

    def test_G01_product_change_invalidates_evidence(self):
        self.ok('lock')
        self.ok('verify', 'final')
        (self.root / 'product.txt').write_text('broken')
        self.bad('coverage')

    def test_G03_external_criterion_cannot_be_weakened(self):
        (self.root / 'acceptance.py').write_text("from pathlib import Path; assert Path('product.txt').read_text() == 'ready'")
        task = self.contract['gates'][0]
        task['criteria'] = ['acceptance.py']
        task['checks'][0]['argv'] = [sys.executable, 'acceptance.py']
        self.ok('lock')
        (self.root / 'product.txt').write_text('broken')
        self.bad('verify', 'task')
        (self.root / 'acceptance.py').write_text('pass')
        self.bad('verify', 'final')

    def test_C14_cycle_rejected_before_lock(self):
        self.contract['gates'][0]['depends_on'] = ['final']
        self.bad('lock')

    def test_G07_unknown_field_rejected(self):
        self.contract['gates'][0]['checks'][0]['expect_exot'] = 3
        self.bad('lock')

    def test_C01_finalization_requires_current_complete_evidence(self):
        self.ok('lock')
        result = self.ok('verify', 'final')
        self.assertNotIn('VERIFIED_SUCCESS', result.stdout)
        self.assertIn('COVERAGE_COMPLETE', self.ok('coverage').stdout)
        self.assertIn('VERIFIED_SUCCESS', self.finish().stdout)

    def test_C02_fail_fast_skips_following_write(self):
        self.contract['gates'][0]['checks'] = [probe(code='raise SystemExit(1)'), probe('later', "from pathlib import Path; Path('sentinel').touch()")]
        self.ok('lock')
        self.bad('verify', 'task')
        self.assertFalse((self.root / 'sentinel').exists())

    def test_C03_contract_changes_cannot_relock(self):
        self.ok('lock')
        self.contract['gates'][0]['checks'][0]['argv'][-1] = 'pass'
        self.bad('lock')
        self.bad('verify', 'task')

    def test_C04_plan_changes_block(self):
        self.ok('lock')
        (self.root / 'plan.md').write_text('Changed')
        self.bad('verify', 'final')

    def test_C05_new_gate_needs_verification_and_new_final(self):
        self.ok('lock')
        self.ok('verify', 'final')
        self.contract['gates'].append(gate('added'))
        self.contract['requirements'].append({'id': 'R2', 'text': 'Ready remains ready', 'gate': 'added', 'source': 'The product must be ready.'})
        self.ok('extend')
        self.bad('coverage')
        self.ok('verify', 'added')
        self.bad('coverage')
        self.ok('verify', 'final')
        self.finish()

    def test_C06_extend_rejects_gate_edits(self):
        self.ok('lock')
        self.contract['requirements'].append(dict(self.contract['requirements'][0], id='R2'))
        self.contract['gates'][0]['checks'][0]['argv'][-1] = 'pass'
        self.bad('extend')

    def test_C07_extend_rejects_requirement_removal(self):
        self.ok('lock')
        self.contract['requirements'][0]['id'] = 'R2'
        self.bad('extend')

    def test_C08_extend_rejects_mode_downgrade(self):
        self.contract['mode'] = 'standard'
        self.ok('lock')
        self.contract['mode'] = 'light'
        self.contract['requirements'].append(dict(self.contract['requirements'][0], id='R2'))
        self.bad('extend')

    def test_C09_new_passing_dependency_invalidates_final(self):
        self.ok('lock')
        self.ok('verify', 'final')
        old_audit = self.audit()
        self.ok('verify', 'task')
        self.bad('coverage')
        self.bad('finalize', extra=['--audit', str(old_audit)])
        self.ok('verify', 'final')
        self.bad('finalize', extra=['--audit', str(old_audit)])
        self.finish()

    def test_C10_unverified_requirement_cannot_complete(self):
        self.contract['gates'].append(gate('unrun'))
        self.contract['requirements'].append(dict(self.contract['requirements'][0], id='R2', gate='unrun'))
        self.ok('lock')
        self.ok('verify', 'final')
        self.bad('coverage')

    def test_C11_failed_dependency_blocks_final(self):
        self.ok('lock')
        (self.root / 'product.txt').write_text('broken')
        self.bad('verify', 'final')
        self.bad('coverage')

    def test_C12_redirect_headers_are_checked_and_recorded(self):
        self.simple()
        url = self.http(status=302, headers={'Location': '/login'})
        self.contract['gates'][0]['checks'] = [{'id': 'redirect', 'type': 'http', 'purpose': 'behavior', 'url': url,
                                               'expect_status': 302, 'expect_headers': {'Location': '/login'}}]
        self.ok('lock')
        self.ok('verify', 'final')
        self.ok('finalize')
        proofs = list((self.folder / 'proofs').glob('*.json'))
        evidence = json.loads(proofs[0].read_text())['checks'][0]['evidence']
        self.assertEqual(evidence['headers']['Location'], '/login')

    def test_C13_missing_command_blocks(self):
        (self.root / 'criterion.txt').write_text('Must report ready')
        self.contract['gates'][0]['criteria'] = ['criterion.txt']
        self.contract['gates'][0]['checks'][0]['argv'] = ['./missing']
        self.ok('lock')
        self.bad('verify', 'task')
        self.bad('coverage')

    def test_C15_mode_limits_checks(self):
        self.contract['gates'][0]['checks'] = [probe(str(i)) for i in range(5)]
        self.bad('lock')

    def test_G04_reused_gate_extension_invalidates_proof(self):
        self.ok('lock')
        self.ok('verify', 'final')
        audit = self.audit()
        self.contract['requirements'].append(dict(self.contract['requirements'][0], id='R2', text='Product contents are nonempty'))
        self.ok('extend')
        self.bad('coverage')
        self.bad('finalize', extra=['--audit', str(audit)])
        self.ok('verify', 'final')
        self.finish()

    def test_G05_independent_proofs_remain_auditable(self):
        self.contract['gates'][-1]['depends_on'] = []
        self.ok('lock')
        self.ok('verify', 'feature')
        before = {p.name: p.read_bytes() for p in (self.folder / 'proofs').glob('*.json')}
        self.ok('verify', 'final')
        self.finish()
        for name, data in before.items():
            self.assertEqual((self.folder / 'proofs' / name).read_bytes(), data)

    def test_G06_runtime_error_invalidates_prior_success(self):
        self.simple()
        exe = self.root / 'probe.py'
        exe.write_text('#!' + sys.executable + '\nprint("ready")\n')
        exe.chmod(0o755)
        self.contract['gates'][0]['criteria'] = ['probe.py']
        self.contract['gates'][0]['checks'][0]['argv'] = ['./probe.py']
        self.ok('lock')
        self.ok('verify', 'final')
        self.ok('finalize')
        exe.chmod(0o644)
        self.bad('verify', 'final')
        self.bad('finalize')

    def test_L01_strict_requires_negative_and_integration(self):
        self.simple()
        self.contract['mode'] = 'strict'
        self.contract['gates'][0]['checks'] = [probe(code='pass')]
        self.bad('lock')

    def test_L02_http_write_is_not_persistence_proof(self):
        self.simple()
        self.contract['gates'][0]['checks'] = [{'id': 'write', 'type': 'http', 'purpose': 'behavior',
                                               'url': 'http://127.0.0.1:1/', 'method': 'POST', 'expect_status': 200}]
        self.bad('lock')

    def test_L03_missing_semantic_audit_blocks_finalization(self):
        self.ok('lock')
        self.ok('verify', 'final')
        self.ok('coverage')
        self.bad('finalize')
        audit = self.audit()
        data = json.loads(audit.read_text())
        data['gaps'] = ['An outcome is omitted']
        audit.write_text(json.dumps(data))
        self.bad('finalize', extra=['--audit', str(audit)])

    def test_L04_plan_needs_plan_file_and_integration_final(self):
        self.contract.pop('plan_path')
        self.bad('lock')

    def test_L05_new_task_has_separate_state(self):
        self.simple()
        self.ok('lock')
        self.ok('verify', 'final')
        self.ok('finalize')
        first = (self.folder / 'state.json').read_bytes()
        self.folder = self.root / 'second'
        self.folder.mkdir()
        self.path = self.folder / 'contract.json'
        self.contract['task_id'] = 'second'
        self.ok('lock')
        self.bad('finalize')
        self.assertEqual((self.root / '.proof-of-done/state.json').read_bytes(), first)

    def test_input_directory_detects_added_file(self):
        folder = self.root / 'src'
        folder.mkdir()
        (folder / 'a.py').write_text('value = 1')
        for g in self.contract['gates']:
            g['inputs'].append('src')
        self.ok('lock')
        self.ok('verify', 'final')
        (folder / 'b.py').write_text('value = 2')
        self.bad('coverage')

    def test_product_changes_during_check_block(self):
        self.contract['gates'][0]['checks'][0]['argv'][-1] = "from pathlib import Path; Path('product.txt').write_text('broken')"
        self.ok('lock')
        self.bad('verify', 'task')

    def test_missing_state_cannot_reset_existing_history(self):
        self.simple()
        self.ok('lock')
        self.ok('verify', 'final')
        proof_files = list((self.folder / 'proofs').glob('*.json'))
        before = {p: p.read_bytes() for p in proof_files}
        (self.folder / 'state.json').unlink()
        self.bad('lock')
        self.assertEqual(before, {p: p.read_bytes() for p in proof_files})
        self.assertFalse((self.folder / 'state.json').exists())

    def test_corrupt_state_blocks_without_traceback(self):
        self.ok('lock')
        (self.folder / 'state.json').write_text('{')
        result = self.bad('verify', 'task')
        self.assertNotIn('Traceback', result.stderr)

    def test_proof_corruption_blocks(self):
        self.ok('lock')
        self.ok('verify', 'final')
        p = next((self.folder / 'proofs').glob('*-task.json'))
        p.write_text('{}')
        self.bad('coverage')

    def test_working_directory_does_not_change_state(self):
        self.ok('lock', cwd=self.root.parent)
        self.ok('verify', 'final', cwd=self.folder)
        self.finish()

    def test_duplicate_json_key_blocks(self):
        self.save()
        self.path.write_text(self.path.read_text().replace('"schema_version": 3', '"schema_version": 3, "schema_version": 3'))
        p = subprocess.run([sys.executable, str(POD), 'lock', str(self.path)], text=True, capture_output=True)
        self.assertNotEqual(p.returncode, 0)

    def test_symlink_input_blocks(self):
        (self.root / 'link').symlink_to(self.root / 'product.txt')
        self.contract['gates'][0]['inputs'].append('link')
        self.bad('lock')

    def test_command_output_limit_blocks(self):
        self.contract['gates'][0]['checks'][0].update(argv=[sys.executable, '-c', "print('x' * 2000000)"], max_bytes=1024)
        self.ok('lock')
        self.bad('verify', 'task')

    def test_http_response_limit_blocks(self):
        self.simple()
        url = self.http(b'x' * 20000)
        self.contract['gates'][0]['checks'] = [{'id': 'http', 'type': 'http', 'purpose': 'behavior',
                                               'url': url, 'expect_status': 200, 'max_bytes': 100}]
        self.ok('lock')
        self.bad('verify', 'final')
        self.bad('finalize')

    def test_http_timeout_blocks(self):
        self.simple()
        url = self.http(delay=0.2)
        self.contract['gates'][0]['checks'] = [{'id': 'http', 'type': 'http', 'purpose': 'behavior',
                                               'url': url, 'expect_status': 200, 'timeout': 0.03}]
        self.ok('lock')
        self.bad('verify', 'final')

    def test_mutation_requires_readback_mapping(self):
        self.contract['mutations'] = [{'outcome': 'Saved product', 'gate': 'task', 'check': 'ready'}]
        self.bad('lock')

    def test_new_plan_addition_preserves_original(self):
        self.ok('lock')
        (self.root / 'addition.md').write_text('Product contents are nonempty.')
        self.contract['plan_additions'] = ['addition.md']
        self.contract['requirements'].append({'id': 'R2', 'text': 'Nonempty', 'gate': 'task', 'source': 'Product contents are nonempty.'})
        self.ok('extend')
        self.ok('verify', 'final')
        self.finish()

    def test_concurrent_operation_and_interruption_block(self):
        self.simple()
        code = "from pathlib import Path; import time; Path('started').touch(); time.sleep(20)"
        self.contract['gates'][0]['checks'][0]['argv'][-1] = code
        self.ok('lock')
        self.save()
        proc = subprocess.Popen([sys.executable, str(POD), 'verify', str(self.path), '--gate', 'final'], cwd=self.root,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for _ in range(100):
                if (self.root / 'started').exists():
                    break
                time.sleep(.02)
            self.assertTrue((self.root / 'started').exists())
            self.bad('coverage')
            proc.terminate()
            proc.communicate(timeout=3)
            self.bad('finalize')
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.communicate()

    def test_timeout_kills_child_before_side_effect(self):
        code = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',\"import time; from pathlib import Path; time.sleep(.5); Path('orphan').touch()\"]); time.sleep(20)"
        self.contract['gates'][0]['checks'][0].update(argv=[sys.executable, '-c', code], timeout=.05)
        self.ok('lock')
        self.bad('verify', 'task')
        time.sleep(.65)
        self.assertFalse((self.root / 'orphan').exists())

    def test_file_observation_cannot_be_excluded_from_freshness(self):
        self.simple()
        (self.root / 'other.txt').write_text('unrelated')
        g = self.contract['gates'][0]
        g.update(inputs=['other.txt'], excludes=['product.txt'], checks=[{'id': 'read', 'type': 'file',
                 'purpose': 'behavior', 'path': 'product.txt', 'equals': 'ready'}])
        self.ok('lock')
        self.ok('verify', 'final')
        (self.root / 'product.txt').write_text('broken')
        self.bad('finalize')

    def test_same_run_dependency_changes_cannot_approve_final(self):
        self.contract['gates'][-1]['inputs'] = ['plan.md']
        self.contract['gates'][-1]['checks'][0]['argv'][-1] = "from pathlib import Path; Path('product.txt').write_text('broken')"
        self.ok('lock')
        self.bad('verify', 'final')

    def test_audit_missing_requirement_does_not_approve(self):
        self.ok('lock')
        self.ok('verify', 'final')
        path = self.audit()
        audit = json.loads(path.read_text())
        audit['requirements'] = []
        path.write_text(json.dumps(audit))
        self.bad('finalize', extra=['--audit', str(path)])

    def test_credentials_from_environment_are_not_recorded(self):
        self.simple()
        secret = 'only-in-environment-123456'
        self.contract['gates'][0]['checks'][0]['argv'][-1] = "import os; print(os.environ['DONEPROOF_TEST_SECRET'])"
        previous = os.environ.get('DONEPROOF_TEST_SECRET')
        os.environ['DONEPROOF_TEST_SECRET'] = secret
        try:
            self.ok('lock')
            self.ok('verify', 'final')
            for path in (self.folder / 'proofs').glob('*.json'):
                self.assertNotIn(secret, path.read_text())
        finally:
            if previous is None:
                os.environ.pop('DONEPROOF_TEST_SECRET', None)
            else:
                os.environ['DONEPROOF_TEST_SECRET'] = previous

    def test_declared_environment_changes_invalidate_proof(self):
        self.simple()
        previous = os.environ.get('POD_ENDPOINT')
        try:
            os.environ['POD_ENDPOINT'] = 'first-environment'
            self.contract['gates'][0]['checks'][0]['env_from'] = {'ENDPOINT': 'POD_ENDPOINT'}
            self.ok('lock')
            self.ok('verify', 'final')
            self.ok('finalize')
            os.environ['POD_ENDPOINT'] = 'second-environment'
            self.bad('finalize')
        finally:
            if previous is None:
                os.environ.pop('POD_ENDPOINT', None)
            else:
                os.environ['POD_ENDPOINT'] = previous


if __name__ == '__main__':
    unittest.main()

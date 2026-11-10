"""Independent regression: external requirement gates outside final's closure."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

POD = Path(__file__).resolve().parents[1] / 'scripts/pod.py'


class ExternalRequirementTests(unittest.TestCase):
    def test_external_readback_is_refreshed_before_final_even_outside_closure(self):
        for reuse in (False, True):
            with self.subTest(reuse=reuse), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                (root / 'input.txt').write_text('source')
                (root / 'outside.txt').write_text('good')
                (root / 'acceptance.md').write_text('Persisted outcome remains good.')
                (root / 'plan.md').write_text('Read back saved outcome.')
                path = root / '.pod/contract.json'
                path.parent.mkdir()

                def check(cid, purpose, code):
                    return {'id': cid, 'type': 'command', 'purpose': purpose,
                            'effect': 'observe', 'argv': [sys.executable, '-c', code],
                            'expect_exit': 0}

                def gate(gid, checks):
                    return {'id': gid, 'level': 'feature', 'inputs': ['input.txt'],
                            'criteria': ['acceptance.md'], 'checks': checks}

                path.write_text(json.dumps({
                    'schema_version': 3, 'task_id': 'readback', 'root': '..',
                    'kind': 'plan', 'mode': 'standard', 'plan_path': 'plan.md',
                    'requirements': [{'id': 'R1', 'text': 'Read back',
                                      'source': 'Read back saved outcome.', 'gate': 'saved'}],
                    'final_gate': 'final', 'gates': [
                        gate('saved', [check('read', 'readback',
                             "from pathlib import Path; assert Path('outside.txt').read_text() == 'good', 'saved outcome must remain good'")]),
                        gate('final', [check('behavior', 'behavior',
                             "from pathlib import Path; assert Path('input.txt').read_text() == 'source'"),
                             check('integration', 'integration',
                             "import json; from pathlib import Path; assert json.loads(Path('.pod/state.json').read_text())['records']['saved']['status'] == 'PASS', 'final must consume a passing saved-state observation'")])]}))

                def call(action, *args):
                    return subprocess.run([sys.executable, str(POD), action, str(path), *args],
                                          cwd=root, text=True, capture_output=True, timeout=15)

                self.assertEqual(call('lock').returncode, 0)
                self.assertEqual(call('verify', '--gate', 'saved').returncode, 0)
                before = json.loads((path.parent / 'state.json').read_text())['records']['saved']['proof']
                # This observation is intentionally external to the declared local source inventory.
                (root / 'outside.txt').write_text('bad')
                result = call('finish', *(['--reuse'] if reuse else []))
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertNotIn('AUDIT_REQUIRED', result.stdout)
                self.assertNotIn('VERIFIED_SUCCESS', result.stdout)
                self.assertIn('saved outcome must remain good', result.stdout)
                saved = json.loads((path.parent / 'state.json').read_text())['records']['saved']
                self.assertNotEqual(before, saved['proof'])
                self.assertEqual(saved['status'], 'FAIL')
                self.assertEqual(json.loads((path.parent / 'completion.json').read_text())['status'], 'INVALIDATED')

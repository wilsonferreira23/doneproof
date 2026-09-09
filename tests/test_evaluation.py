"""Report acceptance tests use artificial rows, never count them as agent runs."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/evaluate.py'


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        spec = importlib.util.spec_from_file_location('evaluation', SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        corpus = {'cases': [{'id': f'fixture-{i}', 'category': 'normal'} for i in range(12)]}
        self.write('corpus.json', corpus)
        for condition in ('v22', 'candidate'):
            (self.root / 'skills' / condition).mkdir(parents=True)
        self.protocol = {'tasks': 12, 'repetitions': 1, 'stage': 'pilot',
                         'corpus_sha256': self.module.sha(self.root / 'corpus.json'),
                         'skill_hashes': {'v22': {}, 'candidate': {}}}
        self.write('protocol.json', self.protocol)
        self.row = {'task': 'fixture', 'category': 'normal', 'repetition': 0, 'correct': True,
                    'declared_complete': True, 'false_success': False, 'false_block': False,
                    'correct_completion': True, 'infrastructure_error': False, 'timed_out': False,
                    'duration_seconds': 1, 'usage': {'input_tokens': 100, 'output_tokens': 10},
                    'protocol_sha256': self.module.sha(self.root / 'protocol.json')}

    def write(self, name, obj):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj))

    def rows(self, candidate=None):
        for i in range(12):
            for condition in ('without', 'v22', 'candidate'):
                row = dict(self.row, task=f'fixture-{i}', condition=condition)
                if condition == 'candidate':
                    row.update(candidate or {})
                folder = f'episodes/fixture-{i}-{condition}'
                self.write(folder + '/result.json', row)
                self.write(folder + '/oracle-result.json', {'exit': 0 if row['correct'] else 1})
                self.write(folder + '/answer.json', {'status': 'complete' if row['declared_complete'] else 'blocked'})
                self.write(folder + '/events.jsonl', {'type': 'turn.completed', 'usage': row['usage']})

    def report(self):
        return subprocess.run([sys.executable, str(SCRIPT), 'report', '--require-pass', str(self.root)], capture_output=True, text=True)

    def test_missing_episodes_cannot_pass(self):
        self.assertNotEqual(self.report().returncode, 0)

    def test_false_success_cannot_pass(self):
        self.rows({'false_success': True, 'correct': False, 'correct_completion': False})
        result = self.report()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('false success observed', result.stdout)

    def test_blocking_everything_cannot_pass(self):
        self.rows({'declared_complete': False, 'correct_completion': False, 'false_block': True})
        self.assertNotEqual(self.report().returncode, 0)

    def test_missing_usage_cannot_be_discarded(self):
        self.rows({'usage': None})
        result = self.report()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('missing measured token usage', result.stdout)

    def test_protocol_change_rejects_old_results(self):
        self.rows()
        self.protocol['repetitions'] = 2
        self.write('protocol.json', self.protocol)
        self.assertNotEqual(self.report().returncode, 0)

    def test_changed_token_summary_is_rejected(self):
        self.rows()
        path = self.root / 'episodes/fixture-0-candidate/result.json'
        row = json.loads(path.read_text())
        row['usage']['input_tokens'] = 1
        path.write_text(json.dumps(row))
        self.assertIn('raw token usage', self.report().stderr)

    def test_changed_category_is_rejected(self):
        self.rows()
        path = self.root / 'episodes/fixture-0-candidate/result.json'
        row = json.loads(path.read_text())
        row['category'] = 'strict'
        path.write_text(json.dumps(row))
        self.assertIn('category', self.report().stderr)

    def test_passing_synthetic_rows_exercise_report_arithmetic(self):
        self.rows()
        result = self.report()
        self.assertNotEqual(result.returncode, 0, 'pilot must not qualify as final efficacy')
        report = json.loads(result.stdout)
        self.assertEqual(report['conditions']['candidate']['correct_completion_rate'], 1)
        self.assertEqual(report['median_normal_token_overhead'], 0)
        self.assertEqual(report['failures'], ['pilot is not final efficacy evidence'])


if __name__ == '__main__':
    unittest.main()

"""Bounded transition properties and controls of the verification boundary."""
import itertools
import json
from pathlib import Path
import sys
import unittest

from test_evidence import EvidenceFixture


class NegativeControls(EvidenceFixture, unittest.TestCase):
    def test_failure_is_behavioral_and_repaired_delivery_requires_new_evidence(self):
        self.ok('lock'); self.ok('finish')
        (self.root / 'product.txt').write_text('broken')
        failed = self.blocked('finish', '--reuse')
        self.assertIn('PRODUCT_NOT_READY', failed.stdout)
        self.assertEqual(self.completion()['status'], 'INVALIDATED')
        (self.root / 'product.txt').write_text('ready')
        self.ok('finish', '--reuse')
        self.assertEqual(self.count(), 3)
        self.assertEqual(self.completion()['status'], 'VERIFIED_SUCCESS')

    def test_irrelevant_assertion_is_not_semantically_detected_but_targeted_control_is(self):
        # Demonstrate the honest boundary: exit/count alone cannot prove relevance.
        (self.root / 'check.py').write_text('assert 1 == 1\n')
        (self.root / 'product.txt').write_text('broken')
        self.ok('lock'); self.ok('finish')
        self.assertEqual(self.completion()['status'], 'VERIFIED_SUCCESS')
        # A separate immutable acceptance assertion detects this exact mutation.
        self.path = self.root / '.proof-of-done' / 'targeted' / 'contract.json'
        self.path.parent.mkdir()
        self.contract['task_id'] = 'targeted'
        self.check['argv'] = [sys.executable, '-c', 'from pathlib import Path; assert Path("product.txt").read_text() == "ready", "PRODUCT_NOT_READY"']
        self.ok('lock')
        self.assertIn('PRODUCT_NOT_READY', self.blocked('finish').stdout)

    def test_bounded_state_sequences_preserve_completion_invariant(self):
        # Explore all 9 sequences of length two. Every step ends in a real CLI
        # finish, checking both acceptance and rejection; this is finite testing.
        actions = ('break', 'restore', 'edit_test')
        for index, sequence in enumerate(itertools.product(actions, repeat=2)):
            with self.subTest(sequence=sequence):
                self.path = self.root / '.proof-of-done' / ('sequence'+str(index)) / 'contract.json'
                self.path.parent.mkdir()
                self.contract['task_id'] = 'sequence'+str(index)
                (self.root / 'product.txt').write_text('ready')
                self.ok('lock'); self.ok('finish')
                ready = True
                for action in sequence:
                    if action == 'break':
                        ready = False
                        (self.root / 'product.txt').write_text('broken')
                    elif action == 'restore':
                        ready = True
                        (self.root / 'product.txt').write_text('ready')
                    else:
                        with (self.root / 'check.py').open('a') as f:
                            f.write('# test revision\n')
                    result = self.cli('finish', '--reuse')
                    self.assertEqual(result.returncode == 0, ready, result.stdout+result.stderr)
                    self.assertEqual(self.completion()['status'] == 'VERIFIED_SUCCESS', ready)
                    if not ready:
                        self.assertNotIn('VERIFIED_SUCCESS', result.stdout)

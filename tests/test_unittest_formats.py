"""Stable IDs across supported native unittest output versions."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('format_pod', Path(__file__).resolve().parents[1]/'scripts/pod.py')
pod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pod)

class UnittestFormats(unittest.TestCase):
    def test_old_and_new_verbose_formats_with_and_without_docstrings(self):
        check = {'runner': 'unittest', 'argv': ['python3'], 'required_tests': ['test_product.Product.test_ready']}
        for label in ('test_product.Product', 'test_product.Product.test_ready'):
            for description in ('', '\nThe product is ready.'):
                with self.subTest(label=label, description=description):
                    output = 'test_ready (' + label + ')' + description + ' ... ok\n\nRan 1 test in 0.001s\n\nOK\n'
                    receipt = pod.test_receipt(check, output)
                    self.assertEqual(receipt['passed_ids'], check['required_tests'])
                    self.assertEqual(receipt['executed'], 1)

    def test_legacy_output_cannot_satisfy_a_different_mandatory_case(self):
        check = {'runner':'unittest', 'argv':['python3'], 'required_tests':['test_product.Product.test_ready']}
        with self.assertRaises(pod.Blocked):
            pod.test_receipt(check, 'test_other (test_product.Product) ... ok\nRan 1 test in 0.001s\nOK\n')

import unittest

from app import add


class MathTests(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(1, 2), 3)
        self.assertEqual(add(-2, 2), 0)

    def test_preserves_inputs(self):
        left, right = [1], [2]
        result = add(left, right)
        self.assertEqual(result, [1, 2])
        self.assertEqual(left, [1])
        self.assertEqual(right, [2])
        self.assertIsNot(result, left)
        self.assertIsNot(result, right)

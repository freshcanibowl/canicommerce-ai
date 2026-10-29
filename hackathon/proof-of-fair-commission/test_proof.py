import unittest
from proof import build, proof, verify

class TestMerkle(unittest.TestCase):
    def test_all_leaves(self):
        rows = [{'id': i, 'amount_sen': i * 7} for i in range(1, 8)]
        tree = build(rows)
        root = tree[-1][0].hex()
        for i, row in enumerate(rows):
            self.assertTrue(verify(row, proof(tree, i), root))

    def test_tampering_fails(self):
        rows = [{'amount_sen': 300}, {'amount_sen': 700}]
        tree = build(rows)
        root = tree[-1][0].hex()
        self.assertFalse(verify({'amount_sen': 301}, proof(tree, 0), root))

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            build([])

    def test_single_leaf(self):
        rows = [{'id': 'single'}]
        tree = build(rows)
        self.assertTrue(verify(rows[0], proof(tree, 0), tree[-1][0].hex()))

if __name__ == '__main__':
    unittest.main()

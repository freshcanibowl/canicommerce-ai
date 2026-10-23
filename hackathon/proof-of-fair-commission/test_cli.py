import copy
import unittest
from cli import exact_commission, export_bundle, verify_bundle

ROWS = [
    {'order_id':'demo-001','partner_id':'agent-A','role':'ORIGINAL','eligible_sen':10000,'amount_sen':300,'currency':'MYR'},
    {'order_id':'demo-001','partner_id':'seller-B','role':'SELLER','eligible_sen':10000,'amount_sen':700,'currency':'MYR'},
    {'order_id':'demo-002','partner_id':'agent-A','role':'ORIGINAL','eligible_sen':105,'amount_sen':3,'currency':'MYR'},
]

class TestCLI(unittest.TestCase):
    def test_rounding(self):
        self.assertEqual(exact_commission(50, 3), 2)
        self.assertEqual(exact_commission(150, 3), 5)
    def test_valid_bundle(self):
        self.assertTrue(verify_bundle(export_bundle(ROWS)))
    def test_tampered_amount(self):
        b = export_bundle(ROWS)
        b['proofs'][0]['record']['amount_sen'] += 1
        self.assertFalse(verify_bundle(b))
    def test_tampered_root(self):
        b = export_bundle(ROWS)
        b['root'] = '0' * 64
        self.assertFalse(verify_bundle(b))
    def test_duplicate_role(self):
        with self.assertRaises(ValueError):
            export_bundle(ROWS + [copy.deepcopy(ROWS[0])])
    def test_wrong_commission(self):
        rows = copy.deepcopy(ROWS)
        rows[1]['amount_sen'] = 701
        with self.assertRaises(ValueError):
            export_bundle(rows)
    def test_missing_record(self):
        b = export_bundle(ROWS)
        b['proofs'].pop()
        self.assertFalse(verify_bundle(b))
    def test_proof_path_replacement(self):
        b = export_bundle(ROWS)
        b['proofs'][0]['path'] = b['proofs'][1]['path']
        self.assertFalse(verify_bundle(b))

if __name__ == '__main__':
    unittest.main()

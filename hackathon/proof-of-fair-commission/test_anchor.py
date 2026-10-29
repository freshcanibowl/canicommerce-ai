import copy
import json
import unittest
from pathlib import Path
from anchor import prepare, check_manifest
from cli import export_bundle

class AnchorTests(unittest.TestCase):
    def setUp(self):
        self.rows = json.loads((Path(__file__).parent / 'synthetic-records.json').read_text())
        self.bundle = export_bundle(self.rows)
    def test_prepare(self):
        m = prepare(self.bundle)
        self.assertEqual(m['chain_status'], 'NOT_DEPLOYED')
        self.assertEqual(m['root'], '0x' + self.bundle['root'])
        self.assertTrue(check_manifest(self.bundle, m))
    def test_tampered_bundle(self):
        bad = copy.deepcopy(self.bundle)
        bad['proofs'][0]['record']['amount_sen'] += 1
        with self.assertRaises(ValueError): prepare(bad)
    def test_tampered_manifest(self):
        m = prepare(self.bundle)
        m['root'] = '0x' + 'f'*64
        self.assertFalse(check_manifest(self.bundle, m))
    def test_reject_fabricated_deployment(self):
        m = prepare(self.bundle)
        m['chain_status'] = 'CONFIRMED'
        self.assertFalse(check_manifest(self.bundle, m))

if __name__ == '__main__': unittest.main()

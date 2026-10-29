import copy
import unittest
from cli import export_bundle
from receipt_verify import verify_receipt

class ReceiptTests(unittest.TestCase):
    def setUp(self):
        rows = [{'order_id':'order-1','partner_id':'agent-1','role':'ORIGINAL','currency':'MYR','eligible_sen':10000,'amount_sen':300}]
        self.bundle = export_bundle(rows)
        self.contract = '0x' + 'ab'*20
        self.tx = '0x' + 'cd'*32
        self.topic = '0x' + 'ef'*32
        self.receipt = {'status':'0x1','transactionHash':self.tx,'blockHash':'0x'+'01'*32,'blockNumber':'0x1',
                        'logs':[{'address':self.contract,'topics':[self.topic,'0x'+self.bundle['root'],'0x'+format(1,'064x'),
                               '0x'+__import__('anchor').SCHEMA_HASH], 'data':'0x','removed':False}]}

    def test_valid(self):
        self.assertTrue(verify_receipt(self.bundle,self.receipt,11155111,11155111,self.contract,self.tx,self.topic))

    def test_wrong_chain(self):
        self.assertFalse(verify_receipt(self.bundle,self.receipt,1,11155111,self.contract,self.tx,self.topic))

    def test_reverted_transaction(self):
        receipt = copy.deepcopy(self.receipt); receipt['status']='0x0'
        self.assertFalse(verify_receipt(self.bundle,receipt,11155111,11155111,self.contract,self.tx,self.topic))

    def test_wrong_root(self):
        receipt = copy.deepcopy(self.receipt); receipt['logs'][0]['topics'][1]='0x'+'00'*32
        self.assertFalse(verify_receipt(self.bundle,receipt,11155111,11155111,self.contract,self.tx,self.topic))

    def test_wrong_contract(self):
        receipt = copy.deepcopy(self.receipt); receipt['logs'][0]['address']='0x'+'00'*20
        self.assertFalse(verify_receipt(self.bundle,receipt,11155111,11155111,self.contract,self.tx,self.topic))

    def test_removed_log(self):
        receipt = copy.deepcopy(self.receipt); receipt['logs'][0]['removed']=True
        self.assertFalse(verify_receipt(self.bundle,receipt,11155111,11155111,self.contract,self.tx,self.topic))

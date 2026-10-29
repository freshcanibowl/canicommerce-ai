"""Synthetic API tests; do not exercise payments or new chain writes."""
import os
from fastapi.testclient import TestClient
import pytest

@pytest.fixture(scope='module')
def client(tmp_path_factory):
    os.environ['CANICOMMERCE_DB']=str(tmp_path_factory.mktemp('pilot')/'test.sqlite3')
    os.environ['CANICOMMERCE_DEMO_MODE']='1'
    import app
    return TestClient(app.app)

def admin(c):
    r=c.post('/api/login',json={'username':'demo.admin','password':'FairProof2026!'})
    assert r.status_code==200, r.text
    return {'Authorization':'Bearer '+r.json()['token']}

def test_auth_guard(client):
    assert client.post('/api/login',json={'username':'demo.admin','password':'bad'}).status_code==401
    assert client.get('/api/audit').status_code==401

def test_baseline_and_reference_anchor(client):
    d=client.get('/api/dashboard').json()
    assert (d['policy']['original_bps'],d['policy']['seller_bps'])==(300,700)
    assert any(o['selling_partner'] is None for o in d['orders'])
    p=client.get('/api/verify/legacy').json()
    assert p['valid'] and not p['rpc_live_checked']

def test_policy_governance(client):
    h=admin(client);before=client.get('/api/dashboard').json()
    r=client.post('/api/policy',headers=h,json={'original_percent':4,'seller_percent':6,'expected_version':before['policy']['version'],'reason':'Synthetic governance adjustment'})
    assert r.status_code==200,r.text
    assert not r.json()['retroactive']
    assert client.get('/api/dashboard').json()['entries']==before['entries']
    stale=client.post('/api/policy',headers=h,json={'original_percent':5,'seller_percent':5,'expected_version':1,'reason':'Stale update should fail'})
    assert stale.status_code==409

def test_capture_amend_dispute(client):
    h=admin(client)
    r=client.post('/api/orders',headers=h,json={'id':'DEMO-TEST-309','customer_id':'synthetic-1','original_agent':'agent-A','selling_partner':'seller-B','eligible_sen':10000,'reason':'API integration synthetic test'})
    assert r.status_code==200,r.text
    d=client.get('/api/dashboard').json()
    rows=[e for e in d['entries'] if e['order_id']=='DEMO-TEST-309']
    assert sorted(e['amount_sen'] for e in rows)==[400,600]
    o=next(o for o in d['orders'] if o['id']=='DEMO-TEST-309')
    a=client.post('/api/orders/DEMO-TEST-309/amend',headers=h,json={'eligible_sen':15000,'expected_version':o['version'],'reason':'Corrected synthetic sample'})
    assert a.status_code==200,a.text
    rows=[e for e in client.get('/api/dashboard').json()['entries'] if e['order_id']=='DEMO-TEST-309']
    assert sorted(e['amount_sen'] for e in rows)==[200,300,400,600]
    o=next(o for o in client.get('/api/dashboard').json()['orders'] if o['id']=='DEMO-TEST-309')
    dispute=client.post('/api/orders/DEMO-TEST-309/dispute',headers=h,json={'expected_version':o['version'],'reason':'Disputed synthetic capture'})
    assert dispute.status_code==200 and not dispute.json()['settlement_eligible']

def test_audit_and_current_proof(client):
    h=admin(client)
    audit=client.get('/api/audit',headers=h).json()
    assert audit['hash_chain_valid'] and len(audit['events'])>=5
    current=client.get('/api/verify/current').json()
    assert current['anchored'] is False
    assert all(p['valid'] for p in current['proofs'])

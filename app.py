"""Isolated synthetic CaniCommerce integration demo; NOT for real commissions or payouts."""
from __future__ import annotations
import hashlib, hmac, json, os, secrets, sqlite3, threading, time
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Header, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from canicommerce.core import commission_sen
from web3_proof.proof import build, proof, verify

ROOT=Path(__file__).resolve().parent
DB=Path(os.environ.get('CANICOMMERCE_DB', str(ROOT/'data'/'canicommerce.sqlite3')))
DEMO=os.environ.get('CANICOMMERCE_DEMO_MODE','0')=='1'
DEMO_USER=os.environ.get('CANICOMMERCE_DEMO_USER','demo.admin')
DEMO_PASSWORD=os.environ.get('CANICOMMERCE_DEMO_PASSWORD','FairProof2026!')
DB.parent.mkdir(parents=True,exist_ok=True)
app=FastAPI(title='CaniCommerce Partner Commission + Web3 Evidence',version='0.8.0',description='Synthetic pilot only. No payments, payouts, or live commission anchoring.')
_lock=threading.RLock(); sessions={}

def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def digest(x):return hashlib.sha256(canon(x).encode()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
def password_hash(p,salt):return hashlib.pbkdf2_hmac('sha256',p.encode(),bytes.fromhex(salt),240000).hex()
def dbconn():
 c=sqlite3.connect(DB,timeout=30,isolation_level=None,check_same_thread=False)
 c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA journal_mode=WAL')
 return c

@contextmanager
def tx():
 with _lock:
  c=dbconn()
  try:
   c.execute('BEGIN IMMEDIATE');yield c;c.commit()
  except Exception:
   c.rollback();raise
  finally:c.close()

def rowdict(r):return dict(r) if r else None

def init_db():
 with dbconn() as c:
  c.executescript('''
   CREATE TABLE IF NOT EXISTS operators(username TEXT PRIMARY KEY,salt TEXT NOT NULL,pass_hash TEXT NOT NULL,role TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS policy_versions(version INTEGER PRIMARY KEY, original_bps INTEGER NOT NULL, seller_bps INTEGER NOT NULL, created_at TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY,customer_id TEXT NOT NULL,original_agent TEXT,selling_partner TEXT,eligible_sen INTEGER NOT NULL CHECK(eligible_sen>=0),status TEXT NOT NULL, captured_at TEXT NOT NULL, policy_version INTEGER NOT NULL,version INTEGER NOT NULL DEFAULT 1,FOREIGN KEY(policy_version) REFERENCES policy_versions(version));
   CREATE TABLE IF NOT EXISTS commission_entries(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id TEXT NOT NULL,partner_id TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('ORIGINAL','SELLER','REVERSAL')),amount_sen INTEGER NOT NULL,policy_version INTEGER NOT NULL,business_key TEXT NOT NULL UNIQUE,created_at TEXT NOT NULL,eligible_at TEXT NOT NULL,FOREIGN KEY(order_id) REFERENCES orders(id));
   CREATE TABLE IF NOT EXISTS audit_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,actor TEXT NOT NULL,action TEXT NOT NULL,target TEXT NOT NULL,before_json TEXT,after_json TEXT NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL,previous_hash TEXT NOT NULL,hash TEXT NOT NULL);
  ''')
 with tx() as c:
  if not c.execute('SELECT 1 FROM policy_versions').fetchone():
   c.execute('INSERT INTO policy_versions VALUES(1,300,700,?,?,?)',(utc(),'SYSTEM','Frozen CaniBiz commercial baseline: 3% overriding, 7% seller'))
  if DEMO and not c.execute('SELECT 1 FROM operators WHERE username=?',(DEMO_USER,)).fetchone():
   salt=secrets.token_hex(16);c.execute('INSERT INTO operators VALUES(?,?,?,?)',(DEMO_USER,salt,password_hash(DEMO_PASSWORD,salt),'admin'))
  if DEMO and not c.execute('SELECT 1 FROM orders').fetchone():
   create_order_db(c,'DEMO-001','customer-demo','agent-A','seller-B',10000,'SYSTEM','Initial synthetic sample')
   create_order_db(c,'DEMO-002','customer-demo2','agent-A',None,105,'SYSTEM','Direct order, no invented selling partner')

# SQL executescript auto-commits: initialized schema only; business writes always use transactions.
def policy(c):return rowdict(c.execute('SELECT * FROM policy_versions ORDER BY version DESC LIMIT 1').fetchone())
def audit(c,actor,action,target,before,after,reason):
 previous=c.execute('SELECT hash FROM audit_events ORDER BY seq DESC LIMIT 1').fetchone()
 prior=previous['hash'] if previous else 'GENESIS'
 event={'actor':actor,'action':action,'target':target,'before':before,'after':after,'reason':reason,'created_at':utc(),'previous_hash':prior}
 hashed=digest(event)
 c.execute('INSERT INTO audit_events(actor,action,target,before_json,after_json,reason,created_at,previous_hash,hash) VALUES(?,?,?,?,?,?,?,?,?)', (actor,action,target,canon(before) if before is not None else None,canon(after),reason,event['created_at'],prior,hashed))
 return hashed

def current_entries(c,order_id):return [rowdict(r) for r in c.execute('SELECT * FROM commission_entries WHERE order_id=? ORDER BY id',(order_id,))]

def create_order_db(c,order_id,customer,original,seller,eligible,actor,reason):
 p=policy(c);now=utc();at=(datetime.fromisoformat(now)+timedelta(days=28)).isoformat()
 c.execute("INSERT INTO orders(id,customer_id,original_agent,selling_partner,eligible_sen,status,captured_at,policy_version,version) VALUES(?,?,?,?,?,'CAPTURED',?,?,1)",(order_id,customer,original,seller,eligible,now,p['version']))
 for role,partner,bps in [('ORIGINAL',original,p['original_bps']),('SELLER',seller,p['seller_bps'])]:
  if partner:
   amount=commission_sen(eligible,Decimal(bps)/10000)
   c.execute('INSERT INTO commission_entries(order_id,partner_id,role,amount_sen,policy_version,business_key,created_at,eligible_at) VALUES(?,?,?,?,?,?,?,?)',(order_id,partner,role,amount,p['version'],f'{order_id}:capture:{role}',now,at))
 audit(c,actor,'ORDER_CAPTURED',order_id,None,{'eligible_sen':eligible,'customer_id':customer,'original_agent':original,'selling_partner':seller,'policy_version':p['version']},reason)

init_db()

def require_admin(authorization:str|None):
 if not authorization or not authorization.startswith('Bearer '):raise HTTPException(401,'Admin authentication required')
 token=authorization[7:]; key=hashlib.sha256(token.encode()).hexdigest();sess=sessions.get(key)
 if not sess or sess[1] < time.time():raise HTTPException(401,'Session invalid or expired')
 return sess[0]

class Login(BaseModel):username:str;password:str
class PolicyUpdate(BaseModel):original_percent:float=Field(ge=0,le=100);seller_percent:float=Field(ge=0,le=100);reason:str=Field(min_length=8,max_length=500);expected_version:int
class OrderInput(BaseModel):id:str=Field(pattern=r'^[A-Za-z0-9-]{3,50}$');customer_id:str=Field(min_length=2,max_length=100);original_agent:str|None=None;selling_partner:str|None=None;eligible_sen:int=Field(ge=0,le=10**12);reason:str=Field(min_length=8,max_length=500)
class OrderAmend(BaseModel):eligible_sen:int=Field(ge=0,le=10**12);reason:str=Field(min_length=8,max_length=500);expected_version:int
class Dispute(BaseModel):reason:str=Field(min_length=8,max_length=500);expected_version:int

@app.get('/')
def home():return FileResponse(ROOT/'web'/'index.html')
@app.get('/legacy-demo')
def legacy():return FileResponse(ROOT/'web'/'legacy-demo.html')
@app.get('/api/health')
def health():return {'ok':True,'mode':'SYNTHETIC_DEMO' if DEMO else 'LOCKED_NO_DEMO_OPERATOR','real_payments':False,'live_anchor_writes':False}
@app.post('/api/login')
def login(item:Login):
 with dbconn() as c:r=c.execute('SELECT * FROM operators WHERE username=?',(item.username,)).fetchone()
 if not r or not hmac.compare_digest(password_hash(item.password,r['salt']),r['pass_hash']):raise HTTPException(401,'Invalid login')
 token=secrets.token_urlsafe(32);sessions[hashlib.sha256(token.encode()).hexdigest()]=(r['username'],time.time()+3600)
 return {'token':token,'role':r['role'],'expires_seconds':3600}
@app.get('/api/dashboard')
def dashboard():
 with dbconn() as c:
  return {'policy':policy(c),'orders':[rowdict(r) for r in c.execute('SELECT * FROM orders ORDER BY captured_at DESC')],'entries':[rowdict(r) for r in c.execute('SELECT * FROM commission_entries ORDER BY id DESC')],'audit_count':c.execute('SELECT COUNT(*) AS n FROM audit_events').fetchone()['n'],'scope':'SYNTHETIC DATA ONLY','chain':'SEPOLIA_REFERENCE_ANCHOR_READ_ONLY'}
@app.post('/api/policy')
def update_policy(item:PolicyUpdate,authorization:str|None=Header(default=None)):
 actor=require_admin(authorization)
 o=round(item.original_percent*100);s=round(item.seller_percent*100)
 if abs(o-item.original_percent*100)>1e-7 or abs(s-item.seller_percent*100)>1e-7:raise HTTPException(422,'At most two decimal places supported')
 if o+s>10000:raise HTTPException(422,'Combined rate cannot exceed 100%')
 with tx() as c:
  old=policy(c)
  if old['version']!=item.expected_version:raise HTTPException(409,'Policy changed; refresh and retry')
  if old['original_bps']==o and old['seller_bps']==s:raise HTTPException(409,'No change')
  updated={'version':old['version']+1,'original_bps':o,'seller_bps':s}
  c.execute('INSERT INTO policy_versions VALUES(?,?,?,?,?,?)',(updated['version'],o,s,utc(),actor,item.reason))
  audit(c,actor,'POLICY_UPDATED','commission-policy',old,updated,item.reason)
 return {'policy':updated,'retroactive':False,'on_chain':False}
@app.post('/api/orders')
def create_order(item:OrderInput,authorization:str|None=Header(default=None)):
 actor=require_admin(authorization)
 if not item.original_agent and not item.selling_partner:raise HTTPException(422,'At least one partner required')
 with tx() as c:
  if c.execute('SELECT 1 FROM orders WHERE id=?',(item.id,)).fetchone():raise HTTPException(409,'Duplicate order id')
  create_order_db(c,item.id,item.customer_id,item.original_agent,item.selling_partner,item.eligible_sen,actor,item.reason)
 return {'order_id':item.id,'status':'CAPTURED','payment_verified':False,'synthetic':True}
@app.post('/api/orders/{order_id}/amend')
def amend(order_id:str,item:OrderAmend,authorization:str|None=Header(default=None)):
 actor=require_admin(authorization)
 with tx() as c:
  r=c.execute('SELECT * FROM orders WHERE id=?',(order_id,)).fetchone()
  if not r:raise HTTPException(404,'Order not found')
  old=rowdict(r)
  if old['version']!=item.expected_version:raise HTTPException(409,'Order changed; refresh and retry')
  if old['eligible_sen']==item.eligible_sen:raise HTTPException(409,'No change')
  new={**old,'eligible_sen':item.eligible_sen,'version':old['version']+1}
  c.execute('UPDATE orders SET eligible_sen=?,version=? WHERE id=?',(item.eligible_sen,new['version'],order_id))
  # Historical entries remain immutable. New compensating adjustments are append-only.
  version=new['version'];p=c.execute('SELECT * FROM policy_versions WHERE version=?',(old['policy_version'],)).fetchone();now=utc()
  for e in current_entries(c,order_id):
   if e['role'] not in ('ORIGINAL','SELLER'):continue
   bps=p['original_bps'] if e['role']=='ORIGINAL' else p['seller_bps']
   prior=commission_sen(old['eligible_sen'],Decimal(bps)/10000);nextval=commission_sen(item.eligible_sen,Decimal(bps)/10000)
   delta=nextval-prior
   if delta:
    key=f'{order_id}:amend:{version}:{e["role"]}'
    c.execute('INSERT INTO commission_entries(order_id,partner_id,role,amount_sen,policy_version,business_key,created_at,eligible_at) VALUES(?,?,?,?,?,?,?,?)',(order_id,e['partner_id'],'REVERSAL',delta,old['policy_version'],key,now,e['eligible_at']))
  audit(c,actor,'ORDER_AMENDED',order_id,old,new,item.reason)
 return {'order_id':order_id,'version':version,'append_only_adjustments':True,'on_chain':False}
@app.post('/api/orders/{order_id}/dispute')
def dispute(order_id:str,item:Dispute,authorization:str|None=Header(default=None)):
 actor=require_admin(authorization)
 with tx() as c:
  r=c.execute('SELECT * FROM orders WHERE id=?',(order_id,)).fetchone()
  if not r:raise HTTPException(404,'Order not found')
  old=rowdict(r)
  if old['version']!=item.expected_version:raise HTTPException(409,'Order changed; refresh')
  if old['status']=='DISPUTED':raise HTTPException(409,'Already disputed')
  new={**old,'status':'DISPUTED','version':old['version']+1}
  c.execute("UPDATE orders SET status='DISPUTED',version=? WHERE id=?",(new['version'],order_id))
  audit(c,actor,'ORDER_DISPUTED',order_id,old,new,item.reason)
 return {'status':'DISPUTED','settlement_eligible':False}
@app.get('/api/audit')
def audit_list(authorization:str|None=Header(default=None)):
 require_admin(authorization)
 with dbconn() as c:events=[rowdict(r) for r in c.execute('SELECT * FROM audit_events ORDER BY seq')]
 previous='GENESIS';valid=True
 for e in events:
  body={k:e[k] for k in ('actor','action','target','reason','created_at','previous_hash')}
  body['before']=json.loads(e['before_json']) if e['before_json'] else None;body['after']=json.loads(e['after_json'])
  if e['previous_hash']!=previous or e['hash']!=digest(body):valid=False
  previous=e['hash']
 return {'events':events,'hash_chain_valid':valid,'limitations':'Hash linked SQLite rows are not independently tamper-proof; database administrators can rewrite history. No live chain anchor.'}
@app.get('/api/verify/legacy')
def legacy_proof():
 bundle=json.loads((ROOT/'web3_proof'/'demo-bundle.json').read_text());manifest=json.loads((ROOT/'web3_proof'/'anchor-manifest.json').read_text())
 valid=all(verify(entry['record'],entry['path'],bundle['root']) for entry in bundle['proofs'])
 return {'valid':valid and '0x'+bundle['root']==manifest['root'],'root':'0x'+bundle['root'],'anchor_manifest':manifest,'scope':'ORIGINAL ANCHORED SYNTHETIC SNAPSHOT','rpc_live_checked':False}
@app.get('/api/verify/current')
def current_proof():
 with dbconn() as c:
  p=policy(c);rows=[]
  for o in c.execute('SELECT * FROM orders ORDER BY id'):
   entries=current_entries(c,o['id'])
   for role in ('ORIGINAL','SELLER'):
    orig=next((e for e in entries if e['role']==role),None)
    if orig:
     amount=sum(e['amount_sen'] for e in entries if e['partner_id']==orig['partner_id'] and (e['role']==role or (e['role']=='REVERSAL' and e['business_key'].endswith(':'+role))))
     rows.append({'order_id':o['id'],'partner_id':orig['partner_id'],'role':role,'eligible_sen':o['eligible_sen'],'amount_sen':amount,'currency':'MYR','policy_version':o['policy_version'],'status':o['status']})
  if not rows:return {'root':None,'proofs':[],'anchored':False}
  layers=build(rows);root=layers[-1][0].hex()
  proofs=[{'record':r,'path':proof(layers,i),'valid':verify(r,proof(layers,i),root)} for i,r in enumerate(rows)]
 return {'root':'0x'+root,'proofs':proofs,'anchored':False,'message':'Current synthetic state: locally recomputed evidence only. Not anchored to Sepolia.'}
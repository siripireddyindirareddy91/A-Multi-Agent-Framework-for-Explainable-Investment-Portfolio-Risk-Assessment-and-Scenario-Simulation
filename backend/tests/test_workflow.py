import os
os.environ['DATABASE_URL']='sqlite://'
os.environ['JWT_SECRET']='test-secret-key-with-more-than-thirty-two-characters'
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from backend.app.engine import calculate, scenario, ASSETS
from backend.app import main
import numpy as np
import pytest

# File-backed isolated database lets request threads share transactional records.
@pytest.fixture(scope='module')
def client(tmp_path_factory):
 from sqlalchemy import create_engine
 from sqlalchemy.orm import sessionmaker
 path=tmp_path_factory.mktemp('db')/'test.db'
 main.engine=create_engine('sqlite:///'+str(path),connect_args={'check_same_thread':False})
 main.Session=sessionmaker(bind=main.engine,expire_on_commit=False)
 main.Base.metadata.create_all(main.engine);main.seed()
 return TestClient(main.app)
def holdings():
 return [dict(ticker=a[0],name=a[1],asset_class=a[2],sector=a[3],quantity=10,purchase_price=a[4]*.9,current_price=a[4],currency='USD') for a in ASSETS]
def test_engine_reproducible_and_accounting():
 h=holdings();a=calculate(h);b=calculate(h)
 assert a==b
 assert a['value']==pytest.approx(sum(x['quantity']*x['current_price'] for x in h))
 assert sum(a['weights'])==pytest.approx(1)
 assert sum(a['risk_contributions'])==pytest.approx(1)
 assert a['cvar']>=a['historical_var']>=0
 assert a['max_drawdown']<=0
 assert a['volatility']==pytest.approx(a['daily_volatility']*np.sqrt(252))
 assert np.allclose(np.array(a['correlations']).T,a['correlations'])
def test_reject_invalid_data():
 with pytest.raises(ValueError):calculate([])
 h=holdings();h[0]['current_price']=0
 with pytest.raises(ValueError):calculate(h)
 h=holdings();h[0]['currency']='EUR'
 with pytest.raises(ValueError):calculate(h)
 with pytest.raises(ValueError):calculate(holdings(),days=2)
def test_scenario_exact_shock():
 h=[holdings()[0]];r=scenario(h,dict(equity=-30))
 assert r['loss_pct']==pytest.approx(.3)
 assert r['after']==pytest.approx(r['before']*.7)
 assert scenario(h,dict(equity=-200))['after']==0
def test_complete_workflow(client):
 ps=client.get('/api/portfolios').json();assert len(ps)==3
 pid=ps[0]['id'];assert len(ps[0]['holdings'])==12
 a=client.post('/api/agents/run-analysis',json=dict(portfolio_id=pid));assert a.status_code==200,a.text
 analysis=a.json();assert len(analysis['agents'])==8
 assert analysis['agents'][-2]['status']=='Awaiting Approval'
 assert analysis['metrics']['value']>0
 r=client.post(f'/api/portfolios/{pid}/simulate',json=dict(name='Crash',equity=-30,bond=4));assert r.status_code==200
 assert r.json()['loss']>0
 assert client.get(f'/api/portfolios/{pid}/scenarios').json()
 rec=analysis['recommendations'][0]
 review=client.post(f"/api/recommendations/{rec['id']}/submit-review").json()
 assert client.post(f"/api/reviews/{review['id']}/decision",json=dict(status='Approved',comment='Review completed')).status_code==403
 auth=client.post('/api/auth/login',json=dict(email='reviewer@aegis.demo',password='AegisReview2026!')).json()
 headers={'Authorization':'Bearer '+auth['token']}
 approved=client.post(f"/api/reviews/{review['id']}/decision",headers=headers,json=dict(status='Approved',comment='Reviewed synthetic evidence.'))
 assert approved.status_code==200;assert approved.json()['history'][0]['reviewer']=='reviewer@aegis.demo'
 for fmt in ['pdf','metrics','holdings','scenarios']:
  r=client.get(f'/api/portfolios/{pid}/export/{fmt}');assert r.status_code==200
  assert len(r.content)>100
  if fmt=='pdf':assert r.content.startswith(b'%PDF')
 assert client.post(f'/api/portfolios/{pid}/chat',json=dict(question='What is my VaR?')).status_code==200
 assert client.post(f'/api/portfolios/{pid}/counterfactual',json=dict(style='Conservative')).status_code==200
def test_crud_csv_auth_and_persistence(client):
 r=client.post('/api/auth/register',json=dict(email='test@example.com',password='LongPassword2026!',name='Test Analyst'));assert r.status_code==200
 headers={'Authorization':'Bearer '+r.json()['token']}
 p=client.post('/api/portfolios',headers=headers,json=dict(name='Unit test',style='Balanced')).json();pid=p['id']
 h=holdings()[0]
 assert client.post(f'/api/portfolios/{pid}/holdings',headers=headers,json=h).status_code==200
 saved=client.get(f'/api/portfolios/{pid}',headers=headers).json();assert saved['holdings'][0]['ticker']=='AAPL'
 client.cookies.clear()
 assert client.get(f'/api/portfolios/{pid}').status_code==404
 assert client.post(f'/api/portfolios/{pid}/upload-csv',headers=headers,files={'file':('bad.csv',b'ticker,quantity\nAAPL,-2')}).status_code==422
 assert client.put('/api/settings',headers=headers,json=dict(simulations=1000,seed=7)).status_code==200
 assert client.get('/api/settings',headers=headers).json()['seed']==7
 assert client.delete(f'/api/portfolios/{pid}',headers=headers).status_code==200

def test_required_cookie_authentication(client,monkeypatch):
 monkeypatch.setattr(main,'REQUIRE_AUTH',True)
 client.cookies.clear()
 missing=client.get('/api/portfolios')
 assert missing.status_code==401
 assert 'expired' not in missing.json()['detail'].lower()
 assert client.get('/api/portfolios',headers={'Authorization':'Bearer invalid-token'}).status_code==401
 response=client.post('/api/auth/login',json=dict(email='analyst@aegis.demo',password='AegisDemo2026!'))
 assert response.status_code==200
 assert 'HttpOnly' in response.headers['set-cookie']
 assert 'SameSite=strict' in response.headers['set-cookie']
 assert client.get('/api/portfolios').status_code==200
 assert client.get('/api/auth/me').headers['cache-control']=='private, no-store'
 assert client.post('/api/auth/logout').status_code==200
 assert client.get('/api/portfolios').status_code==401
 client.cookies.clear()

def test_constrained_optimizer(client):
 r=client.post('/api/portfolios/demo-1/optimize',json=dict(maximum=.2,sector_cap=.5))
 assert r.status_code==200,r.text
 weights=r.json()['weights'];assert sum(w['proposed'] for w in weights)==pytest.approx(1)
 assert max(w['proposed'] for w in weights)<=.200001
 for sector in set(w['sector'] for w in weights):assert sum(w['proposed'] for w in weights if w['sector']==sector)<=.500001
 assert r.json()['status']=='Pending Review'
 assert client.post('/api/portfolios/demo-1/optimize',json=dict(maximum=.01)).status_code==422

def test_all_workspace_actions_and_custom_settings(client):
 client.cookies.clear()
 pid='demo-2'
 for path in ['/api/health','/api/scenarios','/api/settings','/api/audit','/api/reviews',f'/api/portfolios/{pid}',f'/api/portfolios/{pid}/holdings',f'/api/portfolios/{pid}/analyses',f'/api/portfolios/{pid}/recommendations']:
  assert client.get(path).status_code==200,path
 cfg=dict(confidence=.99,days=252,seed=17,simulations=1000)
 metrics=client.get(f'/api/portfolios/{pid}/analytics',params=cfg).json()
 alternate=client.post(f'/api/portfolios/{pid}/counterfactual',json=dict(style='Balanced',**cfg))
 assert alternate.status_code==200
 for k,v in cfg.items():assert alternate.json()['metrics'][k]==v
 exported=client.get(f'/api/portfolios/{pid}/export/metrics',params=cfg)
 assert exported.status_code==200
 import csv,io
 values=dict(csv.reader(io.StringIO(exported.text)))
 assert float(values['historical_var'])==pytest.approx(metrics['historical_var'])
 assert values['seed']=='17' and values['days']=='252'
 for text in ['Explain risk','What is my VaR?','Explain returns']:
  assert client.post(f'/api/portfolios/{pid}/chat',json=dict(question=text)).status_code==200
 p=client.post('/api/portfolios',json=dict(name='Button flow test')).json();new_id=p['id']
 assert client.put(f'/api/portfolios/{new_id}',json=dict(name='Renamed portfolio')).status_code==200
 h=client.post(f'/api/portfolios/{new_id}/holdings',json=holdings()[0]).json()['holdings'][0]
 assert client.put(f"/api/portfolios/{new_id}/holdings/{h['id']}",json=dict(holdings()[0],quantity=20)).status_code==200
 text='ticker,name,asset_class,sector,quantity,purchase_price,current_price,currency\nAAPL,Apple,Equity,Technology,10,100,200,USD\n'
 assert client.post(f'/api/portfolios/{new_id}/upload-csv',files={'file':('valid.csv',text)}).status_code==200
 saved=client.get(f'/api/portfolios/{new_id}').json()
 assert saved['holdings'][0]['current_price']==200
 assert client.delete(f"/api/portfolios/{new_id}/holdings/{saved['holdings'][0]['id']}").status_code==200
 assert client.delete(f'/api/portfolios/{new_id}').status_code==200

def test_review_rejection_revision_and_security(client):
 client.cookies.clear();a=client.post('/api/agents/run-analysis',json=dict(portfolio_id='demo-1')).json()
 ids=[]
 for r in a['recommendations']:
  first=client.post(f"/api/recommendations/{r['id']}/submit-review").json()
  again=client.post(f"/api/recommendations/{r['id']}/submit-review").json()
  assert first['id']==again['id'];ids.append(first['id'])
 client.post('/api/auth/login',json=dict(email='reviewer@aegis.demo',password='AegisReview2026!'))
 for rid,status in zip(ids,['Rejected','Needs Revision']):
  decision=client.post(f'/api/reviews/{rid}/decision',json=dict(status=status,comment='Automated fixture decision for test evidence.'))
  assert decision.status_code==200 and decision.json()['status']==status
 assert client.post('/api/settings',headers={'sec-fetch-site':'cross-site'},json={}).status_code==403
 assert client.put('/api/portfolios/demo-1',json=dict(name='Unauthorized change')).status_code==403
 client.cookies.clear()

"""Production API smoke coverage. Uses only synthetic demo data; no human decisions."""
import json, urllib.request, urllib.error, http.cookiejar, io, csv, sys
base=sys.argv[1] if len(sys.argv)>1 else 'https://aegis-risk-intelligence.vercel.app'
jar=http.cookiejar.CookieJar();http=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
passed=[]
def request(path,data=None,method=None,raw=False):
 req=urllib.request.Request(base+'/api'+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers={'Content-Type':'application/json'})
 with http.open(req,timeout=60) as response:
  body=response.read();assert response.status==200
  return body if raw else json.loads(body)
try:
 try:request('/auth/me');raise AssertionError('Anonymous account access allowed')
 except urllib.error.HTTPError as e:assert e.code==401
 passed.append('anonymous login gate')
 request('/auth/login',dict(email='analyst@aegis.demo',password='AegisDemo2026!'));assert request('/auth/me')['role']=='analyst';passed.append('demo cookie login')
 health=request('/health');assert health['database']=='postgresql' and health['durable'];passed.append('PostgreSQL storage')
 portfolios=request('/portfolios');pid=portfolios[0]['id'];request('/portfolios/'+pid);request('/portfolios/'+pid+'/holdings');passed.append('portfolio workspace')
 query='?confidence=0.99&days=252&simulations=1000&seed=17'
 metrics=request('/portfolios/'+pid+'/analytics'+query);assert metrics['seed']==17;passed.append('risk analytics configuration')
 request('/scenarios');request('/portfolios/'+pid+'/scenarios');passed.append('scenario templates and saved results')
 for endpoint in ['analyses','recommendations']:request('/portfolios/'+pid+'/'+endpoint)
 passed.append('agents and recommendations history')
 request('/portfolios/'+pid+'/chat',dict(question='Explain portfolio risk'));passed.append('explainability question')
 alt=request('/portfolios/'+pid+'/counterfactual',dict(style='Balanced',confidence=.99,days=252,simulations=1000,seed=17));assert alt['metrics']['seed']==17;passed.append('counterfactual matching settings')
 request('/portfolios/'+pid+'/optimize',dict(maximum=.25,sector_cap=.55));passed.append('constrained optimizer')
 request('/reviews');request('/audit');passed.append('review queue and audit')
 for kind in ['pdf','metrics','holdings','scenarios']:
  body=request('/portfolios/'+pid+'/export/'+kind+query,raw=True)
  assert body.startswith(b'%PDF') if kind=='pdf' else len(body)>50
  if kind=='metrics':
   rows=dict(csv.reader(io.StringIO(body.decode())));assert rows['seed']=='17' and rows['confidence']=='0.99'
 passed.append('all four report exports')
 request('/settings');passed.append('settings')
 request('/auth/logout',{},method='POST')
 try:request('/auth/me');raise AssertionError('Logout did not clear session')
 except urllib.error.HTTPError as e:assert e.code==401
 passed.append('logout')
 print(json.dumps(dict(status='passed',checks=passed,count=len(passed)),indent=2))
except Exception as exc:
 print(json.dumps(dict(status='failed',passed=passed,error=str(exc)),indent=2));raise

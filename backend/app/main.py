import os, json, time, uuid, csv, io, secrets, datetime, threading
from typing import TypedDict
from fastapi import FastAPI, HTTPException, Depends, Request, UploadFile, File
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import create_engine, Column, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from pwdlib import PasswordHash
import jwt
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import RetryPolicy
from .engine import calculate, scenario, SCENARIOS, ASSETS
from .optimization import optimize

DB=os.getenv('DATABASE_URL', 'sqlite:////tmp/aegis.db' if os.getenv('VERCEL') else 'sqlite:///./aegis.db')
if DB.startswith('postgres://'): DB=DB.replace('postgres://','postgresql+psycopg://',1)
if DB.startswith('postgresql://'): DB=DB.replace('postgresql://','postgresql+psycopg://',1)
engine=create_engine(DB,connect_args={'check_same_thread':False} if DB.startswith('sqlite') else {},pool_pre_ping=True)
Session=sessionmaker(bind=engine,expire_on_commit=False)
Base=declarative_base()
class User(Base):
 __tablename__='users'
 id=Column(String,primary_key=True); email=Column(String,unique=True,index=True); password=Column(Text); role=Column(String); name=Column(String)
class Record(Base):
 __tablename__='records'
 id=Column(String,primary_key=True); kind=Column(String,index=True); owner=Column(String,ForeignKey('users.id'),index=True); portfolio_id=Column(String,index=True); payload=Column(Text); created_at=Column(DateTime,default=datetime.datetime.utcnow,index=True); updated_at=Column(DateTime,default=datetime.datetime.utcnow,onupdate=datetime.datetime.utcnow)
Base.metadata.create_all(engine)
passwords=PasswordHash.recommended(); SECRET=os.getenv('JWT_SECRET') or secrets.token_hex(32)
DEMO=os.getenv('DEMO_MODE','true').lower()=='true'
REQUIRE_AUTH=os.getenv('REQUIRE_AUTH','false').lower()=='true'
def put(db,kind,data,owner='demo',pid=None,rid=None):
 r=Record(id=rid or str(uuid.uuid4()),kind=kind,owner=owner,portfolio_id=pid,payload=json.dumps(data)); db.add(r);db.flush();return unpack(r)
def unpack(r): return dict(json.loads(r.payload),id=r.id,created_at=r.created_at.isoformat() if r.created_at else None)
def records(db,kind,owner,pid=None):
 q=db.query(Record).filter_by(kind=kind,owner=owner)
 if pid:q=q.filter_by(portfolio_id=pid)
 return [unpack(x) for x in q.order_by(Record.created_at.desc()).all()]
def seed():
 with Session.begin() as db:
  if not DEMO or db.get(User,'demo'):return
  db.add(User(id='demo',email='analyst@aegis.demo',password=passwords.hash('AegisDemo2026!'),role='analyst',name='Alex Morgan'))
  db.add(User(id='reviewer',email='reviewer@aegis.demo',password=passwords.hash('AegisReview2026!'),role='reviewer',name='Jordan Lee'))
  db.flush()
  for k,(name,style) in enumerate([('Global Growth Fund','Growth'),('Strategic Balanced','Balanced'),('Capital Preservation','Conservative')]):
   hs=[]
   for i,a in enumerate(ASSETS):
    budget=(350000 if i<4 else 130000) if k==0 else (100000 if i<8 else 260000) if k==1 else (40000 if i<8 else 400000)
    hs.append(dict(id=str(uuid.uuid4()),ticker=a[0],name=a[1],asset_class=a[2],sector=a[3],quantity=round(budget/a[4],3),purchase_price=round(a[4]*.89,2),current_price=a[4],currency='USD'))
   put(db,'portfolio',dict(name=name,style=style,description='Synthetic multi-asset demonstration portfolio',holdings=hs),rid=f'demo-{k+1}')
seed()
app=FastAPI(title='AEGIS Portfolio Risk Intelligence',version='1.0.0')
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CORS_ORIGINS','http://localhost:3000').split(','),allow_methods=['GET','POST','PUT','DELETE'],allow_headers=['Authorization','Content-Type'])
limits={};lock=threading.Lock()
@app.middleware('http')
async def guard(request:Request,call_next):
 if request.method in ['POST','PUT','DELETE'] and request.cookies.get('aegis_session') and request.headers.get('sec-fetch-site')=='cross-site':return Response('Cross-site request rejected',403)
 key=(request.client.host if request.client else 'unknown',int(time.time()//60))
 with lock:
  if len(limits)>10000: limits.clear()
  limits[key]=limits.get(key,0)+1
  count=limits[key]
 if count>180:return Response('Rate limit exceeded',429)
 response=await call_next(request);response.headers['X-Content-Type-Options']='nosniff';response.headers['X-Frame-Options']='DENY';response.headers['Cache-Control']='private, no-store';return response
def current(request:Request):
 token=request.headers.get('Authorization','').removeprefix('Bearer ') or request.cookies.get('aegis_session','')
 if not token and DEMO and not REQUIRE_AUTH:return dict(id='demo',role='analyst',name='Alex Morgan',email='analyst@aegis.demo')
 if not token:raise HTTPException(401,'Please sign in to open your workspace.')
 try:
  payload=jwt.decode(token,SECRET,algorithms=['HS256'])
  with Session() as db:
   u=db.get(User,payload['sub'])
   if not u:raise ValueError()
   return dict(id=u.id,role=u.role,name=u.name,email=u.email)
 except Exception: raise HTTPException(401,'Session expired. Please sign in.')
def owned(db,pid,u,write=False):
 r=db.get(Record,pid)
 if not r or r.kind!='portfolio' or (r.owner!=u['id'] and not (DEMO and r.owner=='demo')):raise HTTPException(404,'Portfolio not found')
 if write and r.owner!=u['id']:raise HTTPException(403,'Shared sample portfolios are read-only for this account. Create your own portfolio to edit.')
 return r,unpack(r)
def audit(db,u,action,details):put(db,'audit',dict(actor=u['email'],action=action,details=details),u['id'])
def save_payload(r,p):r.payload=json.dumps({k:v for k,v in p.items() if k not in ['id','created_at']});r.updated_at=datetime.datetime.utcnow()
class Credentials(BaseModel):
 email:str=Field(min_length=5,max_length=200);password:str=Field(min_length=12,max_length=200);name:str=Field(default='Portfolio Analyst',max_length=100)
class PortfolioInput(BaseModel):
 name:str=Field(min_length=1,max_length=100);style:str=Field(default='Balanced',max_length=40);description:str=Field(default='',max_length=1000)
class HoldingInput(BaseModel):
 model_config=ConfigDict(extra='ignore',allow_inf_nan=False)
 ticker:str=Field(min_length=1,max_length=15);name:str=Field(min_length=1,max_length=100);asset_class:str;sector:str=Field(min_length=1,max_length=80);quantity:float=Field(gt=0,le=1e12);purchase_price:float=Field(gt=0,le=1e9);current_price:float=Field(gt=0,le=1e9);currency:str='USD'
def validate_holding(h):
 if h.asset_class not in ['Equity','Bond','Commodity','Real Estate'] or h.currency!='USD':raise HTTPException(422,'Supported classes: Equity, Bond, Commodity, Real Estate. USD only.')
 return h.model_dump()
class Config(BaseModel):
 portfolio_id:str;confidence:float=Field(default=.95,ge=.9,le=.999);days:int=Field(default=756,ge=30,le=1260);simulations:int=Field(default=5000,ge=100,le=20000);seed:int=Field(default=42,ge=0,le=2147483647)
class Shock(BaseModel):
 model_config=ConfigDict(allow_inf_nan=False)
 name:str=Field(default='Custom Scenario',max_length=100);equity:float=Field(default=-30,ge=-100,le=100);bond:float=Field(default=4,ge=-100,le=100);commodity:float=Field(default=-8,ge=-100,le=100);real_estate:float=Field(default=-22,ge=-100,le=100);rate:float=Field(default=0,ge=-10,le=20);inflation:float=Field(default=0,ge=-20,le=30);fx:float=Field(default=0,ge=-100,le=100);technology:float=Field(default=0,ge=-100,le=100)
@app.get('/api/health')
def health():return dict(status='ok',demo=DEMO,database='postgresql' if 'postgres' in DB else 'sqlite',durable=not bool(os.getenv('VERCEL')) or 'postgres' in DB)
@app.post('/api/auth/register')
def register(c:Credentials,response:Response):
 with Session.begin() as db:
  if db.query(User).filter_by(email=c.email.lower()).first():raise HTTPException(409,'Email already registered')
  uid=str(uuid.uuid4());db.add(User(id=uid,email=c.email.lower(),password=passwords.hash(c.password),role='analyst',name=c.name))
 return login(c,response)
@app.post('/api/auth/login')
def login(c:Credentials,response:Response):
 with Session() as db:
  u=db.query(User).filter_by(email=c.email.lower()).first()
  if not u or not passwords.verify(c.password,u.password):raise HTTPException(401,'Invalid email or password')
  token=jwt.encode(dict(sub=u.id,exp=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=8)),SECRET,algorithm='HS256')
  response.set_cookie('aegis_session',token,httponly=True,secure=bool(os.getenv('VERCEL')),samesite='strict',max_age=28800,path='/')
  return dict(token=token,user=dict(id=u.id,email=u.email,name=u.name,role=u.role))
@app.post('/api/auth/logout')
def logout(response:Response):
 response.delete_cookie('aegis_session',path='/');return dict(ok=True)
@app.get('/api/auth/me')
def me(u=Depends(current)):return u
@app.get('/api/portfolios')
def portfolios(u=Depends(current)):
 with Session() as db:
  out=records(db,'portfolio',u['id'])
  if DEMO and u['id']!='demo':out+=records(db,'portfolio','demo')
  return out
@app.post('/api/portfolios')
def create_portfolio(p:PortfolioInput,u=Depends(current)):
 with Session.begin() as db:return put(db,'portfolio',dict(**p.model_dump(),holdings=[]),u['id'])
@app.get('/api/portfolios/{pid}')
def portfolio(pid:str,u=Depends(current)):
 with Session() as db:return owned(db,pid,u)[1]
@app.put('/api/portfolios/{pid}')
def update_portfolio(pid:str,p:PortfolioInput,u=Depends(current)):
 with Session.begin() as db:
  r,data=owned(db,pid,u,write=True);data.update(p.model_dump());save_payload(r,data);audit(db,u,'Portfolio updated',pid);return data
@app.delete('/api/portfolios/{pid}')
def delete_portfolio(pid:str,u=Depends(current)):
 with Session.begin() as db:r,_=owned(db,pid,u,write=True);db.delete(r);audit(db,u,'Portfolio deleted',pid)
 return dict(ok=True)
@app.get('/api/portfolios/{pid}/holdings')
def holdings(pid:str,u=Depends(current)):return portfolio(pid,u)['holdings']
@app.post('/api/portfolios/{pid}/holdings')
def add_holding(pid:str,h:HoldingInput,u=Depends(current)):
 with Session.begin() as db:
  r,p=owned(db,pid,u,write=True)
  if len(p['holdings'])>=100:raise HTTPException(422,'Maximum 100 holdings')
  p['holdings'].append(dict(**validate_holding(h),id=str(uuid.uuid4())));save_payload(r,p);audit(db,u,'Holding added',h.ticker);return p
@app.put('/api/portfolios/{pid}/holdings/{hid}')
def edit_holding(pid:str,hid:str,h:HoldingInput,u=Depends(current)):
 with Session.begin() as db:
  r,p=owned(db,pid,u,write=True)
  if not any(x['id']==hid for x in p['holdings']):raise HTTPException(404,'Holding not found')
  p['holdings']=[dict(**validate_holding(h),id=hid) if x['id']==hid else x for x in p['holdings']];save_payload(r,p);audit(db,u,'Holding updated',hid);return p
@app.delete('/api/portfolios/{pid}/holdings/{hid}')
def remove_holding(pid:str,hid:str,u=Depends(current)):
 with Session.begin() as db:
  r,p=owned(db,pid,u,write=True);p['holdings']=[x for x in p['holdings'] if x['id']!=hid];save_payload(r,p);audit(db,u,'Holding removed',hid);return p
@app.post('/api/portfolios/{pid}/upload-csv')
async def upload(pid:str,file:UploadFile=File(...),u=Depends(current)):
 raw=await file.read(1000001)
 if len(raw)>1000000:raise HTTPException(413,'CSV must be below 1 MB')
 try:
  rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
  if not rows or len(rows)>100:raise ValueError('CSV requires 1–100 holdings')
  hs=[dict(**validate_holding(HoldingInput(**r)),id=str(uuid.uuid4())) for r in rows]
 except Exception as e:raise HTTPException(422,'Invalid CSV. Required: ticker,name,asset_class,sector,quantity,purchase_price,current_price,currency (USD).') from e
 with Session.begin() as db:r,p=owned(db,pid,u,write=True);p['holdings']=hs;save_payload(r,p);audit(db,u,'CSV holdings replaced',pid)
 return p
@app.get('/api/portfolios/{pid}/analytics')
def analytics(pid:str,confidence:float=.95,days:int=756,simulations:int=5000,seed:int=42,u=Depends(current)):
 try:return calculate(portfolio(pid,u)['holdings'],confidence,days,simulations,seed)
 except ValueError as e:raise HTTPException(422,str(e))
@app.get('/api/scenarios')
def scenarios():return SCENARIOS
@app.post('/api/portfolios/{pid}/simulate')
def simulate(pid:str,s:Shock,u=Depends(current)):
 result=scenario(portfolio(pid,u)['holdings'],s.model_dump())
 with Session.begin() as db:return put(db,'scenario_result',result,u['id'],pid)
@app.get('/api/portfolios/{pid}/scenarios')
def saved_scenarios(pid:str,u=Depends(current)):
 with Session() as db:owned(db,pid,u);return records(db,'scenario_result',u['id'],pid)

class Alternative(BaseModel):
 style:str;confidence:float=Field(default=.95,ge=.9,le=.999);days:int=Field(default=756,ge=30,le=1260);simulations:int=Field(default=5000,ge=100,le=20000);seed:int=Field(default=42,ge=0,le=2147483647)
@app.post('/api/portfolios/{pid}/counterfactual')
def counterfactual(pid:str,c:Alternative,u=Depends(current)):
 targets={'Conservative':[.25,.55,.15,.05],'Balanced':[.5,.3,.1,.1],'Growth':[.75,.1,.05,.1]}
 if c.style not in targets:raise HTTPException(422,'Unknown allocation style')
 p=portfolio(pid,u);original=analytics(pid,c.confidence,c.days,c.simulations,c.seed,u);hs=[dict(h) for h in p['holdings']];classes=['Equity','Bond','Commodity','Real Estate']
 present=[a for a in classes if any(h['asset_class']==a for h in hs)]
 total=sum(targets[c.style][classes.index(a)] for a in present)
 allocation={a:targets[c.style][classes.index(a)]/total for a in present}
 for h in hs:
  count=sum(x['asset_class']==h['asset_class'] for x in hs)
  h['quantity']=original['value']*allocation[h['asset_class']]/count/h['current_price']
 return dict(metrics=calculate(hs,c.confidence,c.days,c.simulations,c.seed),allocation=allocation,method=f'Explicit class target weights, equal weights within each class, normalized over available classes. Same {c.days}-day history, seed {c.seed}; no optimization or trade execution.')

class OptimizationInput(BaseModel):
 minimum:float=Field(default=0,ge=0,le=1);maximum:float=Field(default=.25,gt=0,le=1);sector_cap:float=Field(default=.55,gt=0,le=1);target_return:float|None=Field(default=None,ge=-1,le=1);transaction_cost:float=Field(default=.001,ge=0,le=.1);risk_aversion:float=Field(default=5,gt=0,le=100);days:int=Field(default=756,ge=30,le=1260);seed:int=Field(default=42,ge=0,le=2147483647)
@app.post('/api/portfolios/{pid}/optimize')
def optimization(pid:str,c:OptimizationInput,u=Depends(current)):
 try:result=optimize(portfolio(pid,u)['holdings'],**c.model_dump())
 except ValueError as e:raise HTTPException(422,str(e))
 with Session.begin() as db:
  saved=put(db,'optimization',result,u['id'],pid);audit(db,u,'Optimization simulated',saved['id']);return saved

AGENTS=[('Portfolio Analysis','Allocation and concentration'),('Market Intelligence','Synthetic market regime and assumptions'),('Quantitative Risk','Validated deterministic risk metrics'),('Scenario Simulation','Seven economic stress scenarios'),('Explainability','Evidence-linked risk attribution'),('Recommendation','Constrained allocation alternatives'),('Human Review','Human decision gate'),('Report Generation','Consolidated analytical report')]
def findings(metrics,hs):
 ranked=sorted(zip(hs,metrics['weights'],metrics['risk_contributions']),key=lambda x:x[2],reverse=True)
 return [dict(title=f"{h['ticker']} contributes {c:.1%} of variance",evidence=f"Weight {w:.1%}; Euler covariance decomposition wᵢ(Σw)ᵢ/(wᵀΣw).",ticker=h['ticker'],contribution=c,weight=w) for h,w,c in ranked]
def recommendations(m,hs):
 top=max(range(len(hs)),key=lambda i:m['weights'][i]);h=hs[top]
 return [dict(title=f"Review {h['ticker']} concentration",reason=f"Largest position is {m['weights'][top]:.1%} of portfolio value.",metric=m['weights'][top],tradeoff='Rebalancing can incur taxes and transaction costs; returns can decrease.',status='Pending Review',evidence='Calculated allocation',impact='Compare alternative allocations before making a decision.'),dict(title='Evaluate defensive diversification',reason=f"Annualized synthetic volatility is {m['volatility']:.1%}; concentration index is {m['concentration']:.3f}.",metric=m['volatility'],tradeoff='Defensive assets may underperform in rising equity markets.',status='Pending Review',evidence='Deterministic historical covariance',impact='Educational simulation; no guaranteed risk reduction.')]
class State(TypedDict):
 portfolio:dict; metrics:dict; outputs:list; recommendations:list; needs_review:bool
def node(index):
 def run(s):
  t=time.perf_counter();m=s['metrics'];hs=s['portfolio']['holdings']
  out=[dict(allocation=m['allocation'],concentration=m['concentration']),dict(source=m['source'],observations=m['days'],volatility_regime='Elevated' if m['volatility']>.2 else 'Normal',seed=m['seed']),{k:m[k] for k in ['historical_var','cvar','volatility','sharpe','beta']},[scenario(hs,c) for c in SCENARIOS],findings(m,hs),recommendations(m,hs),dict(status='Awaiting Approval',reason='All allocation recommendations require explicit human review.'),dict(summary=f"Portfolio value ${m['value']:,.2f}; composite risk score {m['risk_score']}/100. Unapproved educational recommendations.")][index]
  result=dict(agent=AGENTS[index][0],purpose=AGENTS[index][1],status='Awaiting Approval' if index==6 else 'Completed',duration_ms=round((time.perf_counter()-t)*1000,2),output=out,timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat())
  return dict(outputs=s['outputs']+[result],recommendations=out if index==5 else s.get('recommendations',[]),needs_review=True)
 return run
graph=StateGraph(State)
for i in range(8):graph.add_node(str(i),node(i),retry_policy=RetryPolicy(max_attempts=2))
graph.add_edge(START,'0')
for i in range(6):graph.add_edge(str(i),str(i+1))
graph.add_conditional_edges('6',lambda s:'review' if s['needs_review'] else 'report',{'review':END,'report':'7'})
graph.add_edge('7',END)
workflow=graph.compile(checkpointer=InMemorySaver())
@app.post('/api/agents/run-analysis')
def run_analysis(c:Config,u=Depends(current)):
 p=portfolio(c.portfolio_id,u)
 try:m=json.loads(json.dumps(calculate(p['holdings'],c.confidence,c.days,c.simulations,c.seed)))
 except ValueError as e:raise HTTPException(422,str(e))
 run_id=str(uuid.uuid4());t=time.perf_counter()
 state=workflow.invoke(dict(portfolio=p,metrics=m,outputs=[],recommendations=[],needs_review=False),dict(configurable=dict(thread_id=run_id)))
 with Session.begin() as db:
  recs=[put(db,'recommendation',r,u['id'],c.portfolio_id) for r in state['recommendations']]
  result=put(db,'analysis',dict(metrics=m,agents=state['outputs']+[dict(agent='Report Generation',purpose=AGENTS[7][1],status='Awaiting Approval',duration_ms=0,output={'reason':'Generate report after review, or export an unapproved analytical draft.'})],findings=findings(m,p['holdings']),recommendations=recs,duration_ms=round((time.perf_counter()-t)*1000,2),config=c.model_dump(),portfolio_snapshot=p),u['id'],c.portfolio_id,run_id)
  audit(db,u,'Analysis completed',run_id)
 return result
@app.get('/api/portfolios/{pid}/analyses')
def analyses(pid:str,u=Depends(current)):
 with Session() as db:owned(db,pid,u);return records(db,'analysis',u['id'],pid)
@app.get('/api/portfolios/{pid}/recommendations')
def recs(pid:str,u=Depends(current)):
 with Session() as db:owned(db,pid,u);return records(db,'recommendation',u['id'],pid)
@app.post('/api/recommendations/{rid}/submit-review')
def submit(rid:str,u=Depends(current)):
 with Session.begin() as db:
  r=db.get(Record,rid)
  if not r or r.owner!=u['id'] or r.kind!='recommendation':raise HTTPException(404,'Recommendation not found')
  existing=db.query(Record).filter_by(kind='review',portfolio_id=r.portfolio_id).all()
  for e in existing:
   if json.loads(e.payload).get('recommendation_id')==rid:return unpack(e)
  return put(db,'review',dict(recommendation_id=rid,recommendation=unpack(r),status='Pending Review',history=[]),r.owner,r.portfolio_id)
@app.get('/api/reviews')
def reviews(u=Depends(current)):
 with Session() as db:
  q=db.query(Record).filter_by(kind='review')
  if u['role'] not in ['reviewer','administrator']:q=q.filter_by(owner=u['id'])
  return [unpack(x) for x in q.order_by(Record.created_at.desc()).all()]
class Decision(BaseModel):
 status:str;comment:str=Field(min_length=5,max_length=2000)
@app.post('/api/reviews/{rid}/decision')
def decide(rid:str,d:Decision,u=Depends(current)):
 if u['role'] not in ['reviewer','administrator']:raise HTTPException(403,'A signed-in reviewer is required')
 if d.status not in ['Approved','Rejected','Needs Revision']:raise HTTPException(422,'Invalid decision')
 with Session.begin() as db:
  r=db.get(Record,rid)
  if not r or r.kind!='review':raise HTTPException(404,'Review not found')
  p=unpack(r);p['status']=d.status;p['history'].append(dict(status=d.status,comment=d.comment,reviewer=u['email'],at=datetime.datetime.now(datetime.timezone.utc).isoformat()));save_payload(r,p)
  rec=db.get(Record,p['recommendation_id']);rp=unpack(rec);rp['status']=d.status;save_payload(rec,rp);audit(db,u,'Review '+d.status,dict(review=rid,comment=d.comment));return p
@app.get('/api/audit')
def audits(u=Depends(current)):
 with Session() as db:return records(db,'audit',u['id'])
@app.get('/api/settings')
def settings(u=Depends(current)):
 with Session() as db:
  rows=records(db,'settings',u['id']);return rows[0] if rows else dict(confidence=.95,days=756,simulations=5000,seed=42,risk_tolerance='Balanced')
class Preferences(BaseModel):
 confidence:float=Field(default=.95,ge=.9,le=.999);days:int=Field(default=756,ge=30,le=1260);simulations:int=Field(default=5000,ge=100,le=20000);seed:int=Field(default=42,ge=0,le=2147483647);risk_tolerance:str=Field(default='Balanced',max_length=30)
@app.put('/api/settings')
def set_settings(p:Preferences,u=Depends(current)):
 with Session.begin() as db:
  db.query(Record).filter_by(kind='settings',owner=u['id']).delete();return put(db,'settings',p.model_dump(),u['id'])
class Question(BaseModel):
 question:str=Field(min_length=2,max_length=500)
@app.post('/api/portfolios/{pid}/chat')
def chat(pid:str,q:Question,u=Depends(current)):
 m=analytics(pid,u=u);text=q.question.lower()
 if any(x in text for x in ['var','loss','tail']):answer=f"One-day historical VaR at {m['confidence']:.0%} is ${m['historical_var']:,.2f}; CVaR is ${m['cvar']:,.2f}. These are synthetic historical estimates, not a maximum possible loss."
 elif any(x in text for x in ['return','sharpe']):answer=f"Annualized arithmetic mean return is {m['expected_return']:.1%}; Sharpe ratio is {m['sharpe']:.2f}, using a 4% annual risk-free assumption. Future returns are unknown."
 else:answer=f"Composite risk score is {m['risk_score']}/100; annualized volatility is {m['volatility']:.1%}, maximum drawdown {m['max_drawdown']:.1%}, and concentration HHI {m['concentration']:.3f}. Open Explainability for asset contributions."
 return dict(answer=answer,provider='Deterministic evidence retrieval',evidence=dict(model=m['model_version'],seed=m['seed'],days=m['days']))
@app.get('/api/portfolios/{pid}/export/{kind}')
def export(pid:str,kind:str,confidence:float=.95,days:int=756,simulations:int=5000,seed:int=42,u=Depends(current)):
 p=portfolio(pid,u);m=analytics(pid,confidence,days,simulations,seed,u)
 if kind=='pdf':
  from reportlab.pdfgen import canvas
  from reportlab.lib.colors import HexColor
  buf=io.BytesIO();c=canvas.Canvas(buf);c.setTitle('AEGIS Portfolio Risk Report');y=790
  def line(text,size=11):
   nonlocal y
   if y<55:c.showPage();y=790
   c.setFillColor(HexColor('#151B2D'));c.setFont('Helvetica',size);c.drawString(45,y,str(text)[:105]);y-=21
  line('AEGIS / PORTFOLIO RISK INTELLIGENCE',20);line(p['name'],16);line('Analytical draft | Recommendations require explicit human review.');line('Synthetic market data. Educational simulation. Not investment advice.');line(datetime.datetime.now(datetime.timezone.utc).isoformat());line('RISK METRICS',14)
  for k in ['value','invested','expected_return','volatility','historical_var','cvar','parametric_var','monte_carlo_var','max_drawdown','sharpe','sortino','beta','concentration','risk_score']:line(f'{k.replace("_"," ").title()}: {m[k]:,.4f}')
  line('HOLDINGS',14)
  for h in p['holdings']:line(f"{h['ticker']} | {h['asset_class']} | {h['quantity']:,.3f} units | USD {h['quantity']*h['current_price']:,.2f}")
  line('STRESS TESTS',14)
  for s in SCENARIOS:
   result=scenario(p['holdings'],s);line(f"{s['name']}: loss {result['loss_pct']:.2%}, USD {result['loss']:,.2f}")
  line('RISK DRIVERS',14)
  for f in findings(m,p['holdings']):line(f['title'])
  line('REVIEW STATUS',14)
  with Session() as db:
   review_rows=db.query(Record).filter_by(kind='review',portfolio_id=pid).all()
   for r in review_rows:
    item=unpack(r);line(f"{item['recommendation']['title']}: {item['status']}")
  line('METHODOLOGY',14);line('Daily simple returns; 252 trading days/year; arithmetic mean annualization.');line(f'VaR/CVaR are nonnegative one-day USD loss estimates. Confidence: {confidence:.0%}.');line(f'Synthetic one-factor model, seed {seed}; {days} observations; constant current weights.');line('Composite: volatility 35%, drawdown 25%, concentration 25%, tail risk 15%.');line('No live pricing, predictive guarantee, trade execution or regulatory certification.');c.save();content=buf.getvalue();mime='application/pdf'
 else:
  buf=io.StringIO();w=csv.writer(buf)
  if kind=='holdings':
   cols=['ticker','name','asset_class','sector','quantity','purchase_price','current_price','currency'];w.writerow(cols)
   for h in p['holdings']:w.writerow([("'"+str(h[k])) if isinstance(h[k],str) and str(h[k]).startswith(('=','+','-','@')) else h[k] for k in cols])
  elif kind=='scenarios':
   w.writerow(['scenario','before','after','loss','loss_pct'])
   for s in SCENARIOS:
    r=scenario(p['holdings'],s);w.writerow([r[k] for k in ['name','before','after','loss','loss_pct']])
  elif kind=='metrics':
   w.writerow(['metric','value']);w.writerows((k,v) for k,v in m.items() if isinstance(v,(float,int,str)))
  else:raise HTTPException(404,'Export not found')
  content=buf.getvalue().encode();mime='text/csv'
 with Session.begin() as db:put(db,'report',dict(name=p['name'],format=kind,bytes=len(content)),u['id'],pid);audit(db,u,'Report exported',kind)
 return Response(content,media_type=mime,headers={'Content-Disposition':f'attachment; filename="aegis-{kind}.{ "pdf" if kind=="pdf" else "csv"}"'})

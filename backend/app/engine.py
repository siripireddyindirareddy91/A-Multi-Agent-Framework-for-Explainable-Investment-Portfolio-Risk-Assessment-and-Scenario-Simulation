"""Reproducible synthetic-data risk engine. USD only; daily simple returns."""
import numpy as np
from scipy.stats import norm

MODEL_VERSION = 'aegis-1.0'
ASSETS = [
 ('AAPL','Apple Inc.','Equity','Technology',228.5,.24),('MSFT','Microsoft','Equity','Technology',423.2,.22),
 ('NVDA','NVIDIA','Equity','Technology',139.4,.42),('GOOGL','Alphabet','Equity','Communication',175.3,.27),
 ('JPM','JPMorgan Chase','Equity','Financials',242.1,.23),('JNJ','Johnson & Johnson','Equity','Healthcare',156.2,.15),
 ('XOM','Exxon Mobil','Equity','Energy',118.4,.25),('VTI','US Total Market','Equity','Broad Market',289.1,.18),
 ('BND','Total Bond Market','Bond','Fixed Income',73.2,.055),('TLT','Long Treasury','Bond','Fixed Income',92.4,.12),
 ('GLD','SPDR Gold','Commodity','Commodities',245.1,.16),('VNQ','Real Estate ETF','Real Estate','Real Estate',96.3,.22)]

def history(holdings, days=756, seed=42):
 rng=np.random.default_rng(seed)
 market=rng.normal(.00025,.009,days)
 # One shared market factor plus independent asset residuals. Not live data.
 series=[]
 for h in holdings:
  known=next((a for a in ASSETS if a[0]==h['ticker']),None)
  vol=known[5] if known else .22
  beta=.12 if h['asset_class']=='Bond' else .18 if h['asset_class']=='Commodity' else 1.0
  series.append(.00015+beta*market+rng.normal(0,vol/np.sqrt(252)*.65,days))
 return np.asarray(series).T,market

def calculate(holdings,confidence=.95,days=756,simulations=5000,seed=42):
 if not holdings: raise ValueError('Add at least one holding before analysis.')
 values=np.array([h['quantity']*h['current_price'] for h in holdings],dtype=float)
 if not np.isfinite(values).all() or np.any(values<=0): raise ValueError('Holding values must be finite and positive.')
 if any(h.get('currency','USD')!='USD' for h in holdings): raise ValueError('Convert holdings to USD before analysis; FX conversion is not connected.')
 if days<30 or days>1260 or not .9<=confidence<=.999 or not 100<=simulations<=20000: raise ValueError('Invalid analysis configuration.')
 value=float(values.sum()); w=values/value
 r,market=history(holdings,days,seed); p=r@w
 std=float(p.std(ddof=1)); mean=float(p.mean()); q=float(np.quantile(p,1-confidence))
 wealth=np.r_[1,np.cumprod(1+p)]; dd=wealth/np.maximum.accumulate(wealth)-1
 cov=np.atleast_2d(np.cov(r,rowvar=False)); variance=float(w@cov@w)
 contrib=w*(cov@w)/variance if variance>0 else w*0
 downside=float(np.sqrt(np.mean(np.minimum(p-.04/252,0)**2))*np.sqrt(252))
 rng=np.random.default_rng(seed); draws=rng.normal(mean,std,simulations)
 mc=float(max(0,-np.quantile(draws,1-confidence))*value)
 vol=std*np.sqrt(252); mdd=float(dd.min()); hhi=float(w@w)
 score=round(100*(.35*min(vol/.4,1)+.25*min(abs(mdd)/.5,1)+.25*min(hhi/.3,1)+.15*min(max(0,-q)/.05,1)))
 invested=sum(h['quantity']*h['purchase_price'] for h in holdings)
 allocation={}; sectors={}
 for h,v in zip(holdings,values):
  allocation[h['asset_class']]=allocation.get(h['asset_class'],0)+float(v)
  sectors[h['sector']]=sectors.get(h['sector'],0)+float(v)
 performance=[{'day':int(i),'portfolio':round(float(wealth[i]*value/wealth[-1]),2),'benchmark':round(float(np.prod(1+market[:i])*value/wealth[-1]),2)} for i in range(0,days+1,max(1,days//90))]
 return dict(value=value,invested=invested,unrealized_return=value/invested-1 if invested else 0,expected_return=mean*252,volatility=float(vol),daily_volatility=std,historical_var=max(0,-q)*value,cvar=max(0,-float(p[p<=q].mean()))*value,parametric_var=max(0,-mean+norm.ppf(confidence)*std)*value,monte_carlo_var=mc,max_drawdown=mdd,sharpe=float((mean*252-.04)/vol) if vol else 0,sortino=float((mean*252-.04)/downside) if downside else 0,beta=float(np.cov(p,market)[0,1]/np.var(market,ddof=1)),tracking_error=float(np.std(p-market,ddof=1)*np.sqrt(252)),concentration=hhi,risk_score=score,weights=w.tolist(),risk_contributions=contrib.tolist(),correlations=np.nan_to_num(np.atleast_2d(np.corrcoef(r,rowvar=False)),nan=0).tolist(),allocation=allocation,sectors=sectors,performance=performance,confidence=confidence,days=days,seed=seed,simulations=simulations,model_version=MODEL_VERSION,source='Synthetic daily returns; not verified live market data',holding_count=len(holdings))

SCENARIOS=[dict(id='crash',name='Market Crash',description='Broad equity sell-off with a defensive bond rally.',equity=-30,bond=4,commodity=-8,real_estate=-22,rate=0,inflation=0,fx=0,technology=0),dict(id='inflation',name='Inflation Surge',description='Inflation reprices bonds and lifts commodity prices.',equity=-12,bond=-9,commodity=18,real_estate=-8,rate=0,inflation=0,fx=0,technology=0),dict(id='rates',name='Interest Rate Hike',description='A 200 basis point parallel yield increase.',equity=-8,bond=0,commodity=-3,real_estate=-15,rate=2,inflation=0,fx=0,technology=0),dict(id='recession',name='Global Recession',description='A synchronized contraction across growth assets.',equity=-22,bond=7,commodity=-15,real_estate=-18,rate=0,inflation=0,fx=0,technology=0),dict(id='currency',name='Currency Depreciation',description='USD purchasing-power shock applied to all exposures.',equity=0,bond=0,commodity=0,real_estate=0,rate=0,inflation=0,fx=-10,technology=0),dict(id='tech',name='Technology Crash',description='Sector-specific shock to technology holdings.',equity=-5,bond=2,commodity=3,real_estate=-4,rate=0,inflation=0,fx=0,technology=-30),dict(id='banking',name='Banking Crisis',description='Broad risk-off financial conditions.',equity=-20,bond=6,commodity=10,real_estate=-25,rate=0,inflation=0,fx=0,technology=0)]

def scenario(holdings,config):
 impacts=[]
 for h in holdings:
  base={'Equity':'equity','Bond':'bond','Commodity':'commodity','Real Estate':'real_estate'}[h['asset_class']]
  shock=float(config.get(base,0))+float(config.get('fx',0))-float(config.get('inflation',0))
  if h['asset_class']=='Bond': shock-=float(config.get('rate',0))*6
  if h['sector']=='Technology': shock+=float(config.get('technology',0))
  shock=max(-100,shock)/100; before=h['quantity']*h['current_price']
  impacts.append(dict(ticker=h['ticker'],sector=h['sector'],before=before,after=before*(1+shock),impact=before*shock,shock=shock))
 before=sum(x['before'] for x in impacts); after=sum(x['after'] for x in impacts)
 return dict(name=config.get('name','Custom scenario'),before=before,after=after,loss=before-after,loss_pct=(before-after)/before if before else 0,impacts=impacts,assumptions='Additive one-period shocks, bonds use 6-year duration. Inflation is a purchasing-power haircut; FX is a uniform sensitivity. No trading or liquidity costs.',config=config)

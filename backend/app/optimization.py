"""Constrained long-only mean/variance portfolio optimization."""
import numpy as np
from scipy.optimize import minimize
from .engine import history, calculate

def optimize(holdings,minimum=0,maximum=.25,sector_cap=.55,target_return=None,transaction_cost=.001,risk_aversion=5,days=756,seed=42):
 n=len(holdings)
 if not n or minimum*n>1 or maximum*n<1:raise ValueError('Weight bounds cannot sum to 100%.')
 values=np.array([h['quantity']*h['current_price'] for h in holdings]);value=float(values.sum());original=values/value
 returns,_=history(holdings,days,seed);cov=np.atleast_2d(np.cov(returns,rowvar=False))*252;means=returns.mean(axis=0)*252
 constraints=[{'type':'eq','fun':lambda w:float(w.sum()-1)}]
 for sector in set(h['sector'] for h in holdings):
  mask=np.array([h['sector']==sector for h in holdings],dtype=float)
  constraints.append({'type':'ineq','fun':lambda w,mask=mask:float(sector_cap-mask@w)})
 if target_return is not None:constraints.append({'type':'ineq','fun':lambda w:float(means@w-target_return)})
 def objective(w):return float(risk_aversion*(w@cov@w)-means@w+transaction_cost*np.abs(w-original).sum())
 result=minimize(objective,np.full(n,1/n),method='SLSQP',bounds=[(minimum,maximum)]*n,constraints=constraints,options={'maxiter':500,'ftol':1e-10})
 if not result.success:raise ValueError('No feasible solution for these constraints. Relax sector, return or weight limits.')
 weights=result.x
 if abs(weights.sum()-1)>1e-6 or any(c['fun'](weights)<-1e-6 for c in constraints[1:]):raise ValueError('Solver result failed constraint validation.')
 # Keep zero-weight assets at a numerical epsilon to preserve the same seeded
 # asset-column history; removing columns would change residual RNG alignment.
 alternative=[dict(h,quantity=value*max(float(w),1e-12)/h['current_price']) for h,w in zip(holdings,weights)]
 return dict(weights=[dict(ticker=h['ticker'],sector=h['sector'],current=float(old),proposed=float(w)) for h,old,w in zip(holdings,original,weights)],metrics=calculate(alternative,days=days,seed=seed),turnover=float(np.abs(weights-original).sum()),estimated_transaction_cost=float(value*transaction_cost*np.abs(weights-original).sum()),solver='SciPy SLSQP',objective='Risk-adjusted annualized arithmetic return minus proportional turnover costs',status='Pending Review',constraints=dict(minimum=minimum,maximum=maximum,sector_cap=sector_cap,target_return=target_return,risk_aversion=risk_aversion),disclaimer='Synthetic-data educational optimization; no holdings changed and no trades executed.')

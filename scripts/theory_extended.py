"""Independent DDE integration and extended numerical falsification campaign."""
import csv, json, math
from pathlib import Path
import numpy as np
from scipy.integrate import solve_ivp, cumulative_trapezoid
from scipy.optimize import brentq
from lag_audit.thresholds import Threshold, optimal_beta, delayed_exp, zcl_bound, alpha
from lag_audit.theory import random_audit, adversary, audit_instance, coarse_counterexample
from lag_audit.engine import Job, Proposal, Policy
from lag_audit.oracles import integer_knapsack, brute_force


def dde(beta, u, delta, rtol=1e-10):
    """Method of steps using RK45 with dense interpolation of past segments.

    Independent of delayed_exp and its polynomial expansion. History y(u)=1.
    """
    if u<=0: return 1.0
    if delta==0:
        return float(solve_ivp(lambda t,y: beta*y, (0,u), [1.],rtol=rtol,atol=rtol/100).y[0,-1])
    segments=[];value=1.;left=0.
    def past(t):
        if t<=0: return 1.
        index=min(int(t/delta),len(segments)-1)
        return float(segments[index](t)[0])
    while left < u-1e-14:
        right=min(u,left+delta)
        sol=solve_ivp(lambda t,y: [beta*past(t-delta)],(left,right),[value],
                      rtol=rtol,atol=rtol/100,dense_output=True,max_step=delta/8)
        if not sol.success: raise ArithmeticError(sol.message)
        segments.append(sol.sol);value=float(sol.y[0,-1]);left=right
    return value


def write_csv(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='results/theory-extended-002')
    out=Path(parser.parse_args().output);out.mkdir(parents=True,exist_ok=False)
    checks=[]
    for ratio in [2,10,100,1000,1e6]:
        for delta in [0,.01,.05,.1,.2,.3,.5,.9,1]:
            beta=optimal_beta(1,ratio,delta)
            hi=max(2,alpha(1,ratio))
            while dde(hi,1-1/hi,delta)<ratio: hi*=2
            numerical=brentq(lambda b:dde(b,1-1/b,delta)-ratio,1,hi,xtol=1e-9)
            error=abs(numerical-beta)/beta
            checks.append(dict(ratio=ratio,delta=delta,beta_series=beta,beta_dde=numerical,relative_error=error))
            assert error<1e-7,(ratio,delta,error)
    write_csv(out/'dde_crosscheck.csv',checks)
    table5=[];convergence=[]
    for ratio in [10,100,1000]:
        for delta in [.05,.1,.2,.3]:
            table5.append(dict(ratio=ratio,delta=delta,zcl=zcl_bound(1,ratio,delta),lag=optimal_beta(1,ratio,delta)))
            for units in [100,400,1600,4000,16000]:
                for kind in ['zcl','lag']:
                    convergence.append(adversary(ratio,delta,units,kind))
    write_csv(out/'table5.csv',table5);write_csv(out/'convergence.csv',convergence)
    table6=[]
    for design in [0,.05,.1,.2,.3]:
        phi=Threshold(1,100,'lag',delta=design)
        for actual in [0,.05,.1,.2,.3]:
            estimates=[]
            for n in [20001,80001]:
                z=np.linspace(0,1,n);p=np.array([phi(x) for x in z])
                floor=np.array([max(1,phi(max(0,x-actual))) for x in z])
                J=cumulative_trapezoid(floor,z,initial=0)
                active=p>1+1e-10
                estimates.append(max(float(np.max(p[active]/J[active])),100/J[-1]))
            table6.append(dict(design_delta=design,actual_delta=actual,worst_case=estimates[-1],grid_difference=abs(estimates[-1]-estimates[0])))
    write_csv(out/'table6.csv',table6)
    campaigns=[random_audit(3000,seed) for seed in [20261015,20261016]]
    (out/'random_campaigns.json').write_text(json.dumps(campaigns,indent=2))
    # Literal size-0.1 prefix: nine low-density jobs leave exactly one job of room.
    phi=Threshold(1,100);jobs=[]
    for i in range(9):
        r=.1;v=max(1,phi(i*r))*r
        jobs.append(Job(Proposal(str(i),r,v,r),r,v,.1,float(i)))
    for i in range(10): jobs.append(Job(Proposal('high'+str(i),.1,10,.1),.1,10,.1,float(10+i)))
    literal=audit_instance(jobs,Policy(phi),1,1000)
    literal['ratio']=literal['opt_r']/literal['alg']
    coarse={'literal_nine_low_then_high':literal,'with_explicit_0.001_filler':coarse_counterexample()}
    (out/'coarse.json').write_text(json.dumps(coarse,indent=2))
    asym=[]
    for ratio in [10,100,1e3,1e4,1e6,1e8,1e12]:
        beta=optimal_beta(1,ratio,.5);exact=math.sqrt(8*ratio)-2
        assert math.isclose(beta,exact,rel_tol=1e-10)
        asym.append(dict(ratio=ratio,beta=beta,closed_form=exact,zcl=zcl_bound(1,ratio,.5),improvement_factor=zcl_bound(1,ratio,.5)/beta))
    write_csv(out/'half_delay.csv',asym)
    rng=np.random.default_rng(20261014)
    for _ in range(500):
        weights=rng.integers(0,15,10).tolist();values=rng.random(10).tolist()
        assert abs(integer_knapsack(weights,values,30)-brute_force(weights,values,30))<1e-9
    summary={'dde_checks':len(checks),'max_relative_dde_error':max(r['relative_error'] for r in checks),'additional_random_instances':6000,'violations':sum(c['violations'] for c in campaigns),'oracle_crosschecks':500,'table6_max_grid_difference':max(r['grid_difference'] for r in table6),'convergence_cases':len(convergence),'formal_proof_checked':False}
    (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
if __name__=='__main__':main()

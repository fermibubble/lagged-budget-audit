"""Seeded local search around near-tight finite instances, not proof checking."""
import json,math
from dataclasses import asdict,replace
from pathlib import Path
import numpy as np
from lag_audit.engine import Job,Proposal,Policy
from lag_audit.theory import audit_instance
from lag_audit.thresholds import Threshold,alpha,zcl_bound,coverage

out=Path('results/theory-search');out.mkdir(parents=True,exist_ok=False)
rng=np.random.default_rng(20261017);tested=0;failures=[];best=None
for restart in range(100):
    ratio=float(rng.choice([2,10,100,1000,1e6]));units=100
    phi=Threshold(1,ratio,['zcl','lag','band','step'][restart%4],delta=.2,forecast=ratio/3,band=.05,step_edges=(.2,.5,.8),step_values=(1,ratio/10,ratio/2,ratio)) if ratio>=10 else Threshold(1,ratio)
    policy=Policy(phi,['committed','settled'][restart%2]);workers=int(rng.integers(1,10))
    jobs=[]
    for i in range(15):
        r=int(rng.integers(1,50))/units;a=int(rng.integers(0,round(r*units)+1))/units
        v=r*math.exp(rng.uniform(0,math.log(ratio)))
        jobs.append(Job(Proposal(str(i),r,v,r),a,v,float(rng.integers(1,20)),float(i)))
    score=math.inf
    for iteration in range(25):
        candidate=list(jobs)
        if iteration:
            i=int(rng.integers(len(jobs)));j=jobs[i];r=j.proposal.reservation
            density=float(rng.choice([1,ratio,max(1,phi(min(1,sum(x.proposal.reservation for x in jobs[:i])))),math.exp(rng.uniform(0,math.log(ratio)))]))
            v=density*r
            candidate[i]=replace(j,proposal=replace(j.proposal,expected_value=v),value=v,duration=float(rng.integers(1,30)))
        audit=audit_instance(candidate,policy,workers,units);tested+=1
        margin=(audit['alg']+audit['lambda']-audit['J']-audit['fractional_opt_r'])/max(1,audit['fractional_opt_r'])
        record={'restart':restart,'iteration':iteration,'units':units,'workers':workers,'policy':asdict(policy),'jobs':[asdict(j) for j in candidate],'audit':audit,'normalized_reservation_dual_slack':margin}
        if audit['failures']:failures.append(record)
        if margin<score:jobs=candidate;score=margin
        if best is None or margin<best['normalized_reservation_dual_slack']:best=record
# Evaluate the band guarantee only when s < 1/alpha and no harmful refusal bound applies.
band=[]
for ratio in [10,100,1000]:
 for s in [0,.03,.1]:
  for delay in [0,.1,.3]:
   for forecast in [0,1,math.sqrt(ratio),ratio]:
    if not s<1/alpha(1,ratio):continue
    phi=Threshold(1,ratio,'band',forecast=forecast,band=s)
    zs=np.linspace(.001,1,1001)
    observed=max([1,ratio/coverage(phi,delay,1)]+[phi(z)/coverage(phi,delay,z) for z in zs if phi(z)>1+1e-10])
    bound=max(alpha(1,ratio)/(1-alpha(1,ratio)*s),math.exp(alpha(1,ratio)*s)*zcl_bound(1,ratio,s+delay))
    band.append({'ratio':ratio,'s':s,'delta':delay,'forecast':forecast,'grid_W':observed,'bound':bound,'passes':observed<=bound+1e-7})
(out/'summary.json').write_text(json.dumps({'seed':20261017,'adaptive_instances':tested,'violations':len(failures),'band_checks':len(band),'band_violations':sum(not r['passes'] for r in band),'formal_proof_checked':False},indent=2))
(out/'violations.json').write_text(json.dumps(failures,indent=2));(out/'nearest_instance.json').write_text(json.dumps(best,indent=2));(out/'band.json').write_text(json.dumps(band,indent=2))
print((out/'summary.json').read_text())

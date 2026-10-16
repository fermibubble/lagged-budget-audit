"""Literal and explicit-filler coarse-item constructions on nine declared settings."""
import csv,json
from pathlib import Path
from lag_audit.engine import Job,Proposal,Policy
from lag_audit.theory import audit_instance
from lag_audit.thresholds import Threshold,alpha
import math
rows=[]
for ratio in [10,100,1000]:
 for size in [.05,.1,.2]:
  phi=Threshold(1,ratio);n=round(1/size)
  for filler in [0.,.001]:
   jobs=[];commitment=0
   for i,r in enumerate([size]*(n-1)+([filler] if filler else [])):
    value=max(1,phi(commitment))*r
    jobs.append(Job(Proposal(str(i),r,value,r),r,value,.1,float(i)));commitment+=r
   for i in range(n):jobs.append(Job(Proposal('high'+str(i),size,ratio*size,size),size,ratio*size,.1,float(n+i)))
   a=audit_instance(jobs,Policy(phi,'committed'),1,1000)
   rows.append({'ratio':ratio,'size':size,'filler':filler,'alg':a['alg'],'opt':a['opt_r'],'competitive_ratio':a['opt_r']/a['alg'],'claimed_small_item_factor':alpha(1,ratio)*math.exp(alpha(1,ratio)*size),'instance_certificate':a['reservation_certificate'],'harmful_refusal':a['harmful_refusal'],'violations':len(a['failures'])})
out=Path('results/theory-coarse-grid');out.mkdir(parents=True,exist_ok=False)
with (out/'constructions.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps({'constructions':len(rows),'violations':sum(r['violations'] for r in rows),'corrected_exceeds_small_item_factor':sum(r['filler']>0 and r['competitive_ratio']>r['claimed_small_item_factor'] for r in rows)}))

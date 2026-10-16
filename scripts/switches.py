"""Predeclared model switches. Full-archive history is privileged information."""
import csv,gzip,itertools,json,subprocess
from pathlib import Path
import numpy as np
from lag_audit.campaign import Runner,PRIMARY,SUBMISSIONS,make_jobs
from lag_audit.prediction import Predictor
from lag_audit.engine import Policy,replay
from lag_audit.thresholds import Threshold
from lag_audit.data import sha256

out=Path('results/switches');out.mkdir(parents=True,exist_ok=False)
split=json.loads(Path('configs/split_map.json').read_text());runners={};inputs={}
for sub in SUBMISSIONS:
 path=Path('data/public')/sub/'normalized.jsonl';inputs[sub]=sha256(path)
 runners[sub]=Runner([json.loads(x) for x in path.read_text().splitlines()],split)
s={**PRIMARY,'workers':1,'feedback':'full_archive'};records=[]
with gzip.open('data/ledger/switches.jsonl.gz','wt') as log:
 for A,B in itertools.permutations(SUBMISSIONS,2):
  for switch in [3,5,7]:
   history=[{**r,'model_identity':'A'} for r in runners[A].warmup];L,U,fixed=runners[A].tune_rows(runners[A].warmup,s)
   previous=None
   for block in range(2,10):
    label='A' if block<switch else 'B';day=[{**r,'model_identity':label} for r in runners[A if label=='A' else B].blocks[block]]
    model=Predictor(6,20261014,include_model_identity=True).fit(history);p,c=model.predict(day)
    forecast=fixed
    if previous is not None:
     old,pp,cc=previous;dens=pp/cc;candidates=np.unique(np.r_[0,np.quantile(dens,np.linspace(0,1,20))]);scored=[]
     for price in candidates:
      rr=replay(make_jobs(old,pp,cc,s),24,1,Policy(Threshold(L,U,'fixed',forecast=float(price)),'committed','expected'),'paper',600)
      scored.append((rr.value_before_deadline,-rr.spend,-float(price),float(price)))
     forecast=max(scored)[3]
    for name in ['hard_cap','zcl_committed','fixed_previous_day_full_archive','banded_previous_day_full_archive']:
     kind='cap' if name=='hard_cap' else ('fixed' if name.startswith('fixed') else ('band' if name.startswith('banded') else 'zcl'))
     result=replay(make_jobs(day,p,c,s),24,1,Policy(Threshold(L,U,kind,forecast=forecast,band=.1),'committed','expected'),'paper',600)
     row={'from_model':A,'to_model':B,'switch_block':switch,'block':block,'relative_block':block-switch,'policy':name,'feedback':'full_archive','resolved_before_deadline':result.value_before_deadline,'resolved_eventual':result.value,'spend':result.spend,'forecast':forecast,'offered':len(day),'training_count':len(history),'cold_start_B':block==switch}
     records.append(row);log.write(json.dumps({'tag':row,'training_ids':[r['id'] for r in history],'test_ids':[r['id'] for r in day],'events':result.events})+'\n')
    previous=(day,p,c);history.extend(day)
with (out/'episodes.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
(out/'manifest.json').write_text(json.dumps({'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'input_sha256':inputs,'scenarios':60,'episodes':len(records),'feedback':'privileged full archive','evaluated_relative_blocks':[-1,0,1],'episodes_sha256':sha256(out/'episodes.csv')},indent=2))
print('Switch episodes',len(records))

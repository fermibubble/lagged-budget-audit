"""Forward grouped pooling sensitivity; independent successes and unique issues differ."""
import csv,gzip,json,subprocess
from pathlib import Path
import numpy as np
from lag_audit.campaign import Runner,PRIMARY,SUBMISSIONS,make_jobs,digest
from lag_audit.engine import Policy,replay
from lag_audit.partitioned import replay_partitioned
from lag_audit.thresholds import Threshold
from lag_audit.data import sha256

out=Path('results/pooling');out.mkdir(parents=True,exist_ok=False)
split=json.loads(Path('configs/split_map.json').read_text());runners={};inputs={}
for sub in SUBMISSIONS:
 p=Path('data/public')/sub/'normalized.jsonl';inputs[sub]=sha256(p)
 runners[sub]=Runner([json.loads(x) for x in p.read_text().splitlines()],split)
eff=np.array([sum(r['resolved'] for r in runners[sub].warmup)/sum(r['actual_cost'] for r in runners[sub].warmup) for sub in SUBMISSIONS])
learned=120*(.1/5+.9*eff/eff.sum());rows=[];logs=[]
private_LU={sub:runners[sub].tune_rows(runners[sub].warmup,PRIMARY)[:2] for sub in SUBMISSIONS}
calibration=[]
for sub in SUBMISSIONS:
 r=runners[sub];n=max(2,int(.7*len(r.warmup)));p,c=r.predict_rows(r.warmup[:n],r.warmup[n:],6.)
 calibration.extend((p/c).tolist())
L=max(1e-8,float(np.quantile(calibration,.05)));U=max(L*1.001,float(np.quantile(calibration,.95)))
logpath=Path('data/ledger/pooling.jsonl.gz');logpath.parent.mkdir(exist_ok=True,parents=True)
with gzip.open(logpath,'wt') as log:
 for workers in [1,16,64]:
  for queue in ['strict','paper','defer']:
   s={**PRIMARY,'budget':120.,'workers':workers,'queue_mode':queue}
   for block in range(2,10):
    jobs=[];accounts={};issue={}
    for sub in SUBMISSIONS:
     r=runners[sub];day=r.blocks[block];p,c=r.predict_rows(r.warmup,day,6.)
     jobs.extend(make_jobs(day,p,c,s));accounts.update({x['id']:sub for x in day});issue.update({x['id']:x['instance_id'] for x in day})
    # Common timestamp/instance order, stable team tie break, no circular rotations.
    meta={row['id']:row for r in runners.values() for row in r.blocks[block]}
    jobs.sort(key=lambda j:(meta[j.proposal.id]['created_at'],meta[j.proposal.id]['instance_id'],SUBMISSIONS.index(accounts[j.proposal.id])))
    variants=['shared_cap','shared_zcl_settled','shared_zcl_committed','shared_zcl_expected','shared_lag_structural','equal_private_cap','equal_private_zcl','learned_private_cap','learned_private_zcl']
    for name in variants:
     if name.startswith('shared'):
      kind='cap' if name=='shared_cap' else ('lag' if name=='shared_lag_structural' else 'zcl')
      signal='settled' if name in ['shared_lag_structural','shared_zcl_settled'] else ('expected' if name=='shared_zcl_expected' else 'committed')
      phi=Threshold(L,U,kind,delta=min(1,workers*6/120));res=replay(jobs,120,workers,Policy(phi,signal,'expected'),queue,600.)
     else:
      budgets=dict(zip(SUBMISSIONS,[24.]*5 if name.startswith('equal') else learned.tolist()))
      policies={sub:Policy(Threshold(*private_LU[sub],kind='cap' if name.endswith('cap') else 'zcl'),'committed','expected') for sub in SUBMISSIONS}
      res=replay_partitioned(jobs,budgets,workers,policies,accounts,queue,600.)
     completed=[e['id'] for e in res.events if e['kind']=='settle' and e['time']<=600.+1e-10 and e['outcome']==1]
     row={'workers':workers,'queue_mode':queue,'policy':name,'block':block,'resolved_before_deadline':res.value_before_deadline,'unique_issues_before_deadline':len({issue[i] for i in completed}),'spend':res.spend,'utilization':res.spend/120,'peak_running':res.peak_running,'delta':res.delta,'completed_late':res.completed_after_deadline,'offered':len(jobs),'admitted':len(res.admitted)}
     rows.append(row);log.write(json.dumps({'tag':row,'events':res.events})+'\n')
with (out/'episodes.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(out/'manifest.json').write_text(json.dumps({'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'input_sha256':inputs,'episodes':len(rows),'learned_private_budgets':dict(zip(SUBMISSIONS,learned.tolist())),'pooled_L':L,'pooled_U':U,'unique_issue_value_additive':False,'seed':20261014,'episodes_sha256':sha256(out/'episodes.csv')},indent=2))
print('Pooling episodes',len(rows))

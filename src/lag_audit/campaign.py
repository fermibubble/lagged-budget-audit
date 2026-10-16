"""Predeclared multi-submission campaign; all results are recorded-trace replay.

Both predictors receive only features from prediction.py. Adaptive feedback and
forecast policies have distinct names. Metadata and diagnostic outcomes never
enter the admission policy.
"""
from __future__ import annotations
import csv,gzip,hashlib,itertools,json,math,platform,subprocess,time
from collections import Counter,defaultdict
from dataclasses import replace
from datetime import datetime,timezone
from functools import lru_cache
from pathlib import Path
import numpy as np
from sklearn.metrics import brier_score_loss,roc_auc_score
from .engine import Policy,replay
from .empirical import jobs_from
from .prediction import Predictor
from .thresholds import Threshold
from .oracles import resolved_count_oracle
from .data import sha256

POLICIES=['hard_cap','zcl_settled','zcl_committed','zcl_expected_inflight','lag_structural','lag_previous_day','fixed_warmup','banded_warmup','fixed_history','banded_history']
PRIMARY={'reservation':6.,'budget':24.,'workers':16,'queue_mode':'paper','feedback':'frozen_warmup','density_mode':'expected','duration_mode':'fixed','deadline':600.,'arrival_mode':'batch'}
SUBMISSIONS=['20240620_sweagent_claude3.5sonnet','20240728_sweagent_gpt4o','20240402_sweagent_gpt4','20240402_sweagent_claude3opus','20250522_sweagent_claude-4-sonnet-20250514']
SEED=20261014

def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True).encode()).hexdigest()

def make_jobs(rows,p,c,scenario):
    jobs=jobs_from(rows,p,c,scenario['reservation'],scenario['duration_mode'],8.,60.)
    if scenario['arrival_mode']=='scaled':
        times=[datetime.fromisoformat(r['created_at'].replace('Z','+00:00')).timestamp() for r in rows]
        low,high=min(times),max(times)
        jobs=[replace(j,arrival=3600*(t-low)/(high-low) if high>low else 0.) for j,t in zip(jobs,times)]
    return jobs

class Runner:
    def __init__(self,rows,split_map):
        self.rows={r['id']:r for r in rows}
        self.blocks=[[r for r in sorted(rows,key=lambda x:(x['created_at'],x['instance_id'])) if split_map[r['instance_id']]==i] for i in range(10)]
        self.warmup=[r for b in self.blocks[:2] for r in b]
        self.predict=lru_cache(maxsize=8000)(self._predict)
        self.tune=lru_cache(maxsize=8000)(self._tune)
    def _predict(self,history_ids,offered_ids,reservation):
        history=[self.rows[i] for i in history_ids];offered=[self.rows[i] for i in offered_ids]
        model=Predictor(reservation,SEED).fit(history)
        return model.predict(offered)
    def predict_rows(self,history,offered,reservation):
        return self.predict(tuple(r['id'] for r in history),tuple(r['id'] for r in offered),reservation)
    def _tune(self,history_ids,scenario_json):
        s=json.loads(scenario_json);history=[self.rows[i] for i in history_ids]
        n=max(2,int(.7*len(history)));fitting,validation=history[:n],history[n:]
        p,c=self.predict_rows(fitting,validation,s['reservation'])
        densities=p/(s['reservation'] if s['density_mode']=='reservation' else c)
        L=max(1e-8,float(np.quantile(densities,.05)));U=max(L*1.001,float(np.quantile(densities,.95)))
        candidates=np.unique(np.r_[0,np.quantile(densities,np.linspace(0,1,20))])
        jobs=make_jobs(validation,p,c,s);scored=[]
        for price in candidates:
            result=replay(jobs,s['budget'],s['workers'],Policy(Threshold(L,U,'fixed',forecast=float(price)),'committed',s['density_mode']),s['queue_mode'],s['deadline'])
            scored.append((result.value_before_deadline,-result.spend,-float(price),float(price)))
        return L,U,max(scored)[3]
    def tune_rows(self,history,s):return self.tune(tuple(r['id'] for r in history),json.dumps(s,sort_keys=True))
    def episodes(self,s,policies=POLICIES):
        # Validate all offered costs, including rejected jobs, before any replay.
        violations=[r['id'] for r in self.rows.values() if r['actual_cost']>s['reservation']+1e-10]
        if violations:raise ValueError('reservation_exceeded: '+str(violations))
        L,U,fixed=self.tune_rows(self.warmup,s)
        for name in policies:
            history=list(self.warmup);previous_delta=min(1,s['workers']*s['reservation']/s['budget'])
            previous=None
            for block in range(2,10):
                day=self.blocks[block];p,c=self.predict_rows(history,day,s['reservation'])
                d=min(1,s['workers']*s['reservation']/s['budget']) if name=='lag_structural' else previous_delta
                price=fixed
                if name in {'fixed_history','banded_history'}:price=self.tune_rows(history,s)[2]
                if name in {'fixed_previous_day_full_archive','banded_previous_day_full_archive'} and previous is not None:
                    old,pp,cc=previous;dens=pp/(s['reservation'] if s['density_mode']=='reservation' else cc)
                    candidates=np.unique(np.r_[0,np.quantile(dens,np.linspace(0,1,20))]);scored=[]
                    for candidate in candidates:
                        rr=replay(make_jobs(old,pp,cc,s),s['budget'],s['workers'],Policy(Threshold(L,U,'fixed',forecast=float(candidate)),'committed',s['density_mode']),s['queue_mode'],s['deadline'])
                        scored.append((rr.value_before_deadline,-rr.spend,-float(candidate),float(candidate)))
                    price=max(scored)[3]
                kind='cap' if name=='hard_cap' else ('lag' if name.startswith('lag_') else ('fixed' if name.startswith('fixed_') else ('band' if name.startswith('banded_') else 'zcl')))
                signal='settled' if name=='zcl_settled' or name.startswith('lag_') else ('expected' if name=='zcl_expected_inflight' else 'committed')
                phi=Threshold(L,U,kind,delta=d,forecast=price,band=.1)
                jobs=make_jobs(day,p,c,s)
                result=replay(jobs,s['budget'],s['workers'],Policy(phi,signal,s['density_mode']),s['queue_mode'],s['deadline'])
                if name=='lag_previous_settled_full_archive':
                    previous_delta=replay(jobs,s['budget'],s['workers'],Policy(Threshold(L,U),'settled',s['density_mode']),s['queue_mode'],s['deadline']).delta
                else:previous_delta=result.delta
                y=np.array([r['resolved'] for r in day]);actual=np.array([r['actual_cost'] for r in day]);dens=p/(s['reservation'] if s['density_mode']=='reservation' else c)
                reasons=Counter(result.rejected.values());admitted=set(result.admitted)
                row={**s,'submission':day[0]['submission'],'policy':name,'block':block,'resolved':result.value,'resolved_before_deadline':result.value_before_deadline,'spend':result.spend,'utilization':result.spend/s['budget'],'cost_per_resolution':result.spend/result.value_before_deadline if result.value_before_deadline else None,'admitted':len(admitted),'offered':len(day),'room_rejections':reasons['room'],'price_rejections':reasons['price'],'deadline_rejections':reasons['deadline'],'peak_running':result.peak_running,'delta':result.delta,'design_delta':d if kind=='lag' else None,'design_delta_exceeded':int(kind=='lag' and result.delta>d+1e-9),'peak_commitment':result.peak_commitment,'completed_late':result.completed_after_deadline,'makespan':result.makespan,'density_excursions':int(np.sum((dens<L)|(dens>U))),'L':L,'U':U,'forecast_price':price,'auc':float(roc_auc_score(y,p)) if len(set(y))>1 else None,'brier':float(brier_score_loss(y,p)),'cost_mae':float(np.mean(abs(c-actual))),'oracle_resolved_relaxation':resolved_count_oracle(actual.tolist(),y.tolist(),s['budget']),'actual_to_reservation_mean':float(np.mean(actual/s['reservation'])),'training_count':len(history),'training_ids_sha256':digest(sorted(r['id'] for r in history)),'realized_certificate_applicable':False}
                record={'tag':{k:row[k] for k in [*s,'submission','policy','block']},'training_ids':sorted(r['id'] for r in history),'test_ids':[r['id'] for r in day],'admitted':result.admitted,'events':result.events}
                yield row,record
                previous=(day,p,c)
                if s['feedback']=='admitted_only':history.extend(r for r in day if r['id'] in admitted)
                elif s['feedback']=='full_archive':history.extend(day)
                elif s['feedback']!='frozen_warmup':raise ValueError('Unknown feedback')

def scenarios():
    yield 'primary',PRIMARY
    for r,b,w,q,f,d in itertools.product([6.,12.],[24.,96.],[1,4,16,64],['strict','paper','defer'],['frozen_warmup','admitted_only'],['reservation','expected']):
        s={**PRIMARY,'reservation':r,'budget':b,'workers':w,'queue_mode':q,'feedback':f,'density_mode':d}
        if s!=PRIMARY:yield 'factorial',s
    for mode,deadline,arrival in [('fixed',math.inf,'batch'),('api_calls_proxy',600.,'batch'),('api_calls_proxy',3600.,'batch'),('fixed',3600.,'scaled')]:
        for w,q,f in itertools.product([1,16,64],['strict','paper','defer'],['frozen_warmup','admitted_only']):
            yield 'timing',{**PRIMARY,'workers':w,'queue_mode':q,'feedback':f,'duration_mode':mode,'deadline':deadline,'arrival_mode':arrival}
    for w in [1,16,64]:yield 'privileged',{**PRIMARY,'workers':w,'feedback':'full_archive'}

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='results/replay');parser.add_argument('--submission');parser.add_argument('--primary-only',action='store_true');parser.add_argument('--allow-incomplete',action='store_true');parser.add_argument('--data-root',default='data/archives')
    args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    start=datetime.now(timezone.utc).isoformat();split_map=json.loads(Path('configs/split_map.json').read_text());failures=[];counts=Counter();inputs={}
    archive=Path(args.data_root);local=Path('data/ledger')/out.name;local.mkdir(parents=True,exist_ok=True)
    with gzip.open(out/'episodes.csv.gz','wt',newline='') as stream:
        writer=None
        for submission in ([args.submission] if args.submission else SUBMISSIONS):
            path=archive/submission/'normalized.jsonl'
            audit=json.loads(path.with_suffix('.audit.json').read_text());assert audit['normalized_sha256']==sha256(path)
            if not audit['complete'] and not args.allow_incomplete:
                raise ValueError('Incomplete archive: inspect exclusions and pass --allow-incomplete for the predeclared complete-case analysis')
            rows=[json.loads(x) for x in path.read_text().splitlines()];inputs[submission]=sha256(path)
            runner=Runner(rows,split_map)
            with gzip.open(local/(submission+'.jsonl.gz'),'wt',compresslevel=3) as logs:
                for index,(track,s) in enumerate(scenarios()):
                    if args.primary_only and track!='primary':continue
                    policies=POLICIES if track!='privileged' else POLICIES+['lag_previous_settled_full_archive','fixed_previous_day_full_archive','banded_previous_day_full_archive']
                    try:
                        for row,record in runner.episodes(s,policies):
                            row={'track':track,**row}
                            if writer is None:writer=csv.DictWriter(stream,fieldnames=list(row));writer.writeheader()
                            writer.writerow(row);logs.write(json.dumps(record,separators=(',',':'))+'\n');counts[track]+=1
                    except Exception as exc:
                        failures.append({'submission':submission,'track':track,'scenario':s,'error':repr(exc)});print('FAILED',failures[-1],flush=True)
                    if index%30==0:print(submission,index,dict(counts),'prediction cache',runner.predict.cache_info(),flush=True)
            print('COMPLETE',submission,dict(counts),flush=True)
    (out/'failures.json').write_text(json.dumps(failures,indent=2))
    manifest={'started_utc':start,'finished_utc':datetime.now(timezone.utc).isoformat(),'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'python':platform.python_version(),'input_sha256':inputs,'split_map_sha256':sha256(Path('configs/split_map.json')),'protocol_sha256':sha256(Path('docs/EXPERIMENT_PROTOCOL.md')),'episodes':dict(counts),'failures':len(failures),'episodes_sha256':sha256(out/'episodes.csv.gz'),'incomplete_archive_acknowledged':args.allow_incomplete,'paid_calls':0,'interpretation':'Modified-protocol recorded-trace replay; not live agent execution.'}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest),flush=True)
if __name__=='__main__':main()

"""All declared comparisons, descriptive intervals, figures and paper-ready tables."""
import json,math
from pathlib import Path
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from lag_audit.statistics import paired_block_interval
from lag_audit.campaign import SUBMISSIONS
OUT=Path('results/summary');OUT.mkdir(parents=True,exist_ok=False)
df=pd.read_csv('results/final-campaign/episodes.csv.gz')
KEYS=['track','submission','reservation','budget','workers','queue_mode','feedback','density_mode','duration_mode','deadline','arrival_mode']
METRICS=['resolved_before_deadline','resolved','spend','utilization','peak_running','delta','density_excursions','brier','cost_mae','auc','admitted','offered','completed_late']
agg=df.groupby(KEYS+['policy'],dropna=False)[METRICS].mean().reset_index()
agg.to_csv(OUT/'all_cells.csv',index=False)
contrasts=[('lag_structural','zcl_committed'),('lag_structural','zcl_settled'),('lag_structural','zcl_expected_inflight'),('zcl_committed','hard_cap')]
comparisons=[]
def compare(group,metadata,lengths):
 for policy,base in contrasts:
  a=group[group.policy==policy].set_index('block');b=group[group.policy==base].set_index('block');ids=sorted(set(a.index)&set(b.index))
  diffs=(a.loc[ids].resolved_before_deadline-b.loc[ids].resolved_before_deadline).tolist()
  baseline=float(b.loc[ids].resolved_before_deadline.mean())
  for length in lengths:
   ci=paired_block_interval(diffs,20261014,length,5000)
   comparisons.append({**metadata,'policy':policy,'baseline':base,'policy_mean':float(a.loc[ids].resolved_before_deadline.mean()),'baseline_mean':baseline,'relative_difference':float(np.mean(diffs))/baseline if baseline else None,**ci})
for key,group in df.groupby(KEYS,dropna=False):compare(group,dict(zip(KEYS,key)),[1,2,4] if key[0]=='primary' else [2])
primary=df[df.track=='primary'];overall=primary.groupby(['block','policy'],as_index=False)[METRICS].mean()
compare(overall,{'track':'primary','submission':'five_submission_mean'},[1,2,4])
pd.DataFrame(comparisons).to_csv(OUT/'paired_comparisons.csv',index=False)
primary.groupby(['submission','policy'])[METRICS].mean().reset_index().to_csv(OUT/'primary.csv',index=False)
overall.groupby('policy')[METRICS].mean().reset_index().to_csv(OUT/'primary_mean.csv',index=False)
# Freeze widths and order; no selection of the best-looking cells.
selected=df[(df.reservation==6)&(df.budget==24)&(df.feedback=='frozen_warmup')&(df.density_mode=='expected')&(df.duration_mode=='fixed')&(df.deadline==600)&(df.arrival_mode=='batch')]
selected.groupby(['queue_mode','workers','policy'])[METRICS].mean().reset_index().to_csv(OUT/'queue_sensitivity.csv',index=False)
common=pd.read_csv('results/common-sensitivity/episodes.csv.gz')
common.groupby(['submission','policy'])[METRICS].mean().reset_index().to_csv(OUT/'common_sensitivity.csv',index=False)
pool=pd.read_csv('results/pooling/episodes.csv')
pool.groupby(['workers','queue_mode','policy'])[['resolved_before_deadline','unique_issues_before_deadline','spend','peak_running','delta']].mean().reset_index().to_csv(OUT/'pooling.csv',index=False)
switch=pd.read_csv('results/switches/episodes.csv');focus=switch[switch.relative_block.isin([-1,0,1])]
focus.groupby(['relative_block','policy'])[['resolved_before_deadline','spend']].mean().reset_index().to_csv(OUT/'switches.csv',index=False)
# Summary bounds are conditional to these data; every empirical episode is inapplicable to a realized-value certificate.
report={'episodes':len(df),'primary_episodes':len(primary),'scenario_cells':len(agg),'all_primary_blocks_per_submission':8,'number_of_independent_benchmarks':1,'budget_violations_in_recorded_summaries':int(sum(df.spend>df.budget+1e-9)),'maximum_peak_running':int(df.peak_running.max()),'primary_peak_running':int(primary.peak_running.max()),'density_excursion_episodes':int(sum(df.density_excursions>0)),'structural_delta_exceedances':int(df[df.policy=='lag_structural'].design_delta_exceeded.sum()),'empirical_certificates_applicable':int(df.realized_certificate_applicable.sum()),'mean_primary_resolutions':overall.groupby('policy').resolved_before_deadline.mean().to_dict(),'pooled_episodes':len(pool),'switch_episodes':len(switch),'switch_scenarios':60}
(OUT/'overview.json').write_text(json.dumps(report,indent=2))
import runpy
runpy.run_path("scripts/plot_results.py",run_name="__main__")
print(json.dumps(report,indent=2))

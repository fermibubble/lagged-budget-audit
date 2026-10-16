"""Regenerate figures only; no experiment or statistical rerun."""
import math
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from lag_audit.campaign import SUBMISSIONS
OUT=Path("results/summary")
df=pd.read_csv("results/final-campaign/episodes.csv.gz")
primary=df[df.track=="primary"]
selected=df[(df.reservation==6)&(df.budget==24)&(df.feedback=="frozen_warmup")&(df.density_mode=="expected")&(df.duration_mode=="fixed")&(df.deadline==600)&(df.arrival_mode=="batch")]
labels=dict(zip(SUBMISSIONS,['Claude 3.5 Sonnet','GPT-4o','GPT-4','Claude 3 Opus','Claude 4 Sonnet']))
policies=['hard_cap','zcl_settled','zcl_committed','zcl_expected_inflight','lag_structural'];short=['Hard cap','Settled ZCL','Committed ZCL','Expected-in-flight ZCL','Structural lag-aware'];colors=['#89929c','#e69f00','#0072b2','#009e73','#cc79a7']
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':150})
fig,axes=plt.subplots(1,5,figsize=(14,3.4),sharey=True)
for ax,sub in zip(axes,SUBMISSIONS):
 means=primary[primary.submission==sub].groupby('policy').resolved_before_deadline.mean()
 ax.bar(range(5),[means[p] for p in policies],color=colors);ax.set_xticks(range(5),['Cap','S-ZCL','C-ZCL','E-ZCL','Lag'],rotation=50);ax.set_title(labels[sub],fontsize=10);ax.set_ylim(0,max(12,math.ceil(primary.groupby(['submission','policy']).resolved_before_deadline.mean().max()+1)))
axes[0].set_ylabel('Resolutions by deadline / block')
fig.suptitle('Primary setting: USD 24 budget, USD 6 reservation, 16 worker slots, paper queue',fontsize=12);fig.tight_layout();fig.savefig(OUT/'primary.png');fig.savefig(OUT/'primary.pdf');plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(12,3.6),sharey=True)
for ax,queue in zip(axes,['strict','paper','defer']):
 g=selected[selected.queue_mode==queue].groupby(['workers','policy']).resolved_before_deadline.mean()
 for policy,label,color in zip(policies,short,colors):ax.plot([1,4,16,64],[g.loc[w,policy] for w in [1,4,16,64]],'o-',label=label,color=color)
 ax.set_xscale('log',base=4);ax.set_xticks([1,4,16,64],[1,4,16,64]);ax.set_title(queue+' queue');ax.set_xlabel('Worker limit (occupancy is budget-limited)')
axes[0].set_ylabel('Mean resolutions / block');axes[-1].legend(fontsize=7)
fig.suptitle('Queue sensitivity, frozen features, same budget/reservation/deadline');fig.tight_layout();fig.savefig(OUT/'queues.png');fig.savefig(OUT/'queues.pdf');plt.close(fig)
conv=pd.read_csv('results/theory-extended-002/convergence.csv')
fig,ax=plt.subplots(figsize=(6,3.5))
for ratio in [10,100,1000]:
 for kind in ['zcl','lag']:
  g=conv[(conv.ratio_U_L==ratio)&(conv.lag_before_admission_limit==.2)&(conv.kind==kind)]
  ax.loglog(g.units,g.relative_error,'o-' if kind=='zcl' else 's--',label=f'{kind}, U/L={ratio}')
ax.set_xlabel('Budget units');ax.set_ylabel('Relative error vs asymptotic target');ax.set_title('Finite-grid convergence at design lag 0.2');ax.legend(fontsize=7);fig.tight_layout();fig.savefig(OUT/'convergence.png');fig.savefig(OUT/'convergence.pdf');plt.close(fig)

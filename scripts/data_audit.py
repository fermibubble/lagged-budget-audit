"""Publish counts/hashes and derived aggregate statistics; keep issue text local."""
import csv,json
from collections import Counter
from pathlib import Path
import numpy as np
from lag_audit.campaign import SUBMISSIONS
from lag_audit.data import sha256
allrows={};summary=[];split=json.loads(Path('configs/split_map.json').read_text())
for sub in SUBMISSIONS:
 root=Path('data/archives')/sub
 rows=[json.loads(x) for x in (root/'normalized.jsonl').read_text().splitlines()];allrows[sub]=rows
 audit=json.loads((root/'normalized.audit.json').read_text());official=json.loads((root/'official_results.json').read_text())
 costs=np.array([r['actual_cost'] for r in rows]);ratios=6/costs[costs>0]
 counts=Counter(e['reason'] for e in audit['exclusions']);no_logs=set(official.get('no_logs',[]))
 excluded_resolved=len(set(official['resolved'])-{r['instance_id'] for r in rows if r['resolved']})
 row={'submission':sub,'benchmark':500,'archive_trajectories':len(json.loads((root/'inventory.json').read_text())),'retained':len(rows),'missing_trajectory':counts['missing_trajectory'],'unknown_outcome':counts['official_no_logs_unknown_outcome'],'official_no_logs':len(no_logs),'official_no_generation':len(official.get('no_generation',[])),'official_resolved':len(official['resolved']),'retained_resolved':sum(r['resolved'] for r in rows),'excluded_official_resolved':excluded_resolved,'zero_costs':int(sum(costs==0)),'max_cost':float(max(costs)),'mean_cost':float(np.mean(costs)),'median_cost':float(np.median(costs)),'reservation6_median_ratio_positive_cost':float(np.median(ratios)),'reservation6_gamma':float(max(ratios)) if all(costs>0) else None,'warmup_rows':sum(split[r['instance_id']]<2 for r in rows),'warmup_archive_cost':sum(r['actual_cost'] for r in rows if split[r['instance_id']]<2),'evaluated_rows':sum(split[r['instance_id']]>=2 for r in rows),'raw_success_rate_lower':sum(r['resolved'] for r in rows)/500,'raw_success_rate_upper_unknown_exclusions':(sum(r['resolved'] for r in rows)+len(audit['exclusions']))/500}
 summary.append(row)
 # Per-record factual numeric features, with no issue text: reproducibility aid.
 # Text length is a derived count, IDs point to the public original, no patches.
 numeric=[{k:v for k,v in r.items() if k!='problem_statement'}|{'issue_length':len(r['problem_statement'])} for r in rows]
 public=Path('results/data-audit')/sub
 (public/'measurements.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in numeric))
out=Path('results/data-audit')
with (out/'summary.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
common=set.intersection(*[{r['instance_id'] for r in rows} for rows in allrows.values()])
for sub,rows in allrows.items():
 dest=Path('data/common')/sub;dest.mkdir(parents=True,exist_ok=True);path=dest/'normalized.jsonl'
 selected=[r for r in rows if r['instance_id'] in common];path.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in selected))
 (dest/'normalized.audit.json').write_text(json.dumps({'complete':False,'normalized_sha256':sha256(path),'retained':len(selected),'selection':'issue has known cost/outcome in all five submissions','parent_sha256':sha256(Path('data/archives')/sub/'normalized.jsonl')}))
(out/'common.json').write_text(json.dumps({'common_issues':len(common),'ids':sorted(common)},indent=2))
print(json.dumps(summary,indent=2));print('common',len(common))

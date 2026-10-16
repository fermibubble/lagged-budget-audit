"""Cost/counter schema validation independent of policy performance."""
import json,hashlib
from pathlib import Path
from collections import Counter
from lag_audit.campaign import SUBMISSIONS
from lag_audit.data import parse_trajectory,parse_suffix_info
reports=[]
for sub in SUBMISSIONS[:4]:
 counts=Counter();diffs=Counter()
 for path in (Path('data/archives')/sub/'trajs').glob('*.traj'):
  obj=json.loads(path.read_text());parsed=parse_trajectory(obj);counts['objects']+=1
  if parsed['api_calls'] is None:counts['missing_calls']+=1
  else:
   diffs[parsed['api_calls']-len(obj['trajectory'])]+=1
   if parsed['api_calls']==len(obj['trajectory']):counts['calls_equal_trajectory_steps']+=1
  if obj['info']['model_stats'].get('total_cost',parsed['actual_cost'])!=parsed['actual_cost']:counts['cumulative_cost_differs']+=1
 reports.append({'submission':sub,'counts':dict(counts),'api_calls_minus_steps':dict(sorted(diffs.items())),'code_semantics':'Legacy APIStats resets calls, tokens and instance_cost while preserving total_cost; exact submitting revision unavailable'})
full=json.loads(Path('data/smoke/20250522_sweagent_claude-4-sonnet-20250514.json').read_text())
info=parse_suffix_info(Path('data/smoke/range-tail.bin').read_bytes())
reports.append({'submission':SUBMISSIONS[-1],'full_sample_vs_range_stats_identical':info['model_stats']==full['info']['model_stats'],'sample_api_calls':info['model_stats']['api_calls'],'sample_trajectory_steps':len(full['trajectory']),'code_semantics':'Declared release v1.1.0 InstanceStats resets per run; embedded commit unavailable (404)'})
Path('results/data-audit/schema_validation.json').write_text(json.dumps(reports,indent=2));print(json.dumps(reports,indent=2))

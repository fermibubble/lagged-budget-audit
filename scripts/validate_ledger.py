"""Audit regenerated private ledgers without publishing raw issue text."""
import gzip,json
from pathlib import Path
from lag_audit.campaign import SUBMISSIONS
split=json.loads(Path('configs/split_map.json').read_text());episodes=events=0;histories={}
for sub in SUBMISSIONS:
 rows=[json.loads(x) for x in (Path('data/public')/sub/'normalized.jsonl').read_text().splitlines()]
 warmup={r['id'] for r in rows if split[r['instance_id']]<2}
 for line in gzip.open(Path('data/ledger/final-campaign')/(sub+'.jsonl.gz'),'rt'):
  r=json.loads(line);tag=r['tag'];key=json.dumps({k:v for k,v in tag.items() if k!='block'},sort_keys=True)
  expected=histories.get(key,set(warmup));assert expected==set(r['training_ids'])
  assert not expected.intersection(r['test_ids'])
  for event in r['events']:
   assert -1e-8<=event['committed']<=tag['budget']+1e-8
   assert event['reserved']>=-1e-8 and event['settled']>=-1e-8
   assert abs(event['settled']+event['reserved']-event['committed'])<1e-8
   events+=1
  assert sum(e['actual_cost'] for e in r['events'] if e['kind']=='settle')<=tag['budget']+1e-8
  if tag['feedback']=='admitted_only':expected=expected|set(r['admitted'])
  elif tag['feedback']=='full_archive':expected=expected|set(r['test_ids'])
  histories[key]=expected;episodes+=1
result={'episodes_checked':episodes,'events_checked':events,'budget_or_ledger_violations':0,'feedback_provenance_violations':0}
Path('results/ledger_validation.json').write_text(json.dumps(result,indent=2));print(result)

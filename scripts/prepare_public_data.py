"""Materialize reproducible, text-free replay inputs from published measurements."""
import json
from pathlib import Path
from lag_audit.campaign import SUBMISSIONS
from lag_audit.data import sha256
for sub in SUBMISSIONS:
 source=Path('results/data-audit')/sub
 dest=Path('data/public')/sub;dest.mkdir(parents=True,exist_ok=True)
 path=dest/'normalized.jsonl';path.write_bytes((source/'measurements.jsonl').read_bytes())
 audit=json.loads((source/'audit.json').read_text())
 audit['raw_normalized_sha256']=audit['normalized_sha256'];audit['normalized_sha256']=sha256(path)
 audit['representation']='Published numerical measurements and issue character counts; no issue text'
 (dest/'normalized.audit.json').write_text(json.dumps(audit,indent=2))
print('Prepared five text-free replay inputs')

"""Acquire the 2025 archive's verified JSON metadata with bounded HTTP suffix reads."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,threading,xml.etree.ElementTree as ET
import requests,pyarrow.parquet as pq
from lag_audit.data import parse_suffix_info,parse_trajectory,normalize,sha256,safe_destination
SUB='20250522_sweagent_claude-4-sonnet-20250514'
ROOT=Path('data/archives')/SUB
ns={'s':'http://s3.amazonaws.com/doc/2006-03-01/'}
params={'list-type':'2','prefix':f'verified/{SUB}/trajs/'};objects=[]
while True:
 r=requests.get('https://swe-bench-submissions.s3.amazonaws.com/',params=params,timeout=90);r.raise_for_status();root=ET.fromstring(r.content)
 for o in root.findall('s:Contents',ns):
  key=o.find('s:Key',ns).text
  if key.endswith('.traj'):objects.append({'key':key,'bytes':int(o.find('s:Size',ns).text),'etag':o.find('s:ETag',ns).text})
 if root.find('s:IsTruncated',ns).text!='true':break
 params['continuation-token']=root.find('s:NextContinuationToken',ns).text
(ROOT/'inventory.json').write_text(json.dumps(objects,indent=2))
lock=threading.Lock();allocated=0

def one(o):
 global allocated
 instance=Path(o['key']).stem;range_path=ROOT/'ranges'/(instance+'.bin');meta_path=ROOT/'ranges'/(instance+'.json');range_path.parent.mkdir(exist_ok=True)
 source='https://swe-bench-submissions.s3.amazonaws.com/'+o['key']
 if meta_path.exists():
  meta=json.loads(meta_path.read_text());payload=range_path.read_bytes();assert hashlib.sha256(payload).hexdigest()==meta['range_sha256']
  info=parse_suffix_info(payload)
 else:
  for size in [262144,524288,1048576]:
   wanted=min(size,o['bytes'])
   with lock:
    allocated+=wanted
    if allocated>1_000_000_000:raise RuntimeError('Archive range-byte guard exceeded')
   with requests.get(source,headers={'Range':f'bytes=-{size}'},timeout=90,stream=True) as response:
    if response.status_code!=206:raise ValueError('Server did not honor bounded Range request')
    expected=f"bytes {o['bytes']-wanted}-{o['bytes']-1}/{o['bytes']}"
    if response.headers.get('Content-Range')!=expected or response.headers.get('ETag')!=o['etag']:raise ValueError('Object changed or inconsistent byte range')
    payload=response.raw.read(wanted+1)
    if len(payload)!=wanted:raise ValueError('Unexpected payload size')
   try:info=parse_suffix_info(payload)
   except (ValueError,UnicodeError):
    if size==1048576:raise
    continue
   range_path.write_bytes(payload)
   meta={**o,'source':source,'content_range':expected,'range_sha256':hashlib.sha256(payload).hexdigest(),'downloaded_bytes':len(payload),'full_object_sha256':None,'representation':'complete root info parsed from verified HTTP suffix; full object not downloaded'}
   meta_path.write_text(json.dumps(meta,indent=2));break
 dest=ROOT/'trajs'/(instance+'.traj');dest.parent.mkdir(exist_ok=True)
 dest.write_text(json.dumps({'info':info},sort_keys=True))
 return {**meta,'extracted_info_sha256':sha256(dest)}
files=[]
with ThreadPoolExecutor(max_workers=8) as pool:
 for i,f in enumerate(pool.map(one,objects)):
  files.append(f)
  if (i+1)%100==0:print('ranges',i+1,flush=True)
rows=pq.read_table('data/archives/verified.parquet',columns=['instance_id','repo','problem_statement','created_at']).to_pylist()
audit=normalize(rows,ROOT/'trajs',json.loads((ROOT/'official_results.json').read_text()),SUB,ROOT/'normalized.jsonl')
# Explicitly distinguish the hash of the extraction from a full-trajectory hash.
p=ROOT/'normalized.jsonl';normalized=[json.loads(x) for x in p.read_text().splitlines()]
for row in normalized:row['trajectory_sha256_scope']='extracted_info_json; see source lock for range hash'
p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in normalized));audit['normalized_sha256']=sha256(p);audit['acquisition']='HTTP suffix metadata extraction';p.with_suffix('.audit.json').write_text(json.dumps(audit,indent=2))
record={'github_revision':'40f164d5b8f1d249bf95a6df8b74b577fd8e519d','dataset_revision':'c104f840cc67f8b6eec6f759ebc8b2693d585d4a','dataset':'princeton-nlp/SWE-bench_Verified','dataset_sha256':sha256(Path('data/archives/verified.parquet')),'submission':SUB,'retrieved_utc':datetime.now(timezone.utc).isoformat(),'archive_full_bytes':sum(o['bytes'] for o in objects),'range_bytes':sum(f['downloaded_bytes'] for f in files),'files':files,'metadata_sha256':sha256(ROOT/'metadata.yaml'),'official_results_sha256':sha256(ROOT/'official_results.json'),'audit':audit}
(ROOT/'sources.lock.json').write_text(json.dumps(record,indent=2));dest=Path('results/data-audit')/SUB;dest.mkdir(parents=True,exist_ok=True)
(dest/'sources.lock.json').write_text(json.dumps(record,indent=2));(dest/'audit.json').write_text(json.dumps(audit,indent=2));print(json.dumps(audit,indent=2))

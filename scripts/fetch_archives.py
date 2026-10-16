"""Resumable, public-only HTTP acquisition with a 1GB guard per trajectory archive.

No trajectory text or patches are executed. Partial files remain in ignored data/.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json, time, xml.etree.ElementTree as ET
from pathlib import Path
import requests, pyarrow.parquet as pq
from lag_audit.data import normalize, sha256, safe_destination
from probe_sources import SUBMISSIONS
GH='40f164d5b8f1d249bf95a6df8b74b577fd8e519d'
HF='c104f840cc67f8b6eec6f759ebc8b2693d585d4a'
ROOT=Path('data/archives')

def download(url,path):
    if path.exists(): return
    path.parent.mkdir(parents=True,exist_ok=True)
    for attempt in range(4):
        try:
            r=requests.get(url,timeout=120);r.raise_for_status()
            temp=path.with_suffix(path.suffix+'.partial');temp.write_bytes(r.content);temp.replace(path);return
        except Exception:
            if attempt==3:raise
            time.sleep(2**attempt)

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    parquet=ROOT/'verified.parquet'
    url=f'https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified/resolve/{HF}/data/test-00000-of-00001.parquet'
    download(url,parquet)
    rows=pq.read_table(parquet,columns=['instance_id','repo','problem_statement','created_at']).to_pylist()
    ordered=sorted(rows,key=lambda r:(r['created_at'],r['instance_id']))
    splits={r['instance_id']:i//50 for i,r in enumerate(ordered)}
    Path('configs/split_map.json').write_text(json.dumps(splits,indent=2,sort_keys=True)+'\n')
    (ROOT/'issues.json').write_text(json.dumps(rows))
    for sub in SUBMISSIONS:
        dest=ROOT/sub;dest.mkdir(exist_ok=True)
        if (dest/'sources.lock.json').exists():
            print(sub,'already complete',flush=True);continue
        base=f'https://raw.githubusercontent.com/SWE-bench/experiments/{GH}/evaluation/verified/{sub}'
        download(base+'/metadata.yaml',dest/'metadata.yaml')
        download(base+'/results/results.json',dest/'official_results.json')
        import yaml
        expected='s3://swe-bench-submissions/verified/'+sub+'/trajs'
        assert yaml.safe_load((dest/'metadata.yaml').read_text())['assets']['trajs'].rstrip('/')==expected
        prefix=f'verified/{sub}/trajs/'
        ns={'s':'http://s3.amazonaws.com/doc/2006-03-01/'};params={'list-type':'2','prefix':prefix};objects=[]
        while True:
            response=requests.get('https://swe-bench-submissions.s3.amazonaws.com/',params=params,timeout=90);response.raise_for_status()
            root=ET.fromstring(response.content)
            for o in root.findall('s:Contents',ns):
                key=o.find('s:Key',ns).text
                if key.endswith('.traj'):
                    objects.append({'key':key,'bytes':int(o.find('s:Size',ns).text),'etag':o.find('s:ETag',ns).text})
            if root.find('s:IsTruncated',ns).text!='true':break
            params['continuation-token']=root.find('s:NextContinuationToken',ns).text
        total=sum(o['bytes'] for o in objects)
        assert objects and total<=1_000_000_000,(sub,len(objects),total)
        (dest/'inventory.json').write_text(json.dumps(objects,indent=2))
        print(sub,'objects',len(objects),'bytes',total,flush=True)
        def one(o):
            path=safe_destination(dest/'trajs',o['key'][len(prefix):])
            source='https://swe-bench-submissions.s3.amazonaws.com/'+o['key']
            download(source,path)
            if path.stat().st_size!=o['bytes']:raise ValueError('Size mismatch: '+o['key'])
            return {**o,'source':source,'sha256':sha256(path)}
        files=[]
        with ThreadPoolExecutor(max_workers=8) as pool:
            for i,f in enumerate(pool.map(one,objects)):
                files.append(f)
                if (i+1)%100==0:print(sub,i+1,'downloaded',flush=True)
        official=json.loads((dest/'official_results.json').read_text())
        audit=normalize(rows,dest/'trajs',official,sub,dest/'normalized.jsonl')
        lock={'github_revision':GH,'dataset_revision':HF,'dataset':'princeton-nlp/SWE-bench_Verified','dataset_url':url,'dataset_sha256':sha256(parquet),'submission':sub,'retrieved_utc':datetime.now(timezone.utc).isoformat(),'files':files,'metadata_sha256':sha256(dest/'metadata.yaml'),'official_results_sha256':sha256(dest/'official_results.json'),'normalized_sha256':sha256(dest/'normalized.jsonl'),'split_map_sha256':sha256(Path('configs/split_map.json')),'audit':audit}
        (dest/'sources.lock.json').write_text(json.dumps(lock,indent=2))
        public=Path('results/data-audit')/sub;public.mkdir(parents=True,exist_ok=True)
        (public/'sources.lock.json').write_text(json.dumps(lock,indent=2))
        (public/'audit.json').write_text(json.dumps(audit,indent=2))
        print(sub,'retained',audit['retained'],'excluded',len(audit['exclusions']),flush=True)
if __name__=='__main__':main()

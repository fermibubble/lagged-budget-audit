"""Read-only source inventory. Does not inspect run outcomes or costs."""
import json, subprocess, xml.etree.ElementTree as ET
from pathlib import Path
SUBMISSIONS = ['20240620_sweagent_claude3.5sonnet','20240728_sweagent_gpt4o','20240402_sweagent_gpt4','20240402_sweagent_claude3opus','20250522_sweagent_claude-4-sonnet-20250514']
def get(url):
    return subprocess.check_output(['curl','--fail','--silent','--show-error','--location','--retry','3',url])
if __name__ == '__main__':
    dest=Path('data/probe');dest.mkdir(parents=True,exist_ok=True)
    inventory=[]
    for submission in SUBMISSIONS:
        prefix='verified/'+submission+'/trajs/'
        payload=get('https://swe-bench-submissions.s3.amazonaws.com/?list-type=2&prefix='+prefix)
        (dest/(submission+'.xml')).write_bytes(payload)
        root=ET.fromstring(payload);ns={'s':'http://s3.amazonaws.com/doc/2006-03-01/'}
        objs=[{'key':o.find('s:Key',ns).text,'bytes':int(o.find('s:Size',ns).text)} for o in root.findall('s:Contents',ns)]
        row={'submission':submission,'objects':len(objs),'bytes':sum(o['bytes'] for o in objs),'truncated':root.find('s:IsTruncated',ns).text,'first':objs[0] if objs else None}
        inventory.append(row);print(json.dumps(row),flush=True)
    info=json.loads(get('https://huggingface.co/api/datasets/princeton-nlp/SWE-bench_Verified'))
    (dest/'dataset-info.json').write_text(json.dumps({'sha':info['sha'],'siblings':info['siblings']},indent=2))
    (dest/'inventory.json').write_text(json.dumps(inventory,indent=2))

"""Hash tracked publication contents, excluding this manifest's own bytes."""
import hashlib,json,subprocess
from pathlib import Path
manifest=Path('results/PUBLICATION_MANIFEST.json')
paths=[Path(p) for p in subprocess.check_output(['git','ls-files','-z'],text=True).split('\0') if p]
files=[{'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(paths) if p!=manifest]
manifest.write_text(json.dumps({'experiment_code_commit':'6a3dfd25029bbb5c4f0e3f6ab43cc12e06536dc8','files':files,'manifest_self_hash_excluded':True,'original_manuscript_published':False,'raw_trajectories_published':False,'paid_model_calls':0},indent=2))
print('Hashed',len(files),'publication files')

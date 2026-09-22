"""Package only interview preparation documents. Prior packages are never overwritten."""
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT=Path(__file__).resolve().parents[1]
DOCUMENTS=('pitch-30s.md','pitch-1min.md','pitch-3min.md','project-pitch.md','demo-5min.md',
           'demo-10min.md','interview-qa.md','interview-hard-questions.md','interview-depth-map.md',
           'architecture-cheatsheet.md','resume.md','resume-short.md','v3-failure-story.md','limitations.md')

def main():
    output=ROOT/'outputs/sentinel-interview-pack.zip'
    manifest=ROOT/'outputs/sentinel-interview-pack.manifest.json'
    if output.exists() or manifest.exists():raise FileExistsError('Preserve the existing interview package')
    files={name:(ROOT/'docs'/name).read_bytes() for name in DOCUMENTS}
    for name,data in files.items():
        # Every relative link must work within this small, self-contained reading pack.
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',data.decode('utf-8-sig')):
            path=target.split('#',1)[0]
            if path and not re.match(r'\w+://',path) and path not in files:
                raise ValueError('Missing interview-pack reference: '+name+' -> '+path)
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,data in files.items():z.writestr('sentinel-interview-pack/'+name,data)
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        assert all(z.read('sentinel-interview-pack/'+name)==data for name,data in files.items())
    result={'archive':output.name,'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'file_count':len(files),'verified':True,'files':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in files.items()}}
    with manifest.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='files'}))

if __name__=='__main__':main()

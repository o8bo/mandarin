"""Review actual Git index blobs before publication; report findings without values.

Pattern checks supplement review; they cannot prove the absence of every secret.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from prepare_source import files,ROOT

PATTERNS={
    'private key':rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
    'GitHub token':rb'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{40,})',
    'AWS access key':rb'(?:AKIA|ASIA)[A-Z0-9]{16}',
    'credential literal':rb'''(?i)(?:password|passwd|client_secret|api_key|access_token)\s*[:=]\s*["'][^"'\r\n]{8,}["']''',
    'private local path':rb'/home/[A-Za-z0-9_.-]+/|tangerine[-]analysis|ev_[0-9a-f]{32,}',
}
FORBIDDEN={'vendor','.venv','.dev-deps','verification','build','dist','.git','__pycache__'}


def review():
    raw=subprocess.check_output(['git','ls-files','--stage','-z'],cwd=ROOT)
    entries=[];findings=[]
    for item in raw.split(b'\0'):
        if not item:continue
        header,name=item.split(b'\t',1);mode,oid,stage=header.decode().split();path=name.decode('utf-8');entries.append((path,mode,oid))
        if stage!='0' or mode not in {'100644','100755'}:findings.append({'file':path,'issue':'Unexpected index mode/stage'})
    expected={str(rel) for _,rel in files()};actual={p for p,_,_ in entries}
    for path in sorted(actual^expected):findings.append({'file':path,'issue':'Index does not match allowlisted source'})
    batch=subprocess.run(['git','cat-file','--batch'],input=('\n'.join(oid for _,_,oid in entries)+'\n').encode(),stdout=subprocess.PIPE,check=True,cwd=ROOT).stdout
    position=0;manifest={};binary=[]
    for path,mode,oid in entries:
        end=batch.index(b'\n',position);_,kind,size=batch[position:end].split();size=int(size);data=batch[end+1:end+1+size];position=end+2+size
        if kind!=b'blob':raise RuntimeError('Unexpected Git object')
        parts=Path(path).parts
        if any(part in FORBIDDEN for part in parts) or Path(path).suffix.lower() in {'.exe','.dll','.so','.zip','.deb','.whl','.db','.pem','.key'}:findings.append({'file':path,'issue':'Private/generated/binary publication path'})
        if size>5_000_000:findings.append({'file':path,'issue':'Unexpected large source file'})
        if b'\0' in data:
            if not (data.startswith(b'\x89PNG\r\n\x1a\n') and parts[:2]==('docs','screenshots')):findings.append({'file':path,'issue':'Unexpected binary'})
            binary.append(path)
        else:
            for label,pattern in PATTERNS.items():
                if re.search(pattern,data):findings.append({'file':path,'issue':label})
        if (ROOT/path).read_bytes()!=data:findings.append({'file':path,'issue':'Working file differs from staged blob'})
        manifest[path]={'bytes':size,'sha256':hashlib.sha256(data).hexdigest()}
    for required in ['README.md','LICENSE','docs/BUILDING.md','docs/WINDOWS.md','docs/TEST_RESULTS.md']:
        if required not in actual:findings.append({'file':required,'issue':'Required document absent'})
    return {'ok':not findings,'files_reviewed':len(entries),'bytes_reviewed':sum(v['bytes'] for v in manifest.values()),
        'binary_files':binary,'findings':findings,'scope':'Actual index blobs; allowlist, secret patterns, private paths and binary checks; not an exhaustive security audit','manifest':manifest}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',default='verification/staged-review.json');args=parser.parse_args();result=review()
    target=Path(args.report);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='manifest'},indent=2));sys.exit(0 if result['ok'] else 1)

"""Maintainer helper: collect notices from locally downloaded official source tags.

Input: .dev-deps/upstream/{qtbase,qtsvg,pyside-setup}-v6.10.1.tar.gz.
Only licenses, attribution JSON and referenced license/copyright files are
extracted; some upstream copyright notices live in source headers. The main builder consumes the checked-in result offline.
"""
import hashlib
import json
from pathlib import Path,PurePosixPath
import posixpath
import tarfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    dest=ROOT/'third_party/qt-6.10.1';dest.mkdir(parents=True,exist_ok=True);manifest={}
    for repo in ['qt/qtbase','qt/qtsvg','pyside/pyside-setup']:
        name=repo.split('/')[-1];archive=ROOT/'.dev-deps/upstream'/f'{name}-v6.10.1.tar.gz'
        with tarfile.open(archive) as tar:
            all_files={m.name:m for m in tar.getmembers() if m.isfile()};chosen=set()
            for path in all_files:
                parts=PurePosixPath(path).parts
                if 'LICENSES' in parts or ('/' not in path.partition('/')[2] and any(word in parts[-1].upper() for word in ['LICENSE','COPYING','COPYRIGHT'])):chosen.add(path)
                if path.endswith('qt_attribution.json'):
                    chosen.add(path);data=json.loads(tar.extractfile(path).read(),strict=False)
                    for item in data if isinstance(data,list) else [data]:
                        for key in ['LicenseFile','CopyrightFile']:
                            values=item.get(key,[])
                            for value in values if isinstance(values,list) else [values]:
                                reference=posixpath.normpath(posixpath.join(posixpath.dirname(path),value))
                                if reference not in all_files:raise RuntimeError(f'Missing upstream notice: {reference}')
                                chosen.add(reference)
            for path in sorted(chosen):
                relative=PurePosixPath(path).relative_to(PurePosixPath(path).parts[0])
                if '..' in relative.parts:raise RuntimeError('Unsafe notice path')
                data=tar.extractfile(path).read()
                if len(data)>2_000_000:raise RuntimeError('Unexpected large notice')
                target=dest/name/str(relative);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            manifest[repo]={'tag':'v6.10.1','url':f'https://codeload.github.com/{repo}/tar.gz/refs/tags/v6.10.1','source_archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'notice_files':len(chosen)}
    (dest/'PROVENANCE.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()

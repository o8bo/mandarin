"""Prepare an allowlisted source candidate; no GitHub operations."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
ROOT_FILES={'LICENSE','README.md','THIRD_PARTY.md','.gitignore','launch.sh','install.py','mandarin_launcher.py','requirements.txt','requirements-windows.txt','requirements-build.txt','test_engine.py','test_platform.py','test_qt.py','test_build_tools.py','test_drag_flow.py'}
SOURCE_DIRS={'mandarin','assets','docs','scripts','.github','third_party'}

def files():
    for path in sorted(ROOT.rglob('*')):
        relative=path.relative_to(ROOT)
        if str(relative)=='docs/ORIGINAL_INVESTIGATION.md':continue
        if relative.parts[0] not in SOURCE_DIRS and str(relative) not in ROOT_FILES:continue
        if path.is_symlink():raise RuntimeError(f'Source symlink needs review: {relative}')
        if not path.is_file() or '__pycache__' in relative.parts or path.suffix in {'.pyc','.log'}:continue
        if relative.parts[0]!='third_party' and path.suffix.lower() not in {'.py','.css','.md','.svg','.png','.sh','.txt','.yml','.yaml'} and str(relative) not in {'.gitignore','LICENSE'}:raise RuntimeError(f'Unexpected source file: {relative}')
        yield path,relative

def main():
    selected=list(files());manifest={str(rel):hashlib.sha256(path.read_bytes()).hexdigest() for path,rel in selected}
    output=ROOT/'dist';output.mkdir(exist_ok=True);dest=output/'mandarin-v0.1.0-rc-source.zip'
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for path,relative in selected:z.write(path,Path('mandarin')/relative)
        z.writestr('mandarin/SOURCE-MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
    digest=hashlib.sha256(dest.read_bytes()).hexdigest();dest.with_suffix('.zip.sha256').write_text(digest+'  '+dest.name+'\n')
    print(f'{len(selected)} source files; {dest}');print(digest)

if __name__=='__main__':main()

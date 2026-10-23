"""Build on the target OS, run the frozen app, and only then create a ZIP.

The linux-qt-validation target verifies packaging, never produces a Windows EXE.
No optional FFmpeg/LibreOffice/Poppler executables are copied into the bundle.
"""
import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import sysconfig
import tempfile
import zipfile

from verify_portable import inspect_pe, verify

ROOT=Path(__file__).resolve().parents[1]

def build(target):
    windows=target=='windows'
    if windows and (sys.platform!='win32' or struct.calcsize('P')!=8 or platform.machine().lower() not in ('amd64','x86_64')):
        raise SystemExit('Windows x64 builds require native Windows x64 and 64-bit Python. No Windows artifact was built.')
    if windows and sys.version_info[:2]!=(3,12):raise SystemExit('Windows portable builds require Python 3.12 x64.')
    if not windows and sys.platform!='linux':raise SystemExit('linux-qt-validation requires Linux.')
    name='Mandarin' if windows else 'Mandarin-Linux-Qt-validation'
    output=ROOT/'dist';output.mkdir(exist_ok=True)
    # Never ship a ZIP left over from an earlier, now-failing attempt.
    archive=output/('Mandarin-Windows-x64.zip' if windows else name+'.zip')
    if archive.exists():raise SystemExit(f'Existing artifact preserved: {archive}. Move it aside before rebuilding.')
    work=ROOT/'build'/target;work.mkdir(parents=True,exist_ok=True)
    icon=work/'mandarin.ico'
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtGui import QImage,QPainter
    from PySide6.QtCore import Qt
    from PIL import Image
    image=QImage(256,256,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.transparent)
    painter=QPainter(image);QSvgRenderer(str(ROOT/'assets/mandarin.svg')).render(painter);painter.end()
    png=work/'icon.png';image.save(str(png))
    with Image.open(png) as im:im.save(icon,format='ICO',sizes=[(16,16),(32,32),(48,48),(256,256)])
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed','--name',name,
        '--distpath',str(output),'--workpath',str(work/'pyinstaller'),'--specpath',str(work),
        '--paths',str(ROOT),'--add-data',str(ROOT/'assets')+os.pathsep+'assets',
        '--hidden-import','PySide6.QtSvg','--collect-all','pypdf','--exclude-module','gi','--exclude-module','tkinter',
        '--copy-metadata','Pillow','--copy-metadata','pypdf','--copy-metadata','PySide6-Essentials','--copy-metadata','shiboken6']
    if windows:command+=['--icon',str(icon)]
    command.append(str(ROOT/'mandarin_launcher.py'))
    subprocess.run(command,cwd=ROOT,check=True)
    folder=output/name;exe=folder/(name+'.exe' if windows else name)
    pe=inspect_pe(exe) if windows else None
    licenses=folder/'licenses';licenses.mkdir(exist_ok=True)
    notices=ROOT/'third_party/qt-6.10.1'
    if not (notices/'PROVENANCE.json').is_file():raise RuntimeError('Checked-in Qt license/attribution notices missing')
    shutil.copytree(notices,licenses/'qt-6.10.1',dirs_exist_ok=True)
    for doc in ['LICENSE','THIRD_PARTY.md','docs/WINDOWS.md','docs/BUILDING.md']:
        shutil.copy2(ROOT/doc,licenses/Path(doc).name)
    # Include upstream license texts, including Python, Qt modules and wheel DLL notices.
    for package in ['Pillow','pypdf','PySide6-Essentials','shiboken6','pyinstaller']:
        dist=metadata.distribution(package)
        for item in dist.files or []:
            if any(word in str(item).lower() for word in ('license','copying','copyright','notice')):
                source=Path(dist.locate_file(item))
                if source.is_file():
                    dest=licenses/package/str(item).replace('../','')
                    dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
    python_license=next((p for p in [Path(sys.base_prefix)/'LICENSE.txt',Path(sysconfig.get_path('stdlib'))/'LICENSE.txt'] if p.is_file()),None)
    if python_license is None:raise RuntimeError('Python license text missing; cannot package a distribution')
    shutil.copy2(python_license,licenses/'Python-LICENSE.txt')
    report=output/(name+'-smoke.json')
    with tempfile.TemporaryDirectory(prefix='mandarin-clean-cwd-') as clean:
        env=dict(os.environ);env.pop('PYTHONPATH',None);env.pop('PYTHONHOME',None)
        if not windows:env.setdefault('QT_QPA_PLATFORM','offscreen')
        # Launch the artifact outside the source tree with no development module path.
        subprocess.run([str(exe),'--self-test',str(report)],cwd=clean,env=env,timeout=90,check=True)
    result=json.loads(report.read_text())
    if not result.get('ok') or not result.get('frozen'):raise RuntimeError('Frozen smoke check failed')
    manifest={'version':'0.1.0-rc','platform':sys.platform,'architecture':platform.machine(),
        'python':sys.version,'dependencies':{p:metadata.version(p) for p in ['Pillow','pypdf','PySide6-Essentials','shiboken6','pyinstaller']},
        'source_commit':os.environ.get('GITHUB_SHA'), 'pe':pe, 'frozen_smoke':result,'fresh_windows_machine':'NOT TESTED','native_explorer_drop':'NOT TESTED',
        'external_conversion_tools':'Not bundled; detect PATH or configure trusted executables'}
    (folder/'BUILD-REPORT.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(folder.rglob('*')):
            if path.is_file():z.write(path,path.relative_to(output))
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    try:
        verify(archive, output/(name+'-portable-verification.json'))
    except Exception:
        # Keep a failed candidate local for diagnosis, outside the upload path.
        archive.rename(work/(archive.name+'.failed'))
        archive.with_suffix('.zip.sha256').unlink(missing_ok=True)
        raise
    print(archive);print('Frozen and unpacked ZIP smoke PASS; native desktop acceptance still required.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--target',required=True,choices=['windows','linux-qt-validation']);build(parser.parse_args().target)

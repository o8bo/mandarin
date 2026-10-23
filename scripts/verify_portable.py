"""Validate and unpack the portable ZIP, then run its own bundled-runtime tests.

The launcher gets a clean working directory and a PATH without the build Python.
This is runner-level verification, not fresh interactive Windows 11 acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import stat
import struct
import subprocess
import sys
import tempfile
import traceback
import zipfile


def inspect_pe(path):
    path=Path(path);size=path.stat().st_size
    with path.open('rb') as handle:
        if handle.read(2)!=b'MZ':raise ValueError('Missing Windows MZ executable header')
        handle.seek(60);raw=handle.read(4)
        if len(raw)!=4:raise ValueError('Truncated DOS header')
        offset=struct.unpack('<I',raw)[0]
        if offset<64 or offset+26>size:raise ValueError('Invalid PE header offset')
        handle.seek(offset);header=handle.read(26)
        if header[:4]!=b'PE\0\0' or struct.unpack_from('<H',header,4)[0]!=0x8664 or struct.unpack_from('<H',header,24)[0]!=0x20b:
            raise ValueError('Expected a Windows x64 PE32+ executable')
    return {'format':'PE32+','machine':'AMD64','bytes':size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def unpack(archive,dest):
    total=0;seen=set()
    with zipfile.ZipFile(archive) as z:
        members=z.infolist()
        if len(members)>10000:raise ValueError('Portable ZIP has too many entries')
        for member in members:
            raw_name=member.orig_filename
            name=PurePosixPath(raw_name)
            if not name.parts or name.is_absolute() or '..' in name.parts or '\\' in raw_name or ':' in raw_name or '\0' in raw_name or stat.S_ISLNK(member.external_attr>>16):
                raise ValueError('Unsafe portable ZIP member')
            key=str(name).casefold()
            if key in seen:raise ValueError('Duplicate portable ZIP member')
            seen.add(key);total+=member.file_size
            if total>2*1024**3:raise ValueError('Portable ZIP exceeds size limit')
        z.extractall(dest)
        # zipfile does not restore executable permission on POSIX.
        if os.name!='nt':
            for member in members:
                target=Path(dest)/member.filename
                if target.is_file() and (member.external_attr>>16)&stat.S_IXUSR:target.chmod(target.stat().st_mode|stat.S_IXUSR)


def verify(archive,report):
    archive=Path(archive).resolve();report=Path(report).resolve();report.parent.mkdir(parents=True,exist_ok=True)
    result={'ok':False,'platform':sys.platform,'archive':archive.name,'runner_scope':'Packaged runtime; not a clean Windows 11 desktop'}
    smoke_report=report.with_name(report.stem+'-smoke.json')
    try:
        checksum=archive.with_suffix(archive.suffix+'.sha256').read_text(encoding='ascii').split()[0]
        if hashlib.sha256(archive.read_bytes()).hexdigest()!=checksum:raise ValueError('Portable ZIP SHA-256 mismatch')
        with tempfile.TemporaryDirectory(prefix='mandarin-unpacked-') as temp:
            root=Path(temp);unpack(archive,root)
            windows=sys.platform=='win32';name='Mandarin' if windows else 'Mandarin-Linux-Qt-validation'
            folder=root/name;exe=folder/(name+'.exe' if windows else name)
            if not exe.is_file():raise ValueError('Packaged executable missing')
            if windows:
                result['pe']=inspect_pe(exe)
                for relative in ['_internal/python312.dll','_internal/PySide6/Qt/plugins/platforms/qwindows.dll']:
                    # PyInstaller's Windows Qt layout uses PySide6/plugins rather
                    # than the Linux PySide6/Qt/plugins layout on some releases.
                    options=[folder/relative,folder/relative.replace('PySide6/Qt/plugins','PySide6/plugins')]
                    if not any(path.is_file() for path in options):raise ValueError('Bundled Windows runtime component missing: '+relative)
            if not (folder/'licenses/Python-LICENSE.txt').is_file():raise ValueError('Bundled Python license missing')
            env=dict(os.environ)
            for key in list(env):
                if key in {'PYTHONPATH','PYTHONHOME','VIRTUAL_ENV','QT_PLUGIN_PATH','QML2_IMPORT_PATH','QT_QPA_PLATFORM'} or key.startswith('MANDARIN_'):env.pop(key,None)
            env['PATH']=str(Path(env.get('SystemRoot',r'C:\Windows'))/'System32') if windows else ''
            env['LOCALAPPDATA']=str(root/'profile');env['XDG_CONFIG_HOME']=str(root/'config')
            if not windows:env['QT_QPA_PLATFORM']='offscreen'
            clean=root/'working directory العربية';clean.mkdir()
            if smoke_report.exists():smoke_report.unlink()
            subprocess.run([str(exe),'--self-test',str(smoke_report)],cwd=clean,env=env,check=True,timeout=90)
            smoke=json.loads(smoke_report.read_text(encoding='utf-8'))
            if not smoke.get('ok') or not smoke.get('frozen') or smoke.get('platform')!=sys.platform:raise ValueError('Unpacked frozen smoke failed or reported the wrong platform')
            result.update(ok=True,checksum='PASS',zip_extraction='PASS',bundled_runtime_launch='PASS',build_python_removed_from_path=True,smoke=smoke)
    except Exception as error:result.update(error=str(error),traceback=traceback.format_exc())
    result.update(native_explorer_drag='NOT TESTED',fresh_windows_11='NOT TESTED')
    report.write_text(json.dumps(result,indent=2),encoding='utf-8')
    if not result['ok']:raise RuntimeError(result.get('error','Portable verification failed'))
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('archive');parser.add_argument('--report',required=True);args=parser.parse_args();verify(args.archive,args.report)

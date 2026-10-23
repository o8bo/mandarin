"""OS-specific primitives used by both frontends. No GTK/Qt imports."""
from __future__ import annotations
import ctypes
import errno
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import unicodedata

WINDOWS = sys.platform == 'win32'
TOOLS = ('ffmpeg', 'ffprobe', 'libreoffice', 'pdftoppm', 'pdftotext', 'pdfimages')


def resource_root():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))


def application_root():
    return Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else resource_root()


def settings_path():
    base = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) if WINDOWS else Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    return base / 'Mandarin' / 'tools.json'


def read_tools():
    try:
        data = json.loads(settings_path().read_text(encoding='utf-8'))
        return {k: v for k, v in data.items() if k in TOOLS and isinstance(v, str)} if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_tool(name, path):
    if name not in TOOLS:
        raise ValueError('Unknown conversion engine')
    values = read_tools()
    if path:
        if not Path(path).is_file():
            raise ValueError('Choose an existing executable file')
        values[name] = str(Path(path).resolve())
    else:
        values.pop(name, None)
    target = settings_path(); target.parent.mkdir(parents=True, exist_ok=True)
    import tempfile
    fd, temporary = tempfile.mkstemp(prefix='.tools-', dir=target.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(values, handle, indent=2); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def discover_tool(name):
    configured = os.environ.get('MANDARIN_' + name.upper() + '_PATH') or read_tools().get(name)
    if configured:
        p = Path(configured).expanduser()
        return str(p.resolve()) if p.is_file() and (WINDOWS or os.access(p, os.X_OK)) else None
    names = ['soffice.com', 'soffice.exe'] if WINDOWS and name == 'libreoffice' else ['libreoffice', 'soffice'] if name == 'libreoffice' else [name + ('.exe' if WINDOWS else '')]
    for base in [application_root(), resource_root()]:
        for folder in [base/'tools', base/'tools/ffmpeg/bin', base/'tools/poppler/Library/bin', base/'tools/poppler/bin', base/'vendor/usr/bin', base/'vendor/bin']:
            # Linux binaries from an old working copy are not Windows tools.
            for exe in names:
                p = folder / exe
                if p.is_file() and (WINDOWS or os.access(p, os.X_OK)):
                    return str(p.resolve())
    for exe in names:
        path = shutil.which(exe)
        if path: return path
    if WINDOWS and name == 'libreoffice':
        for root in [os.environ.get('ProgramFiles'), os.environ.get('ProgramFiles(x86)')]:
            if root:
                for exe in names:
                    p = Path(root) / 'LibreOffice/program' / exe
                    if p.is_file(): return str(p)
    return None


def safe_name(name):
    """Portable component validation, also applied to archive member names."""
    if not isinstance(name, str) or not name or name in ('.', '..'):
        raise ValueError('Invalid filename')
    if any(ord(c) < 32 or c in '<>:"/\\|?*' for c in name) or name.endswith((' ', '.')):
        raise ValueError('Unsafe or non-portable filename: ' + name)
    stem = unicodedata.normalize('NFKC', name.split('.')[0]).rstrip(' ').upper()
    if stem in {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$'} or stem in {f'{prefix}{i}' for prefix in ('COM', 'LPT') for i in range(1, 10)}:
        raise ValueError('Windows reserved filename: ' + name)
    return name


def publish_file(source, parent, name):
    parent = Path(parent); parent.mkdir(parents=True, exist_ok=True)
    if WINDOWS: safe_name(name)
    desired = Path(name)
    for n in range(100000):
        dest = parent / (name if n == 0 else f'{desired.stem} ({n}){desired.suffix}')
        try:
            if WINDOWS:
                # os.rename on Windows fails if the destination exists (unlike POSIX).
                os.rename(source, dest)
            else:
                os.link(source, dest)
            return str(dest.resolve())
        except FileExistsError:
            continue
    raise RuntimeError('Too many colliding output names')


def publish_directory(source, parent, name):
    parent = Path(parent)
    if WINDOWS: safe_name(name)
    if not WINDOWS:
        libc = ctypes.CDLL(None, use_errno=True)
        rename = getattr(libc, 'renameat2', None)
        if rename is None: raise RuntimeError('Atomic directory publication requires Linux renameat2')
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
    for n in range(100000):
        dest = parent / (name if not n else f'{name} ({n})')
        if WINDOWS:
            try: os.rename(source, dest); return str(dest.resolve())
            except FileExistsError: continue
        else:
            if rename(-100, os.fsencode(source), -100, os.fsencode(dest), 1) == 0: return str(dest.resolve())
            error = ctypes.get_errno()
            if error in (errno.EEXIST, errno.ENOTEMPTY): continue
            raise OSError(error, os.strerror(error))
    raise RuntimeError('Too many colliding output names')


class WindowsJob:
    """A kill-on-close Windows Job; assign a suspended child before resuming it.

    Only documented Win32 APIs are used. This code requires a native Windows test.
    """
    def __init__(self):
        from ctypes import wintypes as w
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        class Basic(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64), ('flags', w.DWORD), ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t), ('active', w.DWORD), ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
        class Extended(ctypes.Structure):
            _fields_ = [('basic', Basic), ('io', IO), ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t), ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]
        self.k.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]; self.k.CreateJobObjectW.restype = w.HANDLE
        self.k.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]; self.k.SetInformationJobObject.restype = w.BOOL
        self.k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]; self.k.AssignProcessToJobObject.restype = w.BOOL
        self.k.CloseHandle.argtypes = [w.HANDLE]; self.k.CloseHandle.restype = w.BOOL
        self.handle = self.k.CreateJobObjectW(None, None)
        if not self.handle: raise ctypes.WinError(ctypes.get_last_error())
        info = Extended(); info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.k.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            self.close(); raise ctypes.WinError(ctypes.get_last_error())

    def attach_and_resume(self, process):
        from ctypes import wintypes as w
        if not self.k.AssignProcessToJobObject(self.handle, w.HANDLE(int(process._handle))):
            raise ctypes.WinError(ctypes.get_last_error())
        class ThreadEntry(ctypes.Structure):
            _fields_ = [('size', w.DWORD), ('usage', w.DWORD), ('id', w.DWORD), ('owner', w.DWORD), ('base_priority', w.LONG), ('delta_priority', w.LONG), ('flags', w.DWORD)]
        self.k.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]; self.k.CreateToolhelp32Snapshot.restype = w.HANDLE
        self.k.Thread32First.argtypes = [w.HANDLE, ctypes.POINTER(ThreadEntry)]; self.k.Thread32First.restype = w.BOOL
        self.k.Thread32Next.argtypes = self.k.Thread32First.argtypes; self.k.Thread32Next.restype = w.BOOL
        self.k.OpenThread.argtypes = [w.DWORD, w.BOOL, w.DWORD]; self.k.OpenThread.restype = w.HANDLE
        self.k.ResumeThread.argtypes = [w.HANDLE]; self.k.ResumeThread.restype = w.DWORD
        snapshot = self.k.CreateToolhelp32Snapshot(4, 0)  # TH32CS_SNAPTHREAD
        if snapshot == w.HANDLE(-1).value: raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = ThreadEntry(); entry.size = ctypes.sizeof(entry)
            ok = self.k.Thread32First(snapshot, ctypes.byref(entry))
            while ok:
                if entry.owner == process.pid:
                    thread = self.k.OpenThread(2, False, entry.id)  # THREAD_SUSPEND_RESUME
                    if not thread: raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        if self.k.ResumeThread(thread) == 0xFFFFFFFF: raise ctypes.WinError(ctypes.get_last_error())
                    finally: self.k.CloseHandle(thread)
                    return
                ok = self.k.Thread32Next(snapshot, ctypes.byref(entry))
            raise RuntimeError('Could not find the suspended converter thread')
        finally: self.k.CloseHandle(snapshot)

    def close(self):
        if self.handle:
            self.k.CloseHandle(self.handle); self.handle = None


def run_process(args, cancelled=None, env=None):
    import tempfile
    job = None; process = None
    if cancelled is not None and cancelled.is_set():raise InterruptedError('Operation cancelled.')
    with tempfile.TemporaryFile() as output:
        try:
            if WINDOWS:
                job = WindowsJob()
                flags = 0x4 | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
                process = subprocess.Popen([str(a) for a in args], stdin=subprocess.DEVNULL, stdout=output, stderr=output, env=env, creationflags=flags)
                job.attach_and_resume(process)
            else:
                process = subprocess.Popen([str(a) for a in args], stdin=subprocess.DEVNULL, stdout=output, stderr=output, env=env, start_new_session=True)
            while process.poll() is None:
                if cancelled is not None and cancelled.is_set():
                    raise InterruptedError('Operation cancelled.')
                time.sleep(.05)
            if process.returncode:
                output.seek(0, 2); length = output.tell(); output.seek(max(0, length - 6000))
                raise RuntimeError(output.read().decode('utf-8', 'replace').strip() or f'Converter exited with status {process.returncode}')
        finally:
            if job: job.close()
            if process and process.poll() is None:
                if WINDOWS:
                    process.kill()  # Also covers an assignment failure while suspended.
                else:
                    os.killpg(process.pid, signal.SIGTERM)
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    if not WINDOWS: os.killpg(process.pid, signal.SIGKILL)
                    else: process.kill()
                    process.wait(timeout=3)
            if process and not WINDOWS:
                # Descendants may ignore TERM after the parent exits. The entire
                # group is private to this operation, so finish its cleanup.
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass

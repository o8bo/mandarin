"""Bounded, generated-data process fixtures for source/frozen self-tests only."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def command(kind, folder):
    prefix=[sys.executable] if getattr(sys,'frozen',False) else [sys.executable,'-m','mandarin']
    return prefix+['--_process-fixture',kind,str(folder)]


def run(kind, folder):
    folder=Path(folder)
    if kind=='leaf':
        if os.name!='nt':signal.signal(signal.SIGTERM,signal.SIG_IGN)
        (folder/'leaf-ready').write_text('ready')
        time.sleep(3)
        (folder/'survived').write_text('Process tree cancellation failed')
        return 0
    if kind=='parent':
        child=subprocess.Popen(command('leaf',folder))
        try:
            deadline=time.monotonic()+12
            while not (folder/'leaf-ready').exists():
                if child.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Fixture child did not start')
                time.sleep(.02)
            (folder/'parent-ready').write_text('ready')
            time.sleep(15)
        finally:
            if child.poll() is None:child.kill()
            child.wait(timeout=5)
        return 0
    if kind=='error':
        if sys.stderr:sys.stderr.write('Mandarin subprocess fixture failure')
        return 7
    raise ValueError('Unknown process fixture')

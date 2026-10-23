"""PyInstaller and source entry; error logging survives a windowed Windows build."""
from pathlib import Path
import os
import sys
import traceback


if __name__=='__main__':
    try:
        from mandarin.__main__ import main
        code=main()
    except Exception:
        details=traceback.format_exc()
        if sys.stderr:print(details,file=sys.stderr)
        if sys.platform=='win32':
            folder=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'Mandarin'
            folder.mkdir(parents=True,exist_ok=True);log=folder/'startup-error.log';log.write_text(details,encoding='utf-8')
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,'Mandarin could not start. Details: '+str(log),'Mandarin startup error',0x10)
        code=1
    raise SystemExit(code)

#!/usr/bin/env python3
"""Install a private per-user copy and a desktop menu launcher. No root needed."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile


def main():
    source = Path(__file__).resolve().parent
    share = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
    target = share / 'mandarin'
    if target.is_symlink():
        raise SystemExit('Refusing a symbolic-link installation destination.')
    if target.exists() and target.resolve() != source:
        raise SystemExit(f'Mandarin is already installed at {target}. Keep or remove that copy explicitly before reinstalling.')
    if target.resolve() != source:
        share.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.mandarin-install-', dir=share) as scratch:
            staged = Path(scratch) / 'app'
            shutil.copytree(source, staged, symlinks=True,
                ignore=shutil.ignore_patterns('__pycache__', 'verification', 'screenshot*.png', '*.whl', '*.deb', 'test_*.py', '.dev-deps', '.venv', '.git', 'dist', 'build', '.github'))
            import ctypes
            libc = ctypes.CDLL(None, use_errno=True)
            rename = libc.renameat2
            rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            rename.restype = ctypes.c_int
            if rename(-100, os.fsencode(staged), -100, os.fsencode(target), 1) != 0:
                error = ctypes.get_errno()
                raise OSError(error, os.strerror(error), str(target))
    (target / 'launch.sh').chmod(0o755)
    applications = share / 'applications'
    applications.mkdir(parents=True, exist_ok=True)
    text = f'''[Desktop Entry]
Type=Application
Name=Mandarin
Comment=Local file conversion and tools for Linux
Exec="{target / 'launch.sh'}" %F
Icon={target / 'assets/mandarin.svg'}
Terminal=false
Categories=Utility;
StartupNotify=true
StartupWMClass=Mandarin
MimeType=image/png;image/jpeg;image/webp;application/pdf;video/mp4;audio/mpeg;application/zip;text/plain;
'''
    entry = applications / 'mandarin.desktop'
    entry.write_text(text, encoding='utf-8')
    if shutil.which('update-desktop-database'):
        subprocess.run(['update-desktop-database', str(applications)], check=False)
    print('Installed:', target)
    print('Desktop launcher:', entry)
    print('Launch:', target / 'launch.sh')


if __name__ == '__main__':
    main()

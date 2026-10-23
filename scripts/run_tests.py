"""Run the actual suite and preserve machine-readable outcomes, including skips."""
import argparse
import importlib.metadata as metadata
import json
from pathlib import Path
import platform
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',default='verification/tests.json');parser.add_argument('--require-windows',action='store_true');args=parser.parse_args()
    if args.require_windows and sys.platform!='win32':parser.error('--require-windows requires native Windows')
    suite=unittest.defaultTestLoader.loadTestsFromNames(['test_engine','test_platform','test_qt','test_build_tools'])
    started=time.monotonic();result=unittest.TextTestRunner(verbosity=2).run(suite)
    versions={}
    for name in ['Pillow','pypdf','PySide6-Essentials','shiboken6']:
        try:versions[name]=metadata.version(name)
        except metadata.PackageNotFoundError:versions[name]='NOT INSTALLED'
    disallowed_skips=[(str(t),reason) for t,reason in result.skipped if not any(s in reason for s in ['FFmpeg unavailable','PDF tools unavailable','LibreOffice not installed'])] if args.require_windows else []
    report={'platform':platform.platform(),'python':platform.python_version(),'dependencies':versions,
        'tests_run':result.testsRun,'passed':result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
        'failures':[(str(t),s) for t,s in result.failures],'errors':[(str(t),s) for t,s in result.errors],
        'skipped_not_tested':[(str(t),s) for t,s in result.skipped],
        'duration_seconds':round(time.monotonic()-started,3),'successful':result.wasSuccessful() and not disallowed_skips,'required_windows_tests':args.require_windows,'disallowed_required_skips':disallowed_skips,
        'scope':'Automated shared engine and Qt events; native Explorer and fresh Windows 11 acceptance separate'}
    target=Path(args.report);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return 0 if report['successful'] else 1

if __name__=='__main__':raise SystemExit(main())

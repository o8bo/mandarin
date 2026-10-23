"""Expose actual CI outcomes without conflating a server runner with Windows 11."""
import json
import os
from pathlib import Path


def main():
    tests=Path('verification/windows-tests.json');portable=Path('dist/Mandarin-portable-verification.json')
    rows=[('Automated tests step',os.environ.get('TEST_OUTCOME','NOT RUN')),
        ('Build/ZIP verification step',os.environ.get('BUILD_OUTCOME','NOT RUN'))]
    if tests.is_file():
        record=json.loads(tests.read_text(encoding='utf-8'))
        rows.append(('Test counts',f"{record['tests_run']} run; {record['passed']} passed; {len(record['skipped_not_tested'])} NOT TESTED skips"))
    if portable.is_file():
        record=json.loads(portable.read_text(encoding='utf-8'))
        rows.append(('Unpacked ZIP / bundled runtime','PASS' if record.get('ok') else 'FAIL'))
    rows.extend([('Interactive Windows 11 / Explorer drag','NOT TESTED'),('Optional external engines','Review explicit skips; not bundled')])
    content='# Windows candidate verification\n\n| Check | Actual result |\n|---|---|\n'+'\n'.join(f'| {name} | {value} |' for name,value in rows)+'\n\nA successful Windows Server runner build does not establish fresh Windows 11 desktop acceptance.\n'
    destination=os.environ.get('GITHUB_STEP_SUMMARY')
    if destination:
        with open(destination,'a',encoding='utf-8') as handle:handle.write(content)
    else:print(content)

if __name__=='__main__':main()

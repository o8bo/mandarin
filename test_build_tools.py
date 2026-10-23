"""Reject malformed architecture headers and unsafe portable ZIPs before execution."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

spec=importlib.util.spec_from_file_location('verify_portable',Path(__file__).parent/'scripts/verify_portable.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)

class BuildVerificationTests(unittest.TestCase):
    def test_rejects_non_windows_or_wrong_architecture(self):
        with tempfile.TemporaryDirectory() as temp:
            exe=Path(temp)/'app.exe'
            for data in [b'\x7fELF',b'MZ'+b'\0'*70]:
                exe.write_bytes(data)
                with self.assertRaises(ValueError):v.inspect_pe(exe)
            data=bytearray(256);data[:2]=b'MZ';struct.pack_into('<I',data,60,128);data[128:132]=b'PE\0\0';struct.pack_into('<H',data,132,0x14c);struct.pack_into('<H',data,152,0x10b);exe.write_bytes(data)
            with self.assertRaises(ValueError):v.inspect_pe(exe)
    def test_rejects_archive_escape_and_case_collisions(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);archive=root/'app.zip'
            for index,names in enumerate([['../escape'],['C:/escape'],['x\\escape'],['Mandarin/a','Mandarin/A']]):
                with self.subTest(names=names):
                    with zipfile.ZipFile(archive,'w') as z:
                        for name in names:
                            info=zipfile.ZipInfo(name);info.filename=info.orig_filename=name
                            z.writestr(info,'fixture')
                    output=root/f'out-{index}'
                    with self.assertRaises(ValueError):v.unpack(archive,output)
                    self.assertFalse(output.exists())

if __name__=='__main__':unittest.main()

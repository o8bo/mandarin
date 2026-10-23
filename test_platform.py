"""Portable safety tests; native Windows cases skip explicitly on other hosts."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile
from mandarin import engine, platform_support as p

class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_reserved_and_unsafe_names(self):
        for name in ['CON','nul.txt','COM1.zip','LPT9','COM¹.txt','CON .txt','a:b','x.','x ','../a','a\\b','a\0b']:
            with self.subTest(name=name),self.assertRaises(ValueError):p.safe_name(name)
        self.assertEqual(p.safe_name('ملف 日本語.txt'),'ملف 日本語.txt')
    def test_missing_explicit_tool_does_not_fall_back(self):
        with patch.dict(os.environ,{'MANDARIN_FFMPEG_PATH':str(self.root/'missing')}):self.assertIsNone(p.discover_tool('ffmpeg'))
    def test_configuration_roundtrip_and_reset(self):
        tool=self.root/'tool';tool.write_text('test')
        with patch.object(p,'settings_path',return_value=self.root/'tools.json'):
            p.save_tool('ffmpeg',str(tool));self.assertEqual(p.read_tools()['ffmpeg'],str(tool.resolve()))
            p.save_tool('ffmpeg',None);self.assertEqual(p.read_tools(),{})
            with self.assertRaises(ValueError):p.save_tool('ffmpeg',str(self.root/'missing'))
    def test_no_overwrite_unicode_file_and_directory(self):
        source=self.root/'source';source.write_text('new');out=self.root/'صورة.txt';out.write_text('old')
        result=Path(p.publish_file(source,self.root,out.name));self.assertNotEqual(result,out);self.assertEqual(out.read_text(),'old');self.assertEqual(result.read_text(),'new')
        original=self.root/'folder';original.mkdir();(original/'keep').write_text('safe')
        staging=self.root/'staging';staging.mkdir();(staging/'new').write_text('new')
        result=Path(p.publish_directory(staging,self.root,'folder'));self.assertNotEqual(result,original);self.assertEqual((original/'keep').read_text(),'safe')
    def test_archive_windows_paths_rejected_and_staging_cleaned(self):
        for name in ['NUL.txt','C:/escape','a:stream','trailing.','a\\b']:
            with self.subTest(name=name):
                archive=self.root/'bad.zip'
                with zipfile.ZipFile(archive,'w') as z:z.writestr(name,'bad')
                with self.assertRaises(engine.OperationError):engine.run_operation('archive:extract',[archive])
                self.assertEqual([x.name for x in self.root.iterdir()],['bad.zip'])
    def test_real_document_conversion(self):
        if not engine.capabilities()['libreoffice']:self.skipTest('LibreOffice not installed: document conversion NOT TESTED')
        source=self.root/'رسالة.txt';source.write_text('Mandarin document fixture',encoding='utf-8')
        result=Path(engine.run_operation('document:pdf',[source])['outputs'][0]);self.assertTrue(result.read_bytes().startswith(b'%PDF-'))
    def test_missing_media_engine_disables_operations(self):
        with patch.object(engine,'capabilities',return_value=dict(engine.capabilities(),ffmpeg=None)):
            self.assertFalse(any(o['available'] for o in engine.get_operations([self.root/'a.mp4'])))
    def test_process_error_is_reported(self):
        with self.assertRaisesRegex(RuntimeError,'fixture failure'):
            p.run_process([sys.executable,'-c','import sys;sys.stderr.write("fixture failure");sys.exit(2)'])
    def test_real_process_tree_cancellation(self):
        marker=self.root/'child-survived';ready=self.root/'ready';cancel=threading.Event();errors=[]
        child='import pathlib,time,signal;'+('signal.signal(signal.SIGTERM,signal.SIG_IGN);' if sys.platform!='win32' else '')+'time.sleep(1.8);pathlib.Path('+repr(str(marker))+').write_text("survived")'
        parent='import pathlib,subprocess,sys,time;subprocess.Popen([sys.executable,"-c",'+repr(child)+']);pathlib.Path('+repr(str(ready))+').write_text("ready");time.sleep(30)'
        def work():
            try:p.run_process([sys.executable,'-c',parent],cancel)
            except BaseException as error:errors.append(error)
        thread=threading.Thread(target=work);thread.start()
        try:
            deadline=time.monotonic()+8
            while not ready.exists() and thread.is_alive() and time.monotonic()<deadline:time.sleep(.02)
            self.assertTrue(ready.exists(),'Subprocess failed to start')
        finally:cancel.set();thread.join(8)
        self.assertFalse(thread.is_alive());self.assertTrue(errors);self.assertIsInstance(errors[0],InterruptedError)
        time.sleep(2);self.assertFalse(marker.exists(),'Descendant survived cancellation')
    @unittest.skipUnless(sys.platform=='win32','Native Windows file locking NOT TESTED on this host')
    def test_windows_locked_destination_preserved(self):
        source=self.root/'source';source.write_bytes(b'new');target=self.root/'locked';target.write_bytes(b'old')
        with target.open('rb'):
            result=p.publish_file(source,self.root,'locked')
            self.assertNotEqual(result,str(target));self.assertEqual(target.read_bytes(),b'old')
    @unittest.skipUnless(sys.platform=='win32','Native Windows Job objects NOT TESTED on this host')
    def test_windows_suspended_process_job_startup(self):
        target=self.root/'job-started'
        p.run_process([sys.executable,'-c','from pathlib import Path;Path('+repr(str(target))+').write_text("yes")'])
        self.assertEqual(target.read_text(),'yes')

if __name__=='__main__':unittest.main()

import os
from pathlib import Path
import tempfile
import threading
import unittest
import zipfile
from mandarin import engine as e

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def image(self,name='rgba.png'):
        from PIL import Image
        p=self.root/name;Image.new('RGBA',(40,20),(255,0,0,0)).save(p);return p
    @unittest.skipUnless(e.capabilities()['pillow'],'Pillow unavailable')
    def test_image_alpha_and_collision_preserve_original(self):
        from PIL import Image
        p=self.image('odd $ ` [name].png');before=p.read_bytes()
        a=e.run_operation('image:jpeg',[p])['outputs'][0]
        b=e.run_operation('image:jpeg',[p])['outputs'][0]
        self.assertNotEqual(a,b);self.assertEqual(before,p.read_bytes())
        with Image.open(a) as im:self.assertTrue(all(x>245 for x in im.getpixel((0,0))))
        resized=e.run_operation('image:resize',[p],{'width':10,'height':10})['outputs'][0]
        with Image.open(resized) as im:self.assertEqual(im.size,(10,5))
    @unittest.skipUnless(e.capabilities()['pillow'],'Pillow unavailable')
    def test_all_advertised_image_writers_produce_readable_files(self):
        from PIL import Image
        p=self.image('صورة 日本語.png')
        for operation in e.get_operations([p]):
            if not operation['available']:continue
            with self.subTest(operation=operation['id']):
                result=Path(e.run_operation(operation['id'],[p])['outputs'][0])
                if result.suffix=='.pdf':self.assertTrue(result.read_bytes().startswith(b'%PDF-'))
                else:
                    with Image.open(result) as image:image.load();self.assertGreater(image.width,0)
    def test_zip_traversal_and_symlink_rejected_without_outputs(self):
        for name,symlink in [('../escape.txt',False),('link',True)]:
            p=self.root/'bad.zip'
            with zipfile.ZipFile(p,'w') as z:
                if symlink:
                    info=zipfile.ZipInfo(name);info.external_attr=(0o120777<<16);z.writestr(info,'/etc/passwd')
                else:z.writestr(name,'bad')
            with self.assertRaises(e.OperationError):e.run_operation('archive:extract',[p])
            self.assertFalse((self.root/'bad-extract').exists())
        self.assertFalse((self.root.parent/'escape.txt').exists())
    def test_archives_roundtrip_and_bomb_limit(self):
        folder=self.root/'input';folder.mkdir();(folder/'a.txt').write_text('hello')
        for fmt in ['zip','tar','tar.gz']:
            out=e.run_operation('archive:'+fmt,[folder])['outputs'][0]
            extracted=Path(e.run_operation('archive:extract',[out])['outputs'][0])
            self.assertEqual((extracted/'input'/'a.txt').read_text(),'hello')
        old=e.MAX_ARCHIVE_BYTES;e.MAX_ARCHIVE_BYTES=2
        try:
            with self.assertRaises(e.OperationError):e.run_operation('archive:extract',[out])
        finally:e.MAX_ARCHIVE_BYTES=old
    def test_subtitle_timing_roundtrip(self):
        p=self.root/'a.srt';p.write_text('1\n00:01:02,123 --> 00:01:05,456\nأهلاً\n\n2\n00:01:07,000 --> 00:01:08,000\nSecond cue\n',encoding='utf-8')
        vtt=Path(e.run_operation('subtitle:vtt',[p])['outputs'][0]);self.assertIn('00:01:02.123 --> 00:01:05.456',vtt.read_text(encoding='utf-8'))
        back=Path(e.run_operation('subtitle:srt',[vtt])['outputs'][0]);self.assertIn('00:01:02,123 --> 00:01:05,456',back.read_text(encoding='utf-8'));self.assertIn('أهلاً',back.read_text(encoding='utf-8'))
        txt=Path(e.run_operation('subtitle:txt',[vtt])['outputs'][0]);self.assertNotIn('-->',txt.read_text(encoding='utf-8'))
    @unittest.skipUnless(e.capabilities()['pypdf'],'pypdf unavailable')
    def test_pdf_merge_split_rotate(self):
        from pypdf import PdfWriter,PdfReader
        paths=[]
        for n in range(2):
            p=self.root/f'{n}.pdf';w=PdfWriter();w.add_blank_page(width=100+n,height=200)
            with p.open('wb') as f:w.write(f)
            paths.append(p)
        merged=e.run_operation('pdf:merge',paths)['outputs'][0];self.assertEqual(len(PdfReader(merged).pages),2)
        split=e.run_operation('pdf:split',[merged])['outputs'];self.assertEqual(len(split),2)
        rotated=e.run_operation('pdf:rotate',[split[0]],{'degrees':'90'})['outputs'][0]
        self.assertEqual(PdfReader(rotated).pages[0].rotation,90)
    @unittest.skipUnless(e.capabilities()['pypdf'] and e.capabilities()['pdftoppm'],'PDF tools unavailable')
    def test_pdf_raster_conversion(self):
        from pypdf import PdfWriter
        from PIL import Image
        p=self.root/'pages.pdf';w=PdfWriter();w.add_blank_page(width=144,height=72)
        with p.open('wb') as f:w.write(f)
        for fmt in ['png','jpeg']:
            out=e.run_operation('pdf:'+fmt,[p])['outputs'];self.assertEqual(len(out),1)
            with Image.open(out[0]) as im:self.assertEqual(im.size,(300,150))
    @unittest.skipUnless(e.capabilities()['ffmpeg'],'FFmpeg unavailable')
    def test_media_formats_and_trim(self):
        import wave
        p=self.root/'tone.wav'
        with wave.open(str(p),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b'\0\0'*8000)
        for fmt in ['mp3','ogg','m4a','opus','aiff']:
            out=Path(e.run_operation('media:'+fmt,[p])['outputs'][0]);self.assertGreater(out.stat().st_size,100)
        out=Path(e.run_operation('media:trim',[p],{'start':0.2,'duration':0.3})['outputs'][0])
        with wave.open(str(out)) as w:self.assertAlmostEqual(w.getnframes()/w.getframerate(),0.3,places=2)
        video=self.root/'video.mp4'
        e._process([e.capabilities()['ffmpeg'],'-nostdin','-loglevel','error','-f','lavfi','-i','color=c=red:s=32x32:d=0.3','-c:v','libx264','-pix_fmt','yuv420p',video])
        for fmt in ['mov','mkv','webm','gif']:
            out=Path(e.run_operation('media:'+fmt,[video])['outputs'][0]);self.assertGreater(out.stat().st_size,100)
        webm=Path(e.run_operation('media:webm',[video])['outputs'][0])
        for operation,options in [('compress',{}),('trim',{'start':0,'duration':.1}),('remove_audio',{})]:
            out=Path(e.run_operation('media:'+operation,[webm],options)['outputs'][0]);self.assertGreater(out.stat().st_size,100)
    @unittest.skipUnless(e.capabilities()['pillow'],'Pillow unavailable')
    def test_batch_failure_reports_completed_outputs(self):
        first=self.image('valid.png');second=self.root/'malformed.png';second.write_bytes(b'not an image')
        with self.assertRaises(Exception) as ctx:e.run_operation('image:jpeg',[first,second])
        result=ctx.exception.partial_result
        self.assertEqual(len(result['outputs']),1)
        self.assertTrue(Path(result['outputs'][0]).is_file())
        self.assertEqual(result['warnings'],[])
        self.assertEqual(second.read_bytes(),b'not an image')
    @unittest.skipUnless(e.capabilities()['pillow'],'Pillow unavailable')
    def test_batch_cancellation_reports_completed_outputs(self):
        first=self.image('first.png');second=self.image('second.png');cancel=threading.Event()
        def progress(completed,total,message):
            if completed==1:cancel.set()
        with self.assertRaises(e.Cancelled) as ctx:e.run_operation('image:jpeg',[first,second],progress=progress,cancelled=cancel)
        result=ctx.exception.partial_result
        self.assertEqual(len(result['outputs']),1)
        self.assertTrue(Path(result['outputs'][0]).is_file())
        self.assertFalse((self.root/'second-jpeg.jpeg').exists())
    def test_cancelled_before_work(self):
        p=self.root/'a.srt';p.write_text('a');cancel=threading.Event();cancel.set()
        with self.assertRaises(e.Cancelled):e.run_operation('subtitle:vtt',[p],cancelled=cancel)
        self.assertEqual(len(list(self.root.iterdir())),1)
    def test_capabilities_are_json_safe(self):
        import json
        json.dumps(e.capabilities());json.dumps(e.get_operations([self.root/'x.mp4']))
    @unittest.skipUnless(e.capabilities()['ffmpeg'],'FFmpeg unavailable')
    def test_audio_actual_conversion(self):
        import wave
        p=self.root/'tone.wav'
        with wave.open(str(p),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b'\0\0'*8000)
        out=Path(e.run_operation('media:flac',[p])['outputs'][0]);self.assertEqual(out.read_bytes()[:4],b'fLaC')

if __name__=='__main__':unittest.main()

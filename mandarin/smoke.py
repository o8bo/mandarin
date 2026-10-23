"""Real source/frozen smoke checks. Explorer/manual Windows acceptance is separate."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import traceback
import zipfile


def require(condition,message):
    if not condition:raise RuntimeError(message)


def process_checks(folder):
    from .platform_support import run_process
    from .process_fixture import command
    cancel=threading.Event();errors=[]
    def work():
        try:run_process(command('parent',folder),cancel)
        except BaseException as error:errors.append(error)
    worker=threading.Thread(target=work,name='smoke-process-tree');worker.start()
    try:
        deadline=time.monotonic()+18
        while not (folder/'parent-ready').exists() and worker.is_alive() and time.monotonic()<deadline:time.sleep(.02)
        require((folder/'parent-ready').exists(),'Subprocess parent/child fixture did not become ready: '+str(errors))
    finally:
        cancel.set();worker.join(10)
    require(not worker.is_alive(),'Converter worker did not stop')
    require(len(errors)==1 and isinstance(errors[0],InterruptedError),'Cancellation did not raise InterruptedError: '+str(errors))
    time.sleep(3.2)
    require(not (folder/'survived').exists(),'Child process survived cancellation')
    try:run_process(command('error',folder))
    except RuntimeError as error:require('7' in str(error) or 'fixture failure' in str(error),'Subprocess failure was not reported')
    else:raise RuntimeError('Nonzero subprocess exit was ignored')


def run(report):
    checks={};result={'ok':False,'platform':sys.platform,'frozen':bool(getattr(sys,'frozen',False)),'checks':checks}
    try:
        from PIL import Image
        from pypdf import PdfReader
        from . import engine
        from .qt_ui import QApplication,MainWindow,STYLE,QTimer
        with tempfile.TemporaryDirectory(prefix='mandarin-smoke-') as temp:
            root=Path(temp);source=root/'صورة 日本語 test.png'
            Image.new('RGBA',(48,32),(10,100,30,128)).save(source);original=source.read_bytes()
            first=Path(engine.run_operation('image:jpeg',[source])['outputs'][0]);before=first.read_bytes()
            with Image.open(first) as image:require(image.size==(48,32) and image.format=='JPEG','JPEG conversion failed')
            checks['image_conversion']='PASS';checks['unicode_arabic_filenames']='PASS'
            second=Path(engine.run_operation('image:jpeg',[source])['outputs'][0])
            require(first!=second and first.read_bytes()==before and source.read_bytes()==original,'Original or prior output overwritten')
            checks['collision_safe_publication']='PASS';checks['original_preservation']='PASS'
            other=root/'صورة ثانية.png';Image.new('RGB',(32,32),'orange').save(other)
            batch=engine.run_operation('image:webp',[source,other]);require(len(batch['outputs'])==2,'Batch did not produce both outputs')
            checks['batch_processing']='PASS'
            cancellation=threading.Event()
            def progress(done,total,message):
                if done==1:cancellation.set()
            try:engine.run_operation('image:bmp',[source,other],progress=progress,cancelled=cancellation)
            except engine.Cancelled as error:
                outputs=error.partial_result['outputs'];require(len(outputs)==1 and Path(outputs[0]).is_file(),'Cancellation lost partial results')
            else:raise RuntimeError('Batch cancellation was ignored')
            checks['batch_cancellation_partial_results']='PASS'
            pdf=engine.run_operation('image:pdf',[source])['outputs'][0]
            require(len(PdfReader(io.BytesIO(Path(pdf).read_bytes())).pages)==1,'Image PDF is unreadable')
            rotated=engine.run_operation('pdf:rotate',[pdf],{'degrees':'90'})['outputs'][0]
            require(PdfReader(io.BytesIO(Path(rotated).read_bytes())).pages[0].rotation==90,'PDF rotation failed')
            checks['pdf_image_and_rotation']='PASS'
            folder=root/'مجلد';folder.mkdir();(folder/'نص.txt').write_text('Mandarin archive fixture',encoding='utf-8')
            archive=engine.run_operation('archive:zip',[folder])['outputs'][0]
            extracted=Path(engine.run_operation('archive:extract',[archive])['outputs'][0])
            require((extracted/folder.name/'نص.txt').read_text(encoding='utf-8')=='Mandarin archive fixture','Archive round trip failed')
            bad=root/'unsafe.zip'
            with zipfile.ZipFile(bad,'w') as z:z.writestr('../escape.txt','unsafe')
            try:engine.run_operation('archive:extract',[bad])
            except engine.OperationError:pass
            else:raise RuntimeError('Unsafe archive was accepted')
            require(not (root/'escape.txt').exists(),'Unsafe archive escaped staging')
            checks['archive_roundtrip_and_traversal_rejection']='PASS'
            override='MANDARIN_FFMPEG_PATH';previous=os.environ.get(override)
            try:
                os.environ[override]=str(root/'missing-ffmpeg.exe')
                require(not any(o['available'] for o in engine.get_operations([root/'video.mp4'])),'Missing FFmpeg advertised available operations')
            finally:
                if previous is None:os.environ.pop(override,None)
                else:os.environ[override]=previous
            checks['missing_dependency_detection']='PASS'
            process_checks(root);checks['process_tree_cancellation']='PASS';checks['subprocess_nonzero_exit']='PASS'
            app=QApplication.instance() or QApplication([]);app.setStyleSheet(STYLE)
            window=MainWindow();window.add_paths([str(source)]);window.show()
            QTimer.singleShot(350,app.quit);app.exec()
            require(window.files.count()==1,'GUI selection model did not contain fixture');window.close()
            checks['qt_startup_and_selection']='PASS'
        result.update(ok=True,image_conversion=True,qt_startup=True,file_selection_model=True)
    except Exception as error:
        result.update(error=str(error),traceback=traceback.format_exc())
    result.update(native_explorer_drag='NOT TESTED',fresh_windows_11='NOT TESTED',
        optional_external_engine_conversions='NOT TESTED by this smoke',
        gui_scope='automated Qt startup/selection; native Explorer and manual desktop acceptance separate')
    report=Path(report);report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(result,indent=2),encoding='utf-8')
    return 0 if result['ok'] else 1

"""Qt integration tests. Synthetic Qt drops do not certify Windows Explorer OLE."""
import tempfile
import time
import sys
import traceback
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QMimeData,QUrl,QPoint,QPointF,QTimer,QEventLoop
from PySide6.QtGui import QDragEnterEvent,QDropEvent
from PySide6.QtTest import QTest
from mandarin.qt_ui import QApplication,MainWindow,RadialMenu,OptionsDialog,STYLE,local_drop_paths
from mandarin import engine

class QtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setStyleSheet(STYLE)
    def setUp(self):
        from PIL import Image
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.source=self.root/'صورة 日本語.png';Image.new('RGBA',(40,20),(10,20,30,128)).save(self.source)
        self.window=MainWindow();self.window.show();self.app.processEvents()
    def tearDown(self):
        self.window.cancel();self.pump_until_idle(8000)
        self.window.close();self.app.processEvents();self.temp.cleanup()
    def pump_until_idle(self,timeout_ms):
        if not self.window.working:return
        # A real Qt event loop releases the GIL for the conversion worker.
        # Repeated QTest.qWait calls can starve Python workers on Windows.
        loop=QEventLoop();poll=QTimer(loop);timeout=QTimer(loop)
        poll.timeout.connect(lambda:loop.quit() if not self.window.working else None)
        timeout.setSingleShot(True);timeout.timeout.connect(loop.quit)
        poll.start(10);timeout.start(timeout_ms);loop.exec();poll.stop();timeout.stop()
    def wait_finished(self):
        self.pump_until_idle(10000)
        worker=self.window.runner.thread
        frame=sys._current_frames().get(worker.ident) if worker else None
        detail=''.join(traceback.format_stack(frame)) if frame else 'No worker frame'
        self.assertFalse(self.window.working,self.window.status.text()+'\n'+detail)
    def test_file_folder_and_destination_dialog_wiring(self):
        with patch('mandarin.qt_ui.QFileDialog.getOpenFileNames',return_value=([str(self.source)],'')):self.window.choose_files()
        self.assertEqual(self.window.selected_paths(),[str(self.source)])
        with patch('mandarin.qt_ui.QFileDialog.getExistingDirectory',return_value=str(self.root)):
            self.window.choose_folder();self.window.choose_output()
        self.assertIn(str(self.root),self.window.paths);self.assertEqual(self.window.output_folder,str(self.root))
        self.window.reset_output();self.assertIsNone(self.window.output_folder)
    def test_synthetic_local_drop_and_remote_rejection(self):
        self.window.wheel_on_drop.setChecked(False);mime=QMimeData();mime.setUrls([QUrl.fromLocalFile(str(self.source)),QUrl('https://example.com/file.png')])
        self.assertEqual(local_drop_paths(mime),[str(self.source)])
        enter=QDragEnterEvent(QPoint(30,30),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(self.window,enter);self.assertTrue(enter.isAccepted())
        drop=QDropEvent(QPointF(30,30),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(self.window,drop);self.assertTrue(drop.isAccepted());self.assertIn(str(self.source),self.window.paths)
    def test_radial_keyboard_and_mouse_selection(self):
        ops=[{'id':str(i),'label':str(i)} for i in range(4)];picked=[]
        wheel=RadialMenu(self.window,ops);wheel.selected.connect(picked.append);wheel.show();QTest.keyClick(wheel,Qt.Key.Key_Right);QTest.keyClick(wheel,Qt.Key.Key_Return)
        self.assertEqual(picked[-1]['id'],'0')
        wheel=RadialMenu(self.window,ops);wheel.selected.connect(picked.append);wheel.show();QTest.mouseClick(wheel,Qt.MouseButton.LeftButton,pos=QPoint(220,80));self.assertEqual(picked[-1]['id'],'0')
    def test_options_reject_invalid_numeric(self):
        dialog=OptionsDialog(self.window,{'label':'Resize','params':[{'key':'width','label':'Width','type':'int','default':10}]})
        dialog.fields['width'][0].setText('invalid');dialog.validate();self.assertTrue(dialog.error.text())
        dialog.fields['width'][0].setText('12');dialog.validate();self.assertEqual(dialog.values,{'width':12});dialog.close()
    def test_real_batch_progress_history_and_corrupt_input(self):
        corrupt=self.root/'broken.png';corrupt.write_bytes(b'broken');self.window.add_paths([str(self.source),str(corrupt)])
        self.window.run_operation({'id':'image:jpeg','label':'JPEG'},options={});self.wait_finished()
        self.assertEqual(len(self.window.history),1);self.assertEqual(self.window.history_list.count(),1);self.assertIn('Stopped:',self.window.status.text());self.assertTrue(Path(self.window.history[0]).is_file())
    def test_background_cancellation_keeps_event_loop_alive(self):
        self.window.add_paths([str(self.source)]);ticks=[];started=threading.Event()
        def slow(operation,paths,options,progress,cancelled):
            started.set()
            while not cancelled.wait(.02):pass
            raise engine.Cancelled('Operation cancelled.')
        with patch('mandarin.jobs.engine.run_operation',side_effect=slow):
            self.window.run_operation({'id':'image:jpeg','label':'JPEG'},options={})
            QTimer.singleShot(30,lambda:ticks.append(True));QTimer.singleShot(80,self.window.cancel);self.wait_finished()
        self.assertTrue(started.is_set());self.assertTrue(ticks);self.assertIn('cancelled',self.window.status.text())

if __name__=='__main__':unittest.main()

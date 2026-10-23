"""Capture only our own Qt window with generated files; no personal data."""
from pathlib import Path
import tempfile
from PIL import Image
from PySide6.QtCore import QTimer
from mandarin.qt_ui import QApplication,MainWindow,RadialMenu,STYLE
from mandarin import engine

app=QApplication([]);app.setStyleSheet(STYLE)
with tempfile.TemporaryDirectory(prefix='mandarin-preview-') as temp:
    folder=Path(temp)
    for name,color in [('Studio cover.png','#e7985c'),('Product detail.png','#7c9572')]:Image.new('RGB',(640,400),color).save(folder/name)
    window=MainWindow();window.add_paths([str(p) for p in folder.glob('*.png')]);window.show()
    dest=Path(__file__).resolve().parents[1]/'docs/screenshots';dest.mkdir(parents=True,exist_ok=True)
    def capture():
        window.grab().save(str(dest/'qt-linux.png'))
        wheel=RadialMenu(window,[o for o in engine.get_operations(window.paths) if o['available']]);wheel.hover=0;wheel.show();app.processEvents();wheel.grab().save(str(dest/'qt-wheel-linux.png'));wheel.close();window.close();app.quit()
    QTimer.singleShot(450,capture);app.exec()

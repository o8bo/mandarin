"""Windows frontend. May also run on Linux for toolkit integration tests.

Explorer files are accepted through Qt's native OLE drop handling. The wheel
is in-app after drop/selection; there are no global hooks or registry edits.
"""
from __future__ import annotations
import math
import os
from pathlib import Path
import sys
from PySide6.QtCore import Qt, Signal, QObject, QUrl, QPoint, QTimer
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPainterPath, QPen, QFont, QCursor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QFileDialog, QListWidget, QListWidgetItem, QAbstractItemView,
    QScrollArea, QGridLayout, QFrame, QProgressBar, QMessageBox, QDialog,
    QDialogButtonBox, QFormLayout, QLineEdit, QComboBox, QCheckBox)
from . import engine
from .jobs import JobRunner
from .platform_support import resource_root, discover_tool, save_tool, TOOLS
from .radial_geometry import sector_at

STYLE = '''
QMainWindow, QDialog {background:#f8f6ef;color:#24372d;}
QWidget {font-family:Segoe UI,DejaVu Sans;font-size:13px;color:#24372d;}
QLabel#brand {color:#ffa35d;font-weight:bold;font-size:19px;}
QFrame#sidebar {background:#27392f;border-radius:14px;}
QFrame#sidebar QLabel {color:#e5eadf;}
QLabel#heading {font-size:27px;font-weight:bold;}
QLabel#muted {color:#728076;}
QFrame#drop {background:#efeee4;border:2px dashed #c4ccba;border-radius:13px;}
QPushButton {background:white;border:1px solid #dce0d4;border-radius:8px;padding:10px 14px;text-align:left;}
QPushButton:hover {background:#edf2e7;border-color:#98aa8c;}
QPushButton:disabled {color:#a1a89d;background:#edece6;}
QPushButton#primary {background:#d76a2c;color:white;border-color:#d76a2c;font-weight:bold;}
QPushButton#nav {background:transparent;color:#e8ecdf;border:0;}
QPushButton#nav:checked {background:#405742;color:#ffbc84;}
QListWidget {background:white;border:1px solid #e2e4da;border-radius:10px;padding:5px;}
QListWidget::item {padding:8px;border-radius:6px;}
QListWidget::item:selected {background:#e4edd9;color:#234a31;}
QLineEdit,QComboBox {background:white;border:1px solid #d7ddcf;border-radius:6px;padding:8px;}
QScrollArea {border:0;background:transparent;}
QWidget#operations {background:#f8f6ef;}
QProgressBar {border:0;border-radius:5px;background:#e4e9dc;min-height:20px;text-align:center;}
QProgressBar::chunk {background:#8da56d;border-radius:5px;}
'''


def local_drop_paths(mime):
    paths = []
    if mime.hasUrls():
        for url in mime.urls():
            if url.isLocalFile():
                p = Path(url.toLocalFile())
                if (p.is_file() or p.is_dir()) and str(p) not in paths:
                    paths.append(str(p.absolute()))
    return paths


class Bridge(QObject):
    progress = Signal(int, int, str)
    finished = Signal(dict, str)


class RadialMenu(QDialog):
    selected = Signal(dict)
    SIZE = 440

    def __init__(self, parent, operations):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.operations = operations[:7] + ([{'id': 'ui:more', 'label': 'More…'}] if len(operations) > 7 else [])
        self.hover = -1
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setAccessibleName('Mandarin radial conversion menu')

    def show_at_cursor(self):
        cursor = QCursor.pos(); screen = QApplication.screenAt(cursor) or QApplication.primaryScreen()
        bounds = screen.availableGeometry()
        x = max(bounds.left(), min(cursor.x()-self.SIZE//2, bounds.right()-self.SIZE+1))
        y = max(bounds.top(), min(cursor.y()-self.SIZE//2, bounds.bottom()-self.SIZE+1))
        self.move(x,y); self.show(); self.setFocus()

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self.SIZE/2
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor('#25362c')); p.drawEllipse(8,8,self.SIZE-16,self.SIZE-16)
        count = len(self.operations)
        for i, op in enumerate(self.operations):
            step = 360/count; start = 90 - i*step - step/2 + 1
            path = QPainterPath(); path.arcMoveTo(17,17,self.SIZE-34,self.SIZE-34,start)
            path.arcTo(17,17,self.SIZE-34,self.SIZE-34,start,step-2)
            end = math.radians(start+step-2)
            path.lineTo(c+72*math.cos(end),c-72*math.sin(end))
            path.arcTo(c-72,c-72,144,144,start+step-2,-(step-2)); path.closeSubpath()
            p.setBrush(QColor('#e57838' if self.hover==i else '#3c5041')); p.drawPath(path)
            angle = -math.pi/2+i*math.tau/count
            x,y = c+143*math.cos(angle),c+143*math.sin(angle)
            p.setPen(QColor('#fff8e9')); p.setFont(QFont('Segoe UI',10,QFont.Weight.Bold))
            p.drawText(int(x-60),int(y-32),120,64,Qt.AlignmentFlag.AlignCenter|Qt.TextFlag.TextWordWrap,op['label'])
            p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#f59250')); p.drawEllipse(int(c-61),int(c-61),122,122)
        p.setPen(QColor('#263b2b')); p.setFont(QFont('Segoe UI',11,QFont.Weight.Bold))
        p.drawText(int(c-60),int(c-30),120,60,Qt.AlignmentFlag.AlignCenter,'CHOOSE\nA FORMAT' if count else 'NO FORMATS\nAVAILABLE')
        p.end()

    def mouseMoveEvent(self,event):
        self.hover = sector_at(event.position().x(),event.position().y(),len(self.operations),self.SIZE); self.update()

    def choose(self,index):
        if 0<=index<len(self.operations):
            self.selected.emit(self.operations[index]); self.accept()

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.choose(sector_at(event.position().x(),event.position().y(),len(self.operations),self.SIZE))

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape: self.reject()
        elif event.key() in (Qt.Key.Key_Left,Qt.Key.Key_Up,Qt.Key.Key_Right,Qt.Key.Key_Down) and self.operations:
            delta = -1 if event.key() in (Qt.Key.Key_Left,Qt.Key.Key_Up) else 1
            self.hover = (self.hover+delta)%len(self.operations); self.update()
        elif event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter): self.choose(max(0,self.hover))
        else: super().keyPressEvent(event)


class OptionsDialog(QDialog):
    def __init__(self,parent,operation):
        super().__init__(parent); self.setWindowTitle(operation['label']); self.fields = {}
        layout = QVBoxLayout(self); form=QFormLayout();layout.addLayout(form)
        for spec in operation.get('params',[]):
            if spec['type']=='choice':
                field=QComboBox();field.addItems([str(x) for x in spec['choices']]);field.setCurrentText(str(spec.get('default','')))
            else: field=QLineEdit(str(spec.get('default','')))
            self.fields[spec['key']] = (field,spec);form.addRow(spec['label'],field)
        self.error=QLabel();self.error.setStyleSheet('color:#ab3d2f');layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);layout.addWidget(buttons)

    def validate(self):
        try:
            self.values={}
            for key,(field,spec) in self.fields.items():
                raw=field.currentText() if isinstance(field,QComboBox) else field.text().strip()
                self.values[key]=int(raw) if spec['type']=='int' else float(raw) if spec['type']=='float' else raw
            self.accept()
        except ValueError: self.error.setText('Enter a valid number in each numeric field.')


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Mandarin — local file conversion');self.resize(1160,820);self.setMinimumSize(900,680)
        self.setWindowIcon(QIcon(str(resource_root()/'assets/mandarin.svg')))
        self.setAcceptDrops(True); self.paths=[];self.mode='convert';self.output_folder=None;self.working=False;self.history=[];self.wheel=None
        self.runner=JobRunner();self.bridge=Bridge();self.bridge.progress.connect(self.on_progress);self.bridge.finished.connect(self.on_finished)
        root=QWidget();self.setCentralWidget(root);layout=QHBoxLayout(root);layout.setContentsMargins(16,16,16,16);layout.setSpacing(24)
        sidebar=QFrame();sidebar.setObjectName('sidebar');sidebar.setFixedWidth(210);side=QVBoxLayout(sidebar);side.setContentsMargins(20,26,20,20)
        brand=QLabel('●  MANDARIN');brand.setObjectName('brand');side.addWidget(brand)
        side.addWidget(QLabel('Your files.\nA simpler workflow.'));side.addSpacing(30);self.nav=[]
        for mode,title in [('convert','Convert'),('tools','Tools'),('actions','File actions')]:
            b=QPushButton(title);b.setObjectName('nav');b.setCheckable(True);b.clicked.connect(lambda _,m=mode:self.set_mode(m));side.addWidget(b);self.nav.append((mode,b))
        side.addStretch();side.addWidget(QLabel('LOCAL BY DESIGN\nNo account. No uploads.'))
        status_button=QPushButton('Engines & settings');status_button.clicked.connect(self.settings);side.addWidget(status_button);layout.addWidget(sidebar)
        content=QVBoxLayout();content.setSpacing(13);layout.addLayout(content,1)
        top=QHBoxLayout();heading=QLabel('Make room for the next thing.');heading.setObjectName('heading');top.addWidget(heading,1)
        add=QPushButton('+ Add files');add.setObjectName('primary');add.clicked.connect(self.choose_files);top.addWidget(add)
        folder=QPushButton('Add folder');folder.clicked.connect(self.choose_folder);top.addWidget(folder);content.addLayout(top)
        caption=QLabel('Convert, tidy up and move on. Everything stays on this computer.');caption.setObjectName('muted');content.addWidget(caption)
        drop=QFrame();drop.setObjectName('drop');box=QVBoxLayout(drop);box.addWidget(QLabel('↓  Drop files or folders from File Explorer here'))
        note=QLabel('Choose a format from the in-app wheel, or use the operation list below.');note.setObjectName('muted');note.setWordWrap(True);box.addWidget(note);content.addWidget(drop)
        filebar=QHBoxLayout();self.file_count=QLabel('YOUR FILES');filebar.addWidget(self.file_count,1)
        self.wheel_button=QPushButton('Open radial menu');self.wheel_button.clicked.connect(lambda:self.open_wheel());filebar.addWidget(self.wheel_button)
        clear=QPushButton('Clear');clear.clicked.connect(self.clear_files);filebar.addWidget(clear);content.addLayout(filebar)
        self.files=QListWidget();self.files.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);self.files.setMaximumHeight(145);self.files.itemSelectionChanged.connect(self.render_operations);content.addWidget(self.files)
        destinations=QHBoxLayout();self.destination=QLabel('Output: next to each original');destinations.addWidget(self.destination,1)
        choose=QPushButton('Change output');choose.clicked.connect(self.choose_output);destinations.addWidget(choose)
        reset=QPushButton('Reset');reset.clicked.connect(self.reset_output);destinations.addWidget(reset);content.addLayout(destinations)
        self.wheel_on_drop=QCheckBox('Open radial menu after dropping files');self.wheel_on_drop.setChecked(True);content.addWidget(self.wheel_on_drop)
        self.operation_area=QScrollArea();self.operation_area.setWidgetResizable(True);content.addWidget(self.operation_area,1)
        progress=QHBoxLayout();self.progress=QProgressBar();self.progress.setRange(0,100);progress.addWidget(self.progress,1)
        self.cancel_button=QPushButton('Cancel');self.cancel_button.clicked.connect(self.cancel);self.cancel_button.setEnabled(False);progress.addWidget(self.cancel_button);content.addLayout(progress)
        content.addWidget(QLabel('RECENT OUTPUTS — double-click to open the folder'))
        self.history_list=QListWidget();self.history_list.setMaximumHeight(100);self.history_list.itemDoubleClicked.connect(lambda item:self.reveal(item.data(Qt.ItemDataRole.UserRole)));content.addWidget(self.history_list)
        self.status=QLabel('Ready when you are.');self.status.setWordWrap(True);content.addWidget(self.status)
        self.set_mode('convert')

    def selected_paths(self):
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.files.selectedItems()] or list(self.paths)

    def add_paths(self,paths,select_added=False):
        accepted=[]
        self.files.blockSignals(True)
        if select_added: self.files.clearSelection()
        for raw in paths:
            p=Path(raw).expanduser().absolute()
            if not(p.is_file() or p.is_dir()):continue
            value=str(p);accepted.append(value)
            if value not in self.paths:
                self.paths.append(value);item=QListWidgetItem(p.name+'  ·  '+engine.detect(p));item.setData(Qt.ItemDataRole.UserRole,value);item.setToolTip(value);self.files.addItem(item)
            if select_added:
                for i in range(self.files.count()):
                    item=self.files.item(i)
                    if item.data(Qt.ItemDataRole.UserRole)==value:item.setSelected(True)
        self.files.blockSignals(False);self.file_count.setText(f'YOUR FILES · {len(self.paths)}');self.render_operations()
        return accepted

    def choose_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Select files');self.add_paths(paths,True)

    def choose_folder(self):
        folder=QFileDialog.getExistingDirectory(self,'Select a folder')
        if folder:self.add_paths([folder],True)

    def clear_files(self):
        self.paths=[];self.files.clear();self.file_count.setText('YOUR FILES');self.render_operations()

    def choose_output(self):
        folder=QFileDialog.getExistingDirectory(self,'Output folder')
        if folder:self.output_folder=folder;self.destination.setText('Output: '+folder)

    def reset_output(self):
        self.output_folder=None;self.destination.setText('Output: next to each original')

    def set_mode(self,mode):
        self.mode=mode
        for key,b in self.nav:b.setChecked(key==mode)
        self.render_operations()

    def render_operations(self):
        if not hasattr(self,'operation_area'):return
        container=QWidget();container.setObjectName('operations');grid=QGridLayout(container);grid.setContentsMargins(0,0,4,4);grid.setSpacing(10)
        paths=self.selected_paths();self.wheel_button.setEnabled(bool(paths) and not self.working)
        if self.mode=='actions':
            ops=[{'id':'ui:paths','label':'Copy file paths'},{'id':'ui:reveal','label':'Open containing folder'},{'id':'ui:open','label':'Open in default application'}] if paths else []
        else:ops=[op for op in engine.get_operations(paths,self.mode) if op['available']]
        for i,op in enumerate(ops):
            b=QPushButton(op['label']+'  →');b.setMinimumHeight(56);b.setToolTip(op.get('detail',''));b.setEnabled(not self.working);b.clicked.connect(lambda _,o=op:self.run_operation(o));grid.addWidget(b,i//2,i%2)
        if not ops:
            message='Drop files to see compatible operations.' if not paths else 'No available operations. Check Engines & settings for missing tools.'
            empty=QLabel(message);empty.setWordWrap(True);grid.addWidget(empty,0,0,1,2)
        grid.setRowStretch((len(ops)+1)//2+1,1)
        previous=self.operation_area.takeWidget();self.operation_area.setWidget(container)
        if previous:previous.deleteLater()

    def dragEnterEvent(self,event):
        if local_drop_paths(event.mimeData()):event.acceptProposedAction()
        else:event.ignore()

    def dragMoveEvent(self,event):
        if local_drop_paths(event.mimeData()):event.acceptProposedAction()
        else:event.ignore()

    def dropEvent(self,event):
        paths=self.add_paths(local_drop_paths(event.mimeData()),True)
        if paths:
            event.acceptProposedAction()
            if self.wheel_on_drop.isChecked() and not self.working:QTimer.singleShot(0,lambda:self.open_wheel(paths))
        else:event.ignore()

    def open_wheel(self,paths=None):
        paths=list(paths or self.selected_paths())
        if not paths or self.working:return
        mode=self.mode if self.mode!='actions' else 'convert'
        operations=[o for o in engine.get_operations(paths,mode) if o['available']]
        if not operations:
            self.status.setText('No radial actions for this selection. Choose Tools or configure an engine.');return
        self.wheel=RadialMenu(self,operations);self.wheel.selected.connect(lambda op:self.run_operation(op,paths));self.wheel.show_at_cursor()

    def run_operation(self,op,paths=None,options=None):
        paths=list(paths or self.selected_paths())
        if self.working or not paths:return
        if op['id']=='ui:more':self.status.setText('Choose from the full operation list.');return
        if op['id'].startswith('ui:'):
            if op['id']=='ui:paths':QApplication.clipboard().setText('\n'.join(paths))
            elif op['id']=='ui:reveal':self.reveal(paths[0])
            elif op['id']=='ui:open':QDesktopServices.openUrl(QUrl.fromLocalFile(paths[0]))
            return
        if options is None and op.get('params'):
            dialog=OptionsDialog(self,op)
            if dialog.exec()!=QDialog.DialogCode.Accepted:return
            options=dialog.values
        options=dict(options or {})
        if self.output_folder:options['output_dir']=self.output_folder
        self.working=True;self.cancel_button.setEnabled(True);self.progress.setValue(0);self.status.setText('Starting '+op['label']+'…');self.render_operations()
        try:self.runner.start(op['id'],paths,options,self.bridge.progress.emit,self.bridge.finished.emit)
        except Exception as error:self.on_finished({'outputs':[],'warnings':[]},str(error))

    def on_progress(self,completed,total,message):
        self.progress.setValue(int(100*completed/total) if total else 0);self.status.setText(message)

    def cancel(self):
        self.runner.cancel();self.status.setText('Cancelling; completed outputs will be kept…')

    def on_finished(self,result,error):
        # Thread signal may arrive just before Thread.is_alive becomes false.
        if self.runner.busy:
            QTimer.singleShot(15,lambda:self.on_finished(result,error));return
        self.working=False;self.cancel_button.setEnabled(False);self.render_operations()
        for path in result.get('outputs',[]):
            self.history.append(path);item=QListWidgetItem(Path(path).name+'  →');item.setData(Qt.ItemDataRole.UserRole,path);item.setToolTip(path);self.history_list.insertItem(0,item)
        count=len(result.get('outputs',[]));self.progress.setValue(100 if not error else self.progress.value())
        message=f'{count} completed output(s).'+(' Stopped: '+error if error else '')
        if result.get('warnings'):message+=' '+ '; '.join(result['warnings'])
        self.status.setText(message)

    def reveal(self,path):
        if path:QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path) if Path(path).is_dir() else Path(path).parent)))

    def settings(self):
        dialog=QDialog(self);dialog.setWindowTitle('Conversion engines');dialog.resize(620,430);layout=QVBoxLayout(dialog)
        note=QLabel('Images, subtitles and archives work locally. Optional engines enable media, documents and PDF rasterization. Choose trusted executables; Mandarin does not download engines.');note.setWordWrap(True);layout.addWidget(note)
        for name in TOOLS:
            row=QHBoxLayout();row.addWidget(QLabel(name));path=QLabel(discover_tool(name) or 'Not found');path.setWordWrap(True);row.addWidget(path,1)
            choose=QPushButton('Locate…')
            def locate(_,name=name,view=path):
                value,_=QFileDialog.getOpenFileName(dialog,'Locate '+name)
                if value:
                    try:save_tool(name,value);view.setText(value)
                    except (ValueError,OSError) as error:QMessageBox.warning(dialog,'Engine path',str(error))
            choose.clicked.connect(locate);row.addWidget(choose);layout.addLayout(row)
            reset=QPushButton('Reset')
            def reset_path(_,name=name,view=path):
                try:save_tool(name,None);view.setText(discover_tool(name) or 'Not found')
                except OSError as error:QMessageBox.warning(dialog,'Engine path',str(error))
            reset.clicked.connect(reset_path);row.addWidget(reset)
        limitations=QLabel('Windows wheel: in-app after drop or selection. Explorer-wide hotkeys and registry context menus are not installed.');limitations.setWordWrap(True);layout.addWidget(limitations)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons);dialog.exec();self.render_operations()

    def closeEvent(self,event):
        if self.working:
            self.cancel();self.status.setText('Wait for cancellation to finish, then close Mandarin.');event.ignore()
        else:event.accept()


def main(paths=None):
    app=QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName('Mandarin');app.setStyleSheet(STYLE)
    window=MainWindow();window.add_paths(paths or []);window.show()
    return app.exec()

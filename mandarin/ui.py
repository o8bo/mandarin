"""Native, local-first Mandarin desktop interface (GTK 3)."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import threading
import tempfile
from urllib.parse import unquote, urlsplit

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gio, GLib, Gtk, Pango

from . import engine


def local_uri_path(uri):
    """Only accept unambiguous local file URIs, never remote locations."""
    parts = urlsplit(uri)
    if parts.scheme != 'file' or parts.netloc not in ('', 'localhost') or parts.query or parts.fragment:
        return None
    path = unquote(parts.path)
    if '\x00' in path or not os.path.isabs(path):
        return None
    return path


def button(label, callback, style=None):
    item = Gtk.Button(label=label)
    if style:
        item.get_style_context().add_class(style)
    item.connect('clicked', callback)
    return item


def label(text, style=None, wrap=False):
    item = Gtk.Label(label=text, xalign=0)
    if style:
        item.get_style_context().add_class(style)
    item.set_line_wrap(wrap)
    return item


def safe_destination(folder, source):
    path = Path(source)
    destination = Path(folder) / path.name
    index = 2
    while destination.exists():
        destination = Path(folder) / f'{path.stem} ({index}){path.suffix}'
        index += 1
    return destination


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title='Mandarin')
        self.app = app
        self.set_default_size(1120, 760)
        self.set_size_request(840, 580)
        self.paths = []
        self.mode = 'convert'
        self.busy = False
        self.cancel_event = threading.Event()
        self.history = []
        self.tray = None
        self.output_folder = None
        self.clipboard_owner = Gtk.Invisible()
        self.clipboard_owner.connect('selection-get', self._selection_get)
        self.file_clipboard = []
        self._load_style()
        self._build()
        self._setup_tray()
        self.connect('delete-event', self._close)
        self._refresh()
        self.show_all()
        self.progress_box.hide()
        self.clear_button.hide()

    def _load_style(self):
        css = Path(__file__).resolve().parent.parent / 'assets' / 'style.css'
        provider = Gtk.CssProvider()
        if css.exists():
            provider.load_from_path(str(css))
            Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _build(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(root)
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title('Mandarin')
        header.set_subtitle('A little less busywork.')
        self.set_titlebar(header)
        header.pack_end(button('Settings', lambda _: self._settings()))
        layout = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        root.pack_start(layout, True, True, 0)
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        sidebar.set_size_request(230, -1)
        sidebar.get_style_context().add_class('sidebar')
        layout.pack_start(sidebar, False, False, 0)
        sidebar.pack_start(label('●  MANDARIN', 'brand'), False, False, 4)
        sidebar.pack_start(label('Your files.\nA simpler workflow.', 'sidebar-title', True), False, False, 12)
        sidebar.pack_start(label('WORKSPACE', 'eyebrow'), False, False, 10)
        for mode, title in [('convert', '↗   Convert'), ('tools', '⌘   Tools'), ('actions', '▤   Actions')]:
            control = button(title, lambda _, m=mode: self._set_mode(m), 'nav')
            setattr(self, 'nav_' + mode, control)
            sidebar.pack_start(control, False, False, 0)
        sidebar.pack_start(Gtk.Box(), True, True, 0)
        sidebar.pack_start(label('LOCAL BY DESIGN', 'eyebrow'), False, False, 0)
        sidebar.pack_start(label('Files stay on your computer.\nNo account. No uploads.', 'privacy', True), False, False, 0)
        sidebar.pack_start(button('Engine status  →', lambda _: self._settings(), 'nav'), False, False, 8)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_border_width(28)
        layout.pack_start(content, True, True, 0)
        title_row = Gtk.Box(spacing=12)
        self.heading = label('Make room for the next thing.', 'heading')
        title_row.pack_start(self.heading, True, True, 0)
        title_row.pack_end(button('+  Add files', lambda _: self._choose_files(), 'primary'), False, False, 0)
        title_row.pack_end(button('Add folder', lambda _: self._choose_folder()), False, False, 0)
        content.pack_start(title_row, False, False, 0)
        self.subtitle = label('Convert, tidy up and move on. All on your Linux desktop.', 'muted', True)
        content.pack_start(self.subtitle, False, False, 0)
        self.drop = Gtk.EventBox()
        self.drop.get_style_context().add_class('dropzone')
        drop_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        drop_content.set_border_width(20)
        drop_content.pack_start(label('↓   Drop something here', 'drop-title'), False, False, 0)
        drop_content.pack_start(label('Images, videos, audio, PDFs, documents and archives', 'muted', True), False, False, 0)
        self.drop.add(drop_content)
        self.drop.drag_dest_set(Gtk.DestDefaults.ALL, [Gtk.TargetEntry.new('text/uri-list', 0, 0)], Gdk.DragAction.COPY)
        self.drop.connect('drag-data-received', self._drop_files)
        content.pack_start(self.drop, False, False, 0)
        files_header = Gtk.Box()
        self.files_heading = label('YOUR FILES', 'eyebrow')
        files_header.pack_start(self.files_heading, True, True, 0)
        self.clear_button = button('Clear', lambda _: self._clear(), 'flat')
        files_header.pack_end(self.clear_button, False, False, 0)
        content.pack_start(files_header, False, False, 0)
        self.files_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.MULTIPLE)
        self.files_list.connect('selected-rows-changed', lambda _: self._render_operations())
        self.files_scroll = Gtk.ScrolledWindow()
        self.files_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.files_scroll.set_min_content_height(76)
        self.files_scroll.set_max_content_height(150)
        self.files_scroll.set_propagate_natural_height(True)
        self.files_scroll.add(self.files_list)
        content.pack_start(self.files_scroll, False, False, 0)
        self.operations_heading = label('WHAT WOULD YOU LIKE TO DO?', 'eyebrow')
        content.pack_start(self.operations_heading, False, False, 0)
        operation_scroll = Gtk.ScrolledWindow()
        self.operation_scroll = operation_scroll
        operation_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.operation_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        operation_scroll.add(self.operation_box)
        content.pack_start(operation_scroll, True, True, 0)
        self.progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.progress_label = label('Working…', 'muted')
        self.progress_bar = Gtk.ProgressBar(show_text=True)
        progress_row = Gtk.Box(spacing=10)
        progress_row.pack_start(self.progress_bar, True, True, 0)
        progress_row.pack_end(button('Cancel', lambda _: self.cancel_event.set()), False, False, 0)
        self.progress_box.pack_start(self.progress_label, False, False, 0)
        self.progress_box.pack_start(progress_row, False, False, 0)
        content.pack_start(self.progress_box, False, False, 0)
        self.history_expander = Gtk.Expander(label='Recent activity')
        self.history_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.history_expander.add(self.history_box)
        content.pack_start(self.history_expander, False, False, 0)
        self.status = label('Ready when you are.', 'muted')
        content.pack_start(self.status, False, False, 0)

    def _set_mode(self, mode):
        self.mode = mode
        titles = {'convert': 'Make room for the next thing.', 'tools': 'The finishing touches.', 'actions': 'Everything in its place.'}
        self.heading.set_text(titles[mode])
        self._render_operations()

    def _chosen_paths(self):
        rows = self.files_list.get_selected_rows()
        return [row.path for row in rows if hasattr(row, 'path')] if rows else list(self.paths)

    def add_paths(self, paths):
        added = 0
        for raw in paths:
            path = os.path.abspath(os.path.expanduser(os.fspath(raw)))
            if os.path.exists(path) and (os.path.isfile(path) or os.path.isdir(path)) and path not in self.paths:
                self.paths.append(path)
                added += 1
        self._refresh()
        if not added:
            self.status.set_text('No new readable files were added. Choose local files or folders to get started.')

    def _refresh(self):
        for child in self.files_list.get_children():
            self.files_list.remove(child)
        for path in self.paths:
            row = Gtk.ListBoxRow()
            row.path = path
            box = Gtk.Box(spacing=12)
            box.set_border_width(9)
            name = label('\u200e' + Path(path).name)
            name.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            name.set_tooltip_text(path)
            box.pack_start(name, True, True, 0)
            try:
                kind = engine.detect(path)
            except Exception:
                kind = 'file'
            box.pack_start(label(str(kind).upper(), 'file-kind'), False, False, 0)
            box.pack_end(button('×', lambda _, p=path: self._remove_path(p), 'flat'), False, False, 0)
            row.add(box)
            self.files_list.add(row)
        if not self.paths:
            placeholder = label('Nothing queued yet — add a file above.', 'muted')
            placeholder.set_margin_top(16)
            placeholder.set_margin_bottom(16)
            row = Gtk.ListBoxRow(selectable=False, activatable=False)
            row.add(placeholder)
            self.files_list.add(row)
        self.files_list.show_all()
        self.clear_button.set_visible(bool(self.paths))
        self.files_heading.set_text(f'YOUR FILES  ·  {len(self.paths)}' if self.paths else 'YOUR FILES')
        self._render_operations()

    def _remove_path(self, path):
        if path in self.paths:
            self.paths.remove(path)
        self._refresh()

    def _clear(self):
        self.paths.clear()
        self._refresh()

    def _render_operations(self):
        for mode in ('convert', 'tools', 'actions'):
            context = getattr(self, 'nav_' + mode).get_style_context()
            (context.add_class if mode == self.mode else context.remove_class)('active')
        for child in self.operation_box.get_children():
            self.operation_box.remove(child)
        paths = self._chosen_paths()
        if not paths:
            empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            empty.set_border_width(24)
            empty.pack_start(label('Good things start with a file.', 'empty-title'), False, False, 0)
            empty.pack_start(label('Add one or a few. Mandarin will show the operations that fit.', 'muted', True), False, False, 0)
            self.operation_box.pack_start(empty, False, False, 0)
        elif self.mode == 'actions':
            actions = [('Copy files', 'Place files on the clipboard for your file manager.', self._copy_files), ('Copy paths', 'Copy full local paths as text.', self._copy_paths), ('Copy to folder', 'Keep the originals and create copies in another folder.', lambda: self._transfer(False)), ('Move to folder', 'Move selected originals to a folder you choose.', lambda: self._transfer(True)), ('Show in folder', 'Open the file location in your file manager.', self._reveal_selected), ('Open terminal here', 'Start a terminal in the first selected file’s folder.', self._terminal), ('Quick preview', 'A floating preview for images and text files.', self._preview)]
            for title, detail, callback in actions:
                self._card(title, detail, lambda _, fn=callback: fn(), not self.busy)
        else:
            try:
                operations = engine.get_operations(paths, mode=self.mode)
                for operation in operations:
                    available = operation.get('available', True)
                    self._card(operation['label'], operation.get('detail', '') if available else operation.get('reason', 'Required engine unavailable'), lambda _, op=operation: self.run_selected_operation(op), available and not self.busy)
                if not operations:
                    self.operation_box.pack_start(label('No matching operations for this selection. Try selecting files of the same type.', 'muted', True), False, False, 10)
            except Exception as error:
                self.operation_box.pack_start(label(f'Could not load operations: {error}', 'muted', True), False, False, 10)
        self.operation_box.show_all()
        GLib.idle_add(self._reset_operation_scroll)

    def _reset_operation_scroll(self):
        adjustment = self.operation_scroll.get_vadjustment()
        adjustment.set_value(adjustment.get_lower())
        return False

    def _card(self, title, detail, callback, sensitive=True):
        card = Gtk.Button()
        card.get_style_context().add_class('operation')
        card.set_sensitive(sensitive)
        row = Gtk.Box(spacing=16)
        row.set_border_width(13)
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        texts.pack_start(label(title, 'card-title'), False, False, 0)
        texts.pack_start(label(detail, 'muted', True), False, False, 0)
        row.pack_start(texts, True, True, 0)
        row.pack_end(label('→', 'arrow'), False, False, 0)
        card.add(row)
        card.connect('clicked', callback)
        self.operation_box.pack_start(card, False, False, 0)

    def activate_wheel_action(self, action, paths):
        self.add_paths(paths)
        # Restrict action dialogs to the files from this particular drag.
        self.files_list.unselect_all()
        selected = set(paths)
        for row in self.files_list.get_children():
            if getattr(row, 'path', None) in selected:
                self.files_list.select_row(row)
        if not self.files_list.get_selected_rows():
            self.status.set_text('No supported local files or folders were received from this drag.')
            return
        self.present()
        if action == 'copy_to':
            self._transfer(False)
        elif action == 'move_to':
            self._transfer(True)
        elif action == 'preview':
            self._preview()
        elif action == 'copy_files':
            self._copy_files()
        elif action == 'more':
            wheel = getattr(self.app, 'wheel', None)
            self._set_mode(getattr(wheel, 'mode', 'actions'))

    def _choose_folder(self):
        folder = self._folder('Add local folder')
        if folder:
            self.add_paths([folder])

    def _choose_files(self):
        dialog = Gtk.FileChooserDialog(title='Add local files', transient_for=self, action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons('Cancel', Gtk.ResponseType.CANCEL, 'Add files', Gtk.ResponseType.OK)
        dialog.set_select_multiple(True)
        dialog.set_local_only(True)
        if dialog.run() == Gtk.ResponseType.OK:
            self.add_paths(dialog.get_filenames())
        dialog.destroy()

    def _drop_files(self, widget, context, x, y, data, info, timestamp):
        paths = [local_uri_path(uri) for uri in data.get_uris() or []]
        accepted = [path for path in paths if path]
        self.add_paths(accepted)
        Gtk.drag_finish(context, bool(accepted), False, timestamp)

    def run_selected_operation(self, op, paths=None):
        if self.busy:
            self.status.set_text('An operation is already running.')
            return
        paths = list(paths or self._chosen_paths())
        if not paths:
            return
        if isinstance(op, str):
            available = engine.get_operations(paths, mode='convert') + engine.get_operations(paths, mode='tools')
            op = next((item for item in available if item['id'] == op), None)
            if op is None:
                self._error('This operation is not available for the selected files.')
                return
        if not op.get('available', True):
            self._error(op.get('reason', 'Required engine unavailable.'))
            return
        options = self._parameters(op, len(paths))
        if options is None:
            return
        if self.output_folder:
            options.setdefault('output_dir', self.output_folder)
        self._start_worker(op['label'], lambda: engine.run_operation(op['id'], paths, options=options, progress=self._worker_progress, cancelled=self.cancel_event))

    def _parameters(self, operation, count):
        dialog = Gtk.Dialog(title=operation['label'], transient_for=self, modal=True)
        dialog.add_buttons('Cancel', Gtk.ResponseType.CANCEL, 'Run operation', Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.set_default_size(470, -1)
        box = dialog.get_content_area()
        box.set_border_width(22)
        box.set_spacing(14)
        box.pack_start(label(f'{count} file' + ('s' if count != 1 else '') + ' · Original files are preserved by conversion tools.', 'muted', True), False, False, 0)
        fields = {}
        for parameter in operation.get('params', []):
            box.pack_start(label(parameter['label']), False, False, 0)
            kind = parameter.get('type', 'text')
            default = parameter.get('default', '')
            if kind == 'choice':
                field = Gtk.ComboBoxText()
                for choice in parameter.get('choices', []):
                    if isinstance(choice, dict):
                        value, title = str(choice.get('value', choice.get('id', ''))), str(choice.get('label', choice.get('value', '')))
                    else:
                        value = title = str(choice)
                    field.append(value, title)
                field.set_active_id(str(default))
                if field.get_active() < 0:
                    field.set_active(0)
            elif kind == 'folder':
                field = Gtk.FileChooserButton(title=parameter['label'], action=Gtk.FileChooserAction.SELECT_FOLDER)
                field.set_local_only(True)
                if default:
                    field.set_filename(str(default))
            else:
                field = Gtk.Entry()
                field.set_text(str(default) if default is not None else '')
                field.set_activates_default(True)
            fields[parameter['key']] = (kind, field)
            box.pack_start(field, False, False, 0)
        box.pack_start(label('Output: ' + (self.output_folder or 'next to each original, using a new filename'), 'muted', True), False, False, 0)
        dialog.show_all()
        result = None
        while dialog.run() == Gtk.ResponseType.OK:
            try:
                result = {}
                for key, (kind, field) in fields.items():
                    if kind == 'choice':
                        value = field.get_active_id()
                    elif kind == 'folder':
                        value = field.get_filename()
                    else:
                        value = field.get_text().strip()
                        if kind == 'int':
                            value = int(value)
                        elif kind == 'float':
                            value = float(value)
                    result[key] = value
                break
            except ValueError:
                self._error('Enter a valid number for each numeric setting.', parent=dialog)
                result = None
        dialog.destroy()
        return result

    def _start_worker(self, title, work):
        if self.busy:
            return
        self.busy = True
        self.cancel_event.clear()
        self.progress_bar.set_fraction(0)
        self.progress_bar.set_text('Starting…')
        self.progress_label.set_text(title)
        self.progress_box.show_all()
        self._render_operations()
        def worker():
            try:
                result = work()
                GLib.idle_add(self._finished, title, result, None)
            except Exception as error:
                GLib.idle_add(self._finished, title, getattr(error, 'partial_result', None), str(error))
        threading.Thread(target=worker, daemon=True).start()

    def _worker_progress(self, completed, total, message):
        GLib.idle_add(self._update_progress, completed, total, message)

    def _update_progress(self, completed, total, message):
        self.progress_bar.set_fraction(min(1.0, max(0.0, completed / total)) if total else 0)
        self.progress_bar.set_text(f'{completed} / {total}' if total else 'Working…')
        self.progress_label.set_text(str(message))
        return False

    def _finished(self, title, result, error):
        self.busy = False
        self.progress_box.hide()
        self._render_operations()
        if error:
            if result and result.get('outputs'):
                self._finished(title, result, None)
                self.status.set_text(f"{len(result['outputs'])} completed output(s) kept. Operation stopped: {error}")
            else:
                self.status.set_text('Operation stopped: ' + error)
            self._error(error)
        else:
            result = result or {}
            outputs = result.get('outputs', [])
            warnings = result.get('warnings', [])
            text = f'{title} · {len(outputs)} output' + ('s' if len(outputs) != 1 else '')
            if self.cancel_event.is_set():
                text += ' · cancelled'
            self.status.set_text(text + ((' · ' + str(warnings[0])) if warnings else ''))
            self.history.insert(0, (text, outputs))
            self.history = self.history[:6]
            for child in self.history_box.get_children():
                self.history_box.remove(child)
            for caption, files in self.history:
                row = button(caption + ('   ↗' if files else ''), lambda _, p=list(files): self._reveal(p[0]) if p else None, 'history')
                row.set_tooltip_text('\n'.join(map(str, files)))
                self.history_box.pack_start(row, False, False, 0)
            self.history_box.show_all()
            self.history_expander.set_expanded(True)
            if warnings:
                self._error('\n'.join(map(str, warnings)), title='Completed with a note', warning=True)
        return False

    def _error(self, message, parent=None, title='Something needs attention', warning=False):
        dialog = Gtk.MessageDialog(transient_for=parent or self, modal=True, message_type=Gtk.MessageType.WARNING if warning else Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.CLOSE, text=title)
        dialog.format_secondary_text(str(message))
        dialog.run()
        dialog.destroy()

    def _folder(self, title):
        dialog = Gtk.FileChooserDialog(title=title, transient_for=self, action=Gtk.FileChooserAction.SELECT_FOLDER)
        dialog.add_buttons('Cancel', Gtk.ResponseType.CANCEL, 'Choose folder', Gtk.ResponseType.OK)
        dialog.set_local_only(True)
        folder = dialog.get_filename() if dialog.run() == Gtk.ResponseType.OK else None
        dialog.destroy()
        return folder

    def _copy_paths(self):
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text('\n'.join(self._chosen_paths()), -1)
        self.status.set_text('Paths copied to the clipboard.')

    def _copy_files(self):
        self.file_clipboard = [Path(path).as_uri() for path in self._chosen_paths()]
        selection = Gdk.SELECTION_CLIPBOARD
        for name, info in [('text/uri-list', 1), ('x-special/gnome-copied-files', 2), ('UTF8_STRING', 3)]:
            Gtk.selection_add_target(self.clipboard_owner, selection, Gdk.Atom.intern(name, False), info)
        self.clipboard_owner.realize()
        if Gtk.selection_owner_set(self.clipboard_owner, selection, Gdk.CURRENT_TIME):
            self.status.set_text('Files copied. Paste them into your file manager.')
        else:
            self._copy_paths()
            self.status.set_text('Clipboard file transfer unavailable; file paths copied instead.')

    def _selection_get(self, widget, data, info, timestamp):
        if info == 1:
            data.set_uris(self.file_clipboard)
        elif info == 2:
            data.set(Gdk.Atom.intern('x-special/gnome-copied-files', False), 8, ('copy\n' + '\n'.join(self.file_clipboard)).encode('utf-8'))
        else:
            data.set_text('\n'.join(local_uri_path(uri) for uri in self.file_clipboard), -1)

    def _transfer(self, move):
        paths = self._chosen_paths()
        folder = self._folder('Move to folder' if move else 'Copy to folder')
        if not folder:
            return
        if move:
            dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.OK_CANCEL, text=f'Move {len(paths)} selected file(s)?')
            dialog.format_secondary_text(f'Originals will be moved to:\n{folder}\nExisting filenames will never be replaced.')
            response = dialog.run()
            dialog.destroy()
            if response != Gtk.ResponseType.OK:
                return
        def work():
            outputs, warnings, moved = [], [], []
            for index, source in enumerate(paths):
                if self.cancel_event.is_set():
                    break
                try:
                    source_path = Path(source)
                    if source_path.is_symlink():
                        raise ValueError('Select the original file or folder instead of a symbolic link.')
                    if source_path.is_dir() and Path(folder).resolve().is_relative_to(source_path.resolve()):
                        raise ValueError('Choose a destination outside the selected folder.')
                    def copy_file(src, dst):
                        with open(src, 'rb') as source_stream, open(dst, 'xb') as target_stream:
                            while True:
                                if self.cancel_event.is_set():
                                    raise RuntimeError('Operation cancelled.')
                                chunk = source_stream.read(1024 * 1024)
                                if not chunk:
                                    break
                                target_stream.write(chunk)
                        shutil.copystat(src, dst)
                        return dst
                    with tempfile.TemporaryDirectory(prefix='.mandarin-', dir=folder) as temporary:
                        staged = Path(temporary) / source_path.name
                        if source_path.is_dir():
                            # Preserve nested symbolic links as links; never follow them.
                            shutil.copytree(source, staged, symlinks=True, copy_function=copy_file)
                        else:
                            copy_file(source, staged)
                        if self.cancel_event.is_set():
                            raise RuntimeError('Operation cancelled.')
                        if source_path.is_dir():
                            destination = engine._folder_publish(staged, Path(folder), source_path.name)
                        else:
                            destination = engine._publish(staged, Path(folder), source_path.name)
                    if move:
                        if source_path.is_dir():
                            shutil.rmtree(source)
                        else:
                            os.unlink(source)
                        moved.append(source)
                    outputs.append(str(destination))
                except Exception as error:
                    warnings.append(f'{Path(source).name}: {error}')
                self._worker_progress(index + 1, len(paths), Path(source).name)
            if moved:
                GLib.idle_add(self._remove_moved, moved)
            return {'outputs': outputs, 'warnings': warnings}
        self._start_worker('Move to folder' if move else 'Copy to folder', work)

    def _remove_moved(self, paths):
        self.paths = [path for path in self.paths if path not in paths]
        self._refresh()
        return False

    def _reveal(self, path):
        location = Path(path)
        folder = location if location.is_dir() else location.parent
        try:
            Gio.AppInfo.launch_default_for_uri(folder.as_uri(), None)
        except Exception as error:
            self._error(error)

    def _reveal_selected(self):
        paths = self._chosen_paths()
        if paths:
            self._reveal(paths[0])

    def _terminal(self):
        paths = self._chosen_paths()
        if not paths:
            return
        folder = str(Path(paths[0]).parent)
        for command in ('x-terminal-emulator', 'gnome-terminal', 'xfce4-terminal', 'mate-terminal', 'xterm'):
            executable = shutil.which(command)
            if executable:
                try:
                    subprocess.Popen([executable], cwd=folder, start_new_session=True)
                except Exception as error:
                    self._error(error)
                return
        self._error('No supported terminal emulator is installed.')

    def _preview(self):
        paths = self._chosen_paths()
        if not paths:
            return
        path = Path(paths[0])
        preview = Gtk.Window(title=path.name, transient_for=self)
        preview.set_default_size(620, 480)
        preview.set_keep_above(True)
        scroll = Gtk.ScrolledWindow()
        preview.add(scroll)
        try:
            from gi.repository import GdkPixbuf
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), 900, 650, True)
            scroll.add(Gtk.Image.new_from_pixbuf(pixbuf))
        except Exception:
            try:
                if path.stat().st_size > 2 * 1024 * 1024:
                    raise ValueError('Text preview is limited to 2 MB. Open this file in its default application.')
                text = path.read_text(encoding='utf-8')
                if '\x00' in text:
                    raise ValueError('This binary format cannot be previewed as text.')
                view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
                view.set_left_margin(18)
                view.set_right_margin(18)
                view.get_buffer().set_text(text)
                scroll.add(view)
            except Exception as error:
                notice = label(f'Preview is unavailable for this file.\n\n{error}', 'muted', True)
                notice.set_margin_start(24)
                notice.set_margin_end(24)
                scroll.add(notice)
        preview.show_all()

    def _settings(self):
        dialog = Gtk.Dialog(title='Mandarin settings', transient_for=self, modal=True)
        dialog.add_button('Done', Gtk.ResponseType.CLOSE)
        dialog.set_default_size(560, 660)
        box = dialog.get_content_area()
        box.set_border_width(24)
        box.set_spacing(14)
        box.pack_start(label('Made for your desktop.', 'empty-title'), False, False, 0)
        box.pack_start(label('All processing happens locally. Capabilities depend on the engines installed on this computer.', 'muted', True), False, False, 0)
        box.pack_start(label('OUTPUT FOLDER', 'eyebrow'), False, False, 0)
        output = button(self.output_folder or 'Next to each original', lambda _: choose())
        def choose():
            folder = self._folder('Default output folder')
            if folder:
                self.output_folder = folder
                output.set_label(folder)
        box.pack_start(output, False, False, 0)
        box.pack_start(button('Reset to next to originals', lambda _: (setattr(self, 'output_folder', None), output.set_label('Next to each original')), 'flat'), False, False, 0)
        box.pack_start(label('DRAG WHEEL', 'eyebrow'), False, False, 0)
        wheel = getattr(self.app, 'wheel', None)
        wheel_ready = wheel is not None and getattr(wheel, 'pointer', None) is not None
        if wheel_ready:
            toggle = Gtk.CheckButton(label='Enable the global drag wheel')
            toggle.set_active(wheel.enabled)
            toggle.connect('toggled', lambda control: setattr(wheel, 'enabled', control.get_active()))
            box.pack_start(toggle, False, False, 0)
            box.pack_start(label('While dragging files, press Shift for Convert, Alt for Tools, or Ctrl for Actions. Drop onto a wedge to run it.', 'muted', True), False, False, 0)
        else:
            box.pack_start(label('Global drag wheel requires an X11 desktop. The main file drop area works on both X11 and Wayland.', 'muted', True), False, False, 0)
        box.pack_start(label('PROCESSING ENGINES', 'eyebrow'), False, False, 0)
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(160)
        engines = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        scroll.add(engines)
        try:
            caps = engine.capabilities()
            for name, state in caps.items():
                if name.startswith('archive_max_'):
                    continue
                if isinstance(state, dict):
                    available = bool(state.get('available', state.get('path', False)))
                    detail = state.get('version') or state.get('path') or state.get('reason') or ''
                else:
                    available = bool(state)
                    detail = str(state) if state not in (True, False, None) else ''
                engines.pack_start(label(('●  ' if available else '○  ') + str(name) + ('  ·  ' + str(detail) if detail else ('  ·  ready' if available else '  ·  unavailable')), 'muted', True), False, False, 0)
        except Exception as error:
            engines.pack_start(label(str(error), 'muted', True), False, False, 0)
        box.pack_start(scroll, True, True, 0)
        box.pack_start(label('Closing the window keeps Mandarin in the tray when available.\nUse the tray menu to quit. File clipboard contents require Mandarin to stay open.', 'muted', True), False, False, 0)
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def _setup_tray(self):
        try:
            gi.require_version('AyatanaAppIndicator3', '0.1')
            from gi.repository import AyatanaAppIndicator3 as Indicator
        except (ValueError, ImportError):
            return
        self.tray = Indicator.Indicator.new('mandarin', 'mandarin', Indicator.IndicatorCategory.APPLICATION_STATUS)
        self.tray.set_icon_full(str(Path(__file__).resolve().parent.parent / 'assets' / 'mandarin.svg'), 'Mandarin')
        menu = Gtk.Menu()
        for caption, fn in [('Open Mandarin', lambda _: self.present()), ('Add files…', lambda _: (self.present(), self._choose_files())), ('Quit Mandarin', lambda _: self._quit())]:
            item = Gtk.MenuItem(label=caption)
            item.connect('activate', fn)
            menu.append(item)
        menu.show_all()
        self.tray.set_menu(menu)
        self.tray.set_status(Indicator.IndicatorStatus.ACTIVE)

    def _close(self, *_):
        if self.tray:
            self.hide()
            return True
        if self.busy:
            self.status.set_text('Cancel or finish the current operation before closing Mandarin.')
            return True
        return False

    def _quit(self):
        if self.busy:
            self.present()
            self.status.set_text('Cancel or finish the current operation before quitting Mandarin.')
            return
        self.app.quit()


class MandarinApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.local.Mandarin', flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.window = None

    def do_activate(self):
        if self.window is None:
            self.window = MainWindow(self)
        self.window.present()

    def do_open(self, files, count, hint):
        self.do_activate()
        self.window.add_paths([file.get_path() for file in files if file.is_native() and file.get_path()])


def create_application():
    return MandarinApplication()


def main(argv=None):
    import sys
    return create_application().run(argv if argv is not None else sys.argv)

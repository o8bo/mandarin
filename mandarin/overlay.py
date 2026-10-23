"""X11 drag wheel. Uses the XDND selection, never a global keyboard grab."""
from __future__ import annotations

import ctypes
import ctypes.util
import math
from pathlib import Path
from urllib.parse import urlsplit, unquote

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo

from . import engine


def local_paths(uris):
    result = []
    for uri in uris:
        parsed = urlsplit(uri)
        if parsed.scheme == "file" and parsed.netloc in ("", "localhost") and not parsed.query and not parsed.fragment:
            decoded = unquote(parsed.path)
            if "\0" in decoded or not decoded.startswith("/"):
                continue
            path = Path(decoded)
            if path.exists() and (path.is_file() or path.is_dir()):
                result.append(str(path))
    return result


class XPointer:
    """Read pointer/modifier state and whether an X11 file drag is in progress."""

    def __init__(self):
        display = Gdk.Display.get_default()
        if display is None or "X11" not in type(display).__name__:
            raise RuntimeError("The global drag wheel needs an X11 desktop. Use the main drop zone on Wayland.")
        self.lib = ctypes.CDLL(ctypes.util.find_library("X11"))
        self.lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.lib.XOpenDisplay.restype = ctypes.c_void_p
        self.lib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        self.lib.XDefaultRootWindow.restype = ctypes.c_ulong
        self.lib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        self.lib.XInternAtom.restype = ctypes.c_ulong
        self.lib.XGetSelectionOwner.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.lib.XGetSelectionOwner.restype = ctypes.c_ulong
        self.lib.XQueryPointer.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_uint)]
        self.lib.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self.lib.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.lib.XKeysymToKeycode.restype = ctypes.c_ubyte
        self.lib.XQueryKeymap.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.display = self.lib.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError("Could not open the X11 display")
        self.root = self.lib.XDefaultRootWindow(self.display)
        self.selection = self.lib.XInternAtom(self.display, b"XdndSelection", 0)
        self.escape_code = self.lib.XKeysymToKeycode(self.display, 0xFF1B)

    def state(self):
        root, child = ctypes.c_ulong(), ctypes.c_ulong()
        x, y, wx, wy, mask = ctypes.c_int(), ctypes.c_int(), ctypes.c_int(), ctypes.c_int(), ctypes.c_uint()
        self.lib.XQueryPointer(self.display, self.root, ctypes.byref(root), ctypes.byref(child),
            ctypes.byref(x), ctypes.byref(y), ctypes.byref(wx), ctypes.byref(wy), ctypes.byref(mask))
        owner = self.lib.XGetSelectionOwner(self.display, self.selection)
        return x.value, y.value, mask.value, bool(owner)

    def close(self):
        if self.display:
            self.lib.XCloseDisplay(self.display)
            self.display = None

    def escape_down(self):
        # Inspect only Escape; no text events are captured or stored.
        keys = (ctypes.c_ubyte * 32)()
        self.lib.XQueryKeymap(self.display, keys)
        return bool(keys[self.escape_code // 8] & (1 << (self.escape_code % 8)))


from .radial_geometry import sector_at


class DragWheel(Gtk.Window):
    SIZE = 420

    def __init__(self, controller):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.controller = controller
        self.pointer = None
        self.poll_id = None
        self.release_id = None
        self.mode = "convert"
        self.paths = []
        self.operations = []
        self.hover = -1
        self.last_mod = 0
        self.pending_drop = False
        self.drop_point = None
        self.asked = False
        self.enabled = True
        self.origin = (0, 0)
        self.set_title("Mandarin drag wheel")
        self.set_default_size(self.SIZE, self.SIZE)
        self.set_resizable(False)
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_accept_focus(False)
        self.set_app_paintable(True)
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.connect("draw", self._draw)
        self.drag_dest_set(Gtk.DestDefaults(0), [Gtk.TargetEntry.new("text/uri-list", 0, 0)], Gdk.DragAction.COPY)
        self.connect("drag-motion", self._motion)
        self.connect("drag-drop", self._drop)
        self.connect("drag-data-received", self._received)
        self.connect("drag-leave", self._leave)

    def start(self):
        try:
            self.pointer = XPointer()
            self.poll_id = GLib.timeout_add(35, self._poll)
            return True
        except Exception as error:
            self.unavailable_reason = str(error)
            return False

    def stop(self):
        if self.poll_id:
            GLib.source_remove(self.poll_id)
            self.poll_id = None
        if self.release_id:
            GLib.source_remove(self.release_id)
            self.release_id = None
        if self.pointer:
            self.pointer.close()
            self.pointer = None
        self.hide()

    def _poll(self):
        x, y, mask, selection = self.pointer.state()
        modifiers = mask & (1 | 4 | 8)
        down = bool(mask & 256)
        if self.enabled and down and selection and modifiers and modifiers != self.last_mod:
            mode = "actions" if modifiers & 4 else "tools" if modifiers & 8 else "convert"
            if not self.get_visible():
                self.paths = []
                self.operations = []
                self.pending_drop = False
                self.drop_point = None
                self.asked = False
                self.open_at(x, y, mode)
            elif self.mode != mode:
                self.mode = mode
                self._rebuild()
        self.last_mod = modifiers
        if self.get_visible():
            if self.pointer.escape_down():
                self.hide()
                return True
            self.hover = sector_at(x - self.origin[0], y - self.origin[1], len(self.operations))
            self.queue_draw()
            if not down and not self.release_id:
                self.release_id = GLib.timeout_add(350, self._released)
        return True

    def _released(self):
        self.release_id = None
        if not self.pending_drop:
            self.hide()
        return False

    def open_at(self, x, y, mode="convert"):
        self.mode = mode
        monitor = Gdk.Display.get_default().get_monitor_at_point(x, y)
        bounds = monitor.get_workarea()
        px = max(bounds.x, min(x - self.SIZE // 2, bounds.x + bounds.width - self.SIZE))
        py = max(bounds.y, min(y - self.SIZE // 2, bounds.y + bounds.height - self.SIZE))
        self.origin = (px, py)
        self.move(px, py)
        self.show_all()
        self.queue_draw()

    def _rebuild(self):
        if self.mode == "actions":
            self.operations = [
                {"id": "ui:copy_paths", "label": "Copy path"},
                {"id": "ui:reveal", "label": "Show folder"},
                {"id": "ui:copy_to", "label": "Copy to…"},
                {"id": "ui:terminal", "label": "Terminal"},
                {"id": "ui:preview", "label": "Preview"},
                {"id": "ui:more", "label": "All actions"},
            ]
        elif self.paths:
            options = [op for op in engine.get_operations(self.paths, self.mode) if op.get("available", True)]
            self.operations = options[:7]
            if len(options) > 7:
                self.operations.append({"id": "ui:more", "label": "More…"})
        else:
            self.operations = []
        self.queue_draw()

    def _motion(self, widget, context, x, y, time):
        Gdk.drag_status(context, Gdk.DragAction.COPY, time)
        if not self.asked:
            self.asked = True
            self.drag_get_data(context, Gdk.Atom.intern("text/uri-list", False), time)
        self.hover = sector_at(x, y, len(self.operations))
        self.queue_draw()
        return True

    def _drop(self, widget, context, x, y, time):
        self.pending_drop = True
        self.drop_point = (x, y)
        self.hover = sector_at(x, y, len(self.operations))
        self.drag_get_data(context, Gdk.Atom.intern("text/uri-list", False), time)
        return True

    def _leave(self, *args):
        self.hover = -1
        self.queue_draw()

    def _received(self, widget, context, x, y, selection, info, time):
        paths = local_paths(selection.get_uris() or [])
        if paths:
            self.paths = paths
            self._rebuild()
        if not self.pending_drop:
            return
        # Selection delivery is asynchronous; its x/y can be zero on GTK/X11.
        # The coordinates from drag-drop identify the user's chosen wedge.
        dx, dy = self.drop_point or (x, y)
        chosen = sector_at(dx, dy, len(self.operations))
        op = self.operations[chosen] if chosen >= 0 else {"id": "ui:more"}
        Gtk.drag_finish(context, bool(self.paths), False, time)
        self.hide()
        self.pending_drop = False
        self.drop_point = None
        if self.paths:
            GLib.idle_add(self._dispatch, op, list(self.paths))

    def _dispatch(self, op, paths):
        self.controller.add_paths(paths)
        self.controller.present()
        action = op["id"]
        if action == "ui:copy_paths":
            Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text("\n".join(paths), -1)
        elif action in ("ui:reveal", "ui:terminal"):
            import subprocess
            parent = str(Path(paths[0]).parent)
            if action == "ui:reveal":
                subprocess.Popen(["xdg-open", parent])
            else:
                import shutil
                for cmd in ("x-terminal-emulator", "gnome-terminal", "xfce4-terminal"):
                    if shutil.which(cmd):
                        subprocess.Popen([cmd], cwd=parent)
                        break
        elif not action.startswith("ui:"):
            self.controller.run_selected_operation(op, paths=paths)
        else:
            # The main window owns destination/preview dialogs and the full operation list.
            if hasattr(self.controller, "activate_wheel_action"):
                self.controller.activate_wheel_action(action.removeprefix("ui:"), paths)
        return False

    def _text(self, cr, text, x, y, size=11, color=(0.96, 0.94, 0.90), bold=False, width=112):
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(Pango.FontDescription(f"Sans {'Bold ' if bold else ''}{size}"))
        layout.set_width(width * Pango.SCALE)
        layout.set_alignment(Pango.Alignment.CENTER)
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        layout.set_text(text, -1)
        _, height = layout.get_pixel_size()
        cr.set_source_rgb(*color)
        cr.move_to(x - width / 2, y - height / 2)
        PangoCairo.show_layout(cr, layout)

    def _draw(self, widget, cr):
        import cairo
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        center = self.SIZE / 2
        cr.set_source_rgba(0.10, 0.12, 0.10, 0.97)
        cr.arc(center, center, center - 9, 0, 2 * math.pi)
        cr.fill()
        count = len(self.operations)
        for i, op in enumerate(self.operations):
            angle = -math.pi / 2 + i * 2 * math.pi / count
            start, end = angle - math.pi / count + .018, angle + math.pi / count - .018
            cr.new_path()
            cr.arc(center, center, center - 16, start, end)
            cr.arc_negative(center, center, 72, end, start)
            cr.close_path()
            cr.set_source_rgb(*((.94, .36, .15) if i == self.hover else (.17, .20, .17)))
            cr.fill()
            self._text(cr, op.get("label", ""), center + 132 * math.cos(angle),
                center + 132 * math.sin(angle), size=10, bold=True, width=105)
        cr.set_source_rgb(.97, .49, .22)
        cr.arc(center, center, 61, 0, math.pi * 2)
        cr.fill()
        label = {"convert": "CONVERT", "tools": "TOOLS", "actions": "ACTIONS"}[self.mode]
        self._text(cr, label, center, center - 10, size=10, color=(.12, .16, .11), bold=True)
        self._text(cr, "Drop to open" if self.paths else "Move file here", center, center + 15,
            size=8, color=(.12, .16, .11), width=105)
        return False

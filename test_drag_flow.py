"""Real X11 XDND integration test between two windows owned by this test.

Run with the same PYTHONPATH/PATH as launch.sh; requires a graphical X11 session.
No user file manager or unrelated window is automated.
"""
import ctypes
import ctypes.util
import json
from pathlib import Path
import tempfile
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
from PIL import Image
from mandarin.overlay import DragWheel


def main(mode='convert'):
    folder = tempfile.TemporaryDirectory(prefix='mandarin-drag-test-')
    path = Path(folder.name) / 'drag sample.png'
    Image.new('RGB', (32, 32), 'orange').save(path)
    result = {'wheel_visible': False, 'file_received': False, 'operation': None}
    class Controller:
        def add_paths(self, paths):
            result['paths'] = paths
        def present(self):
            pass
        def run_selected_operation(self, op, paths=None):
            result['operation'] = op['id']
            result['paths'] = paths
    wheel = DragWheel(Controller())
    assert wheel.start(), getattr(wheel, 'unavailable_reason', 'wheel failed')
    window = Gtk.Window(title='Mandarin DND test source')
    window.set_default_size(280, 140)
    window.move(240, 260)
    source = Gtk.EventBox()
    source.add(Gtk.Label(label='Test-owned source file'))
    window.add(source)
    source.drag_source_set(Gdk.ModifierType.BUTTON1_MASK,
        [Gtk.TargetEntry.new('text/uri-list', 0, 0)], Gdk.DragAction.COPY)
    source.connect('drag-data-get', lambda widget, context, data, info, time: data.set_uris([path.as_uri()]))
    window.show_all()
    x = wheel.pointer.lib
    d = wheel.pointer.display
    xt = ctypes.CDLL(ctypes.util.find_library('Xtst'))
    xt.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
    xt.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    xt.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    x.XFlush.argtypes = [ctypes.c_void_p]
    shift = x.XKeysymToKeycode(d, {'convert': 0xffe1, 'tools': 0xffe9, 'actions': 0xffe3}[mode])
    def pointer(px, py):
        xt.XTestFakeMotionEvent(d, -1, px, py, 0)
        x.XFlush(d)
    def button(down):
        xt.XTestFakeButtonEvent(d, 1, down, 0)
        x.XFlush(d)
    def key(down):
        xt.XTestFakeKeyEvent(d, shift, down, 0)
        x.XFlush(d)
    def step1():
        px, py = window.get_position()
        result['source_origin'] = [px, py]
        pointer(px + 100, py + 90)
        button(1)
        return False
    def step2():
        px, py = result['source_origin']
        pointer(px + 135, py + 95)
        return False
    def step3():
        key(1)
        return False
    def step4():
        result['wheel_visible'] = wheel.get_visible()
        key(0)
        px, py = wheel.origin
        pointer(px + 210, py + 80)
        return False
    def step5():
        result['file_received'] = bool(wheel.paths)
        result['operations'] = [o['id'] for o in wheel.operations]
        if wheel.get_visible():
            pix = Gdk.pixbuf_get_from_window(wheel.get_window(), 0, 0, wheel.SIZE, wheel.SIZE)
            filename = 'screenshot-wheel.png' if mode == 'convert' else f'screenshot-wheel-{mode}.png'
            pix.savev(str(Path(__file__).parent / filename), 'png', [], [])
        button(0)
        return False
    def done():
        button(0)
        key(0)
        wheel.stop()
        window.destroy()
        Gtk.main_quit()
        return False
    for wait, callback in [(500, step1), (800, step2), (1200, step3), (1650, step4), (2250, step5), (3300, done)]:
        GLib.timeout_add(wait, callback)
    Gtk.main()
    if mode == 'actions':
        result['clipboard_matches'] = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text() == str(path)
    folder.cleanup()
    print(json.dumps(result, indent=2))
    assert result['wheel_visible'], 'Modifier did not open wheel during XDND'
    assert result['file_received'], 'Wheel did not receive file URI preview'
    expected = {'convert': 'image:jpeg', 'tools': 'image:resize'}.get(mode)
    if expected:
        assert result['operation'] == expected, 'Drop did not dispatch highlighted operation'
    else:
        assert result['clipboard_matches'], 'Copy path action did not reach the clipboard'


if __name__ == '__main__':
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else 'convert')

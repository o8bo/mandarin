"""Desktop entry point; command-line conversion is available without a GUI."""
import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Mandarin · local file conversion for Windows and Linux")
    parser.add_argument("files", nargs="*")
    parser.add_argument("--capabilities", action="store_true")
    parser.add_argument("--list", action="store_true", help="List operations for selected files")
    parser.add_argument("--operation", help="Run a conversion operation without a window")
    parser.add_argument("--options", default="{}", help="JSON operation settings")
    parser.add_argument("--background", action="store_true", help="Start quietly in the tray")
    parser.add_argument("--frontend",choices=['gtk','qt'],help='Linux defaults to GTK; Windows defaults to Qt')
    parser.add_argument("--self-test",metavar='REPORT.json',help='Run real packaged GUI, conversion, publication and cancellation checks')
    parser.add_argument("--_process-fixture", nargs=2, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args._process_fixture:
        from .process_fixture import run
        return run(args._process_fixture[0], Path(args._process_fixture[1]))
    from . import engine
    if args.self_test:
        from .smoke import run
        return run(Path(args.self_test))
    if args.capabilities:
        if sys.stdout: print(json.dumps(engine.capabilities(), indent=2))
        return 0
    if args.list:
        if sys.stdout: print(json.dumps(engine.get_operations(args.files, "convert") + engine.get_operations(args.files, "tools"), indent=2))
        return 0
    if args.operation:
        try:
            result = engine.run_operation(args.operation, args.files, json.loads(args.options))
            if sys.stdout: print(json.dumps(result, indent=2))
            return 0
        except Exception as error:
            if sys.stderr:print(str(error), file=sys.stderr)
            return 1
    if args.frontend=='qt' or (sys.platform=='win32' and args.frontend!='gtk'):
        from .qt_ui import main as qt_main
        return qt_main(args.files)
    if sys.platform=='win32':raise RuntimeError('GTK frontend is Linux-only. Use the default Qt frontend on Windows.')
    from .ui import MandarinApplication
    from .overlay import DragWheel
    class DesktopApplication(MandarinApplication):
        def do_activate(self):
            super().do_activate()
            if not hasattr(self, "wheel"):
                self.wheel = DragWheel(self.window)
                self.wheel.start()
                self.connect("shutdown", lambda *_: self.wheel.stop())
                if args.background and self.window.tray:
                    from gi.repository import GLib
                    GLib.idle_add(self.window.hide)

    app = DesktopApplication()
    # Gio forwards open-file requests to an existing instance; do not discard them.
    return app.run([sys.argv[0], *args.files])


if __name__ == "__main__":
    raise SystemExit(main())

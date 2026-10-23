# Build and verification

Python 3.12 x64 is the pinned build target. GTK remains the Linux default;
PySide6 is used for the Windows frontend. Build on the target OS: PyInstaller
is not a Windows cross-compiler. See its [Qt deployment guidance](https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html).

## Windows (PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe scripts/run_tests.py --require-windows --report verification/windows-tests.json
.\.venv\Scripts\python.exe scripts/build_portable.py --target windows
```

A successful run creates:

- `dist/Mandarin/Mandarin.exe`, its `_internal` tree and `licenses/`
- `dist/Mandarin-smoke.json` and `dist/Mandarin/BUILD-REPORT.json`
- `dist/Mandarin-Windows-x64.zip` and `.zip.sha256`
- `dist/Mandarin-portable-verification.json` and `dist/Mandarin-portable-verification-smoke.json`

The builder refuses non-Windows/non-x64 hosts, checks the PE x64 header, runs the
frozen GUI/conversion/safety/cancellation smoke from a temporary working directory
with PYTHONPATH removed, then ZIPs the distribution and verifies the checksum,
extracts it, and launches the extracted executable with build Python removed from
PATH and an isolated tool configuration. Both report success before CI uploads
the candidate. Failed ZIP verification moves the candidate into the ignored
build directory rather than retaining it at the upload path. It refuses to
replace an existing ZIP. Bundled Python/Qt/Pillow/pypdf and upstream license
notices are included. Optional engine binaries are not copied. Requirements pin
direct/build dependencies; this is a repeatable process, not a claim of
bit-identical builds or a complete transitive hash lock. The build report records
resolved versions. No installer or code signing is supplied.

The manual **Build Windows portable candidate** GitHub Actions workflow uses
`windows-2022`, runs native Qt tests, then this same builder and retains candidate/diagnostic artifacts for 30 days.
It uses pinned, verified Node 24 action commits; versions and SHA values are
recorded in PUBLICATION.md. Diagnostics and a job summary are retained on failures;
required test/build failures keep their nonzero status.
It has read-only repository permissions and does not publish a release. It has
**not been run** from the Linux workspace. Manual workflows must first exist on
the default branch: [GitHub instructions](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).
Do not push or publish until the owner approves. A runner smoke test is not a
fresh Windows 11 desktop acceptance test.

## Linux regression and Qt packaging validation

Linux Mint system GTK dependencies:

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 python3-pil python3-pypdf ffmpeg libreoffice poppler-utils
./launch.sh --capabilities
PYTHONPATH=vendor:. PATH="$PWD/vendor/usr/bin:$PATH" python3 -m unittest -v test_engine test_platform
PYTHONPATH=vendor:. PATH="$PWD/vendor/usr/bin:$PATH" python3 test_drag_flow.py
python3 test_drag_flow.py tools
python3 test_drag_flow.py actions
```

The last three commands require an X11 session. Automated CI uses Xvfb; actual
Mint desktop testing is separate. Wayland supports the main GTK window drop
zone; the X11 global wheel is unavailable there. Wayland was not tested here.

For Qt integration tests/build validation, install `python3-venv` if needed, create a separate venv and install
`requirements-build.txt` (Qt may need `libegl1 libopengl0 libxcb-cursor0` on Linux):

```bash
QT_QPA_PLATFORM=offscreen python -m unittest -v test_engine test_platform test_qt
QT_QPA_PLATFORM=offscreen python -m mandarin --self-test qt-smoke.json
QT_QPA_PLATFORM=offscreen python scripts/build_portable.py --target linux-qt-validation
```

This produces a **Linux ELF** executable/ZIP named `Mandarin-Linux-Qt-validation`.
It is a packaging diagnostic, not the Linux Mint GTK release or a Windows build.
GTK remains installed/launched through `install.py` / `launch.sh`.
The expanded packaged smoke covers images, Arabic/Japanese filenames, output
collisions/original preservation, batch results and cancellation, image-to-PDF
and PDF rotation, safe ZIP round trips, missing engine detection, a real
parent/child process tree cancellation, nonzero subprocess errors and Qt startup.
Its child fixture runs the bundled executable itself, without an external Python.
Explorer dragging, native dialogs, Windows 11 DPI and clean-machine acceptance
remain manual checks. Optional FFmpeg/LibreOffice/Poppler conversions are not
implied by the packaged smoke.

Tests generate only temporary fixtures. Optional-engine tests skip explicitly
when dependencies are absent; review skip reasons before judging coverage.

# Windows 11 x64

Status: native Windows Server 2022 CI has started. The initial source-test run
failed and prevented the EXE build; fixes are being verified. Interactive Windows
11 desktop/Explorer acceptance is **NOT TESTED**. No verified Windows ZIP yet.
See [PUBLICATION.md](PUBLICATION.md) for the repository and build instructions.

## Portable application (after a successful Windows build)

Extract the entire `Mandarin-Windows-x64.zip`, then launch `Mandarin/Mandarin.exe`.
Keep `_internal` beside the executable. Python is included. Do not run the EXE
inside the ZIP. This candidate is unsigned; code signing is not configured.
No administrator privileges, global input hooks, registry edits or account are
required. Windows ARM64 and 32-bit Windows are not targets.

Images, ZIP/TAR archives, SRT/VTT/TXT subtitles and pypdf operations are included.
Optional conversion executables are **not** included:

| Engine | Enables | Configuration |
|---|---|---|
| FFmpeg | Audio/video encodes and tools | Select `ffmpeg.exe`; optional `ffprobe.exe` |
| LibreOffice | Office document conversions | Select `soffice.com` or `soffice.exe` in its installed `program` directory |
| Poppler | PDF page rasterization, embedded image export | Select `pdftoppm.exe`, `pdftotext.exe`, `pdfimages.exe` as needed |

Use **Engines & settings → Locate** to choose trusted installed tools, including
all their own dependent DLLs. Renaming one executable is not an installation.
FFmpeg upstream lists Windows builds at <https://ffmpeg.org/download.html>.
LibreOffice downloads: <https://www.libreoffice.org/download/download-libreoffice/>.
Poppler upstream: <https://poppler.freedesktop.org/> (upstream does not ship an
official Windows installer; obtain a build from a source you trust).
Mandarin never downloads or installs engines automatically.

Discovery checks `MANDARIN_<TOOL>_PATH`, saved configuration, adjacent `tools/`
layouts, PATH, then standard LibreOffice Program Files directories. An invalid
explicit path disables that tool rather than silently choosing another binary.
Configuration: `%LOCALAPPDATA%/Mandarin/tools.json`. Use Reset beside an engine to clear its saved path. Startup failures write `startup-error.log` in that
same directory and show a native error dialog.

## Interaction

Add files/folders with the buttons, or drag files from Explorer **onto Mandarin**.
The in-app wheel appears near the cursor after a drop (optional checkbox), or
with **Open radial menu**. Select a wedge with the mouse, or use arrows/Enter;
Escape closes it. More opens access to the full operation list. Select multiple
files for batch conversion; no selection means all listed files. Output defaults
to beside the originals; choose another destination when necessary.

Windows does not implement the Linux desktop-wide modifier wheel, a tray daemon,
or Explorer context menus. No claim is made that desktop-wide Explorer dragging
opens the wheel. Session history is memory-only. File actions currently cover
copying paths, opening files and opening their containing folder.

## Automated runner verification

The native Windows workflow requires Windows Server 2022 x64 / Python 3.12. It
runs the source suite (including file-lock and Job-object tests), builds a PE32+
AMD64 EXE, and runs expanded packaged smoke checks before and after ZIP extraction.
The extracted test removes the build Python from PATH and isolates configuration.
Images, pypdf, archives and process-tree cancellation are required; optional
FFmpeg/LibreOffice/Poppler absence is explicitly recorded as NOT TESTED skips.
The workflow does not install those engines or infer their Windows correctness
from Linux. Required dependency/native test skips fail the native test gate.

A passing server-runner report would still leave the interactive checks below
open. The first native source-test report is available; packaging is pending a passing run.

## Native acceptance checklist

Every entry below is **NOT TESTED** until a tester records Windows version,
artifact SHA-256, engine versions, steps and result. Automated Qt events do not
establish Explorer OLE behavior.

- Extract on a clean Windows 11 x64 machine with no Python; launch by double click.
- Test DPI scaling 100/150/200%, keyboard navigation, smallest practical window.
- Use native file/folder/output dialogs, multi-select, cancel each dialog.
- Drag one file, several Unicode files and a folder from Explorer into the app.
- Select all wheel wedges, More, Escape, screen edges and multiple monitors.
- Convert transparent PNG to JPEG and each installed image writer; inspect output.
- With trusted optional engines: play encoded audio/video, open Office PDFs,
  inspect PDF raster pages and extracted images; test missing/broken engines.
- Run a long conversion, cancel, verify child processes stop and UI stays responsive.
- Verify batch error/cancel preserves completed outputs and original bytes.
- Repeat output names, locked destinations, write-denied folders and long paths.
- Test corrupt/unsupported files, hostile archives, ZIP/TAR round trip.
- Close during work, wait for cancellation, close again; open history output folder.

Automated native Windows Job/file-lock tests exist in `test_platform.py` and must
pass on a Windows runner. Long paths depend on Windows policy and engine support;
the app does not change that policy. Network share behavior has not been tested.

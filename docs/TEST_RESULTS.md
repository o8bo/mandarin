# Actual test record — 2026-10-23

## Current native Windows result

[Run 39939527182](https://github.com/o8bo/mandarin/actions/runs/39939527182), source `08bcaf537cd39655305fa8f43504337bc4ae8b82`,
**SUCCESS** on Windows Server 2022 x64 / CPython 3.12.10. Source suite:
**32 run, 28 passed, 0 failures/errors, 4 explicit optional-engine skips**.
The portable PE32+ AMD64 executable passed all 12 packaged checks, and the
unpacked ZIP repeated all 12 with build Python removed from PATH. The downloaded
ZIP and EXE hashes were independently checked on the Linux workspace.

| Windows check | Actual result |
|---|---|
| Qt startup / file-selection model | PASS on runner |
| Synthetic Qt local drop / radial mouse and keyboard | PASS on runner |
| Pillow images, Arabic/Japanese names | PASS |
| No-overwrite, collision-safe publication, locked destination | PASS |
| Batch conversion, partial failure/cancellation | PASS |
| Native Job/process-tree cancellation, subprocess errors | PASS |
| pypdf merge/split/rotate; packaged image-to-PDF/rotation | PASS |
| Safe archive processing | PASS |
| PE32+ AMD64 / bundled Python / ZIP extraction and relaunch | PASS |
| FFmpeg audio/video | NOT TESTED — 2 source tests skipped |
| Poppler PDF rasterization | NOT TESTED — 1 source test skipped |
| LibreOffice document conversion | NOT TESTED — 1 source test skipped |
| Interactive Windows 11 / native Explorer OLE / native dialogs | NOT TESTED |
| Fresh no-Python Windows 11 machine, DPI/multiple monitors | NOT TESTED |

Windows ZIP SHA-256:
`37eda3a5ac8095ec1021e265153463553b9da1028cc70b8698b8f9402d81b5a0`.
EXE SHA-256:
`612a51d44a300d958214a55fa8d943002ab69c1a3457dd39b86ef47733216697`.
ZIP size: 49,143,575 bytes; EXE: 3,435,707 bytes.
[Candidate artifact](https://github.com/o8bo/mandarin/actions/runs/39939527182/artifacts/12495452024) ·
[diagnostic reports](https://github.com/o8bo/mandarin/actions/runs/39939527182/artifacts/12495436992).

The following sections preserve the earlier stages and the failed first attempt;
they are historical records, not replacements for the current result above.

Development host: Linux Mint / X11, x86-64, glibc 2.39, system Python 3.12.3.
No Windows host, VM, Wine or Windows runner was available/executed. Windows-native
claims below remain **NOT TESTED**, including shared code when run on Windows.

## Pre-publication baseline results (historical)

| Feature | Linux | Windows |
|---|---|---|
| GUI startup | PASS — GTK and Qt on X11 | NOT TESTED |
| Drag and drop | PASS — real GTK XDND; Qt synthetic local-file events | NOT TESTED — Explorer OLE pending |
| Radial menu | PASS — GTK Convert/Tools/Actions; Qt mouse/keyboard events | NOT TESTED |
| Images | PASS — advertised writers, transparency, Unicode, collision preservation | NOT TESTED |
| Audio/video | PASS — real FFmpeg outputs, trim and WebM tools | NOT TESTED |
| Documents | PASS — real TXT to PDF through LibreOffice | NOT TESTED |
| PDF | PASS — merge/split/rotate and Poppler page rasterization | NOT TESTED |
| Batch processing | PASS — partial failure/cancel retains completed outputs | NOT TESTED |
| Cancellation | PASS — actual process tree, including child ignoring TERM; Qt responsiveness | NOT TESTED — native Job tests pending |
| Filename safety | PASS — no overwrite, Unicode, reserved/ADS/traversal rejection | NOT TESTED — native file-lock test pending |
| Frozen package | PASS — Linux Qt ELF only, unpacked ZIP smoke | NOT TESTED — Windows EXE not built |
| Fresh Windows 11 machine | NOT TESTED / not applicable | NOT TESTED |
| Wayland desktop fallback | NOT TESTED | NOT TESTED / not applicable |

Before changes: existing 12 backend tests PASS; actual GTK XDND conversion wheel
PASS. After changes: **30 tests run, 28 passed, 0 failures, 0 errors, 2 skips**.
Skips are explicitly the native Windows file-lock and suspended-child Job startup
checks. Final pinned-dependency suite: Pillow 12.0.0, pypdf 6.21.2,
PySide6 Essentials/shiboken6 6.10.1. The Linux launcher environment uses system Pillow 10.2.0; its final backend
regression also passed separately (13 tests).

Real engine fixtures include RGBA image writers; audio wave encodes; generated
H.264 video and WebM trim/compress/remove-audio; Unicode document to PDF; generated
PDF merge/split/rotation and raster pages; subtitle timing round trips; ZIP/TAR
round trips and malicious entries. Coverage of these fixtures does not establish
every possible input, font, codec, Office filter or GUI action.

Qt tests exercise selection-dialog wiring with mocked dialog returns, local URL
Qt drag/drop events, wheel mouse/keyboard, numeric options, real corrupt-image
batch results and worker responsiveness during cancellation. Native OS dialog
interaction and Explorer's drag source are separate manual acceptance items.

## Commands actually run

From the application directory (the private development paths are not published):

```bash
# Baseline backend and real GTK/X11 wheel
PYTHONPATH=vendor:. PATH="$PWD/vendor/usr/bin:$PATH" python3 -m unittest -v test_engine
PYTHONPATH=vendor:. PATH="$PWD/vendor/usr/bin:$PATH" python3 test_drag_flow.py

# Final pinned-dependency suite; .venv has requirements-build.txt installed
PYTHONPATH=vendor:. PATH="$PWD/vendor/usr/bin:$PATH" QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/run_tests.py --report verification/tests.json

# All three real X11 wheel modes after changes
PYTHONPATH=vendor:. PATH="$PWD/vendor/usr/bin:$PATH" python3 test_drag_flow.py
PYTHONPATH=vendor:. PATH="$PWD/vendor/usr/bin:$PATH" python3 test_drag_flow.py tools
PYTHONPATH=vendor:. PATH="$PWD/vendor/usr/bin:$PATH" python3 test_drag_flow.py actions

# Target guard: expected refusal / exit 1 on Linux, no Windows artifact
QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/build_portable.py --target windows

# Real Linux frozen app, then smoke after unpacking its ZIP outside the source
QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/build_portable.py --target linux-qt-validation
```

The final automated suite completed in 5.629 seconds. Real GTK XDND after changes
selected `image:jpeg`, `image:resize` and verified clipboard paths in Actions.
GTK main-window startup/Unicode selection also passed. Qt main window and wheel
were rendered/captured through native XCB on Linux; all six Qt tests also passed
on XCB in 2.153 seconds. Screenshots are labeled Linux.
The host lacked libxcb-cursor0, so the official Ubuntu package was extracted
privately for this diagnostic. It was not installed system-wide or bundled into
a claimed Linux release.

The Linux ZIP was extracted into a temporary directory and launched with PATH
empty and PYTHONPATH/PYTHONHOME removed. Frozen GUI startup, Unicode PNG→JPEG and
selection-model smoke passed. This verifies a Linux packaged runtime, not Windows.

## Failures encountered and resolution

- LibreOffice could not start inside the restricted development sandbox. The
  same real fixture passed outside that sandbox; final suite ran there.
- First Linux freeze attempt inherited a broken distro pkg_resources/jaraco hook.
  Frozen startup correctly failed and the builder emitted no ZIP. Rebuilding in
  an isolated venv resolved it; the final frozen/unpacked smoke passed. The
  original failure log remains local rather than being hidden.
- Native Qt XCB startup first failed because libxcb-cursor0 was missing. Supplying
  the official library privately enabled native Linux rendering.

Machine logs, original backup and full local reports are in ignored `verification/`;
none contains personal conversion fixtures and they are excluded from the source
candidate. CI workflows have been prepared but **have not run**. Missing optional
Windows engines will produce explicit skips in CI; review logs before declaring
Windows media/doc/PDF utility coverage. See WINDOWS.md for manual acceptance.

## Publication-readiness follow-up — actual local results

No Windows runner was executed in this follow-up. The historical Linux results
above remain the baseline; completed Linux development was not repeated.

New checks actually executed on Linux:

```bash
.venv/bin/python -m unittest -v test_build_tools
QT_QPA_PLATFORM=offscreen .venv/bin/python -m mandarin --self-test verification/expanded-source-smoke.json
QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/build_portable.py --target linux-qt-validation
```

- Two new build-verification tests: **2 PASS** (reject ELF/truncated/x86 PE headers,
  malicious portable ZIP paths and case-colliding entries before extraction).
- Expanded source smoke: **12 checks PASS**, including real PDF image/rotation,
  Arabic/Japanese filenames, no overwrite/collisions, batch processing/partial
  cancellation, ZIP safety, missing dependencies and actual child-process cleanup.
- Expanded frozen Linux smoke: **12 checks PASS**.
- Extracted Linux ZIP with build Python removed from PATH: **12 checks PASS**,
  checksum/extraction/bundled runtime launch PASS. This is a Linux ELF, not an EXE.

The automated suite now includes 32 test cases (the former 30 plus the two build
tests). This does **not** mean 32 Windows cases passed: the Windows workflow has
not run. On Windows, `scripts/run_tests.py --require-windows` refuses non-Windows
hosts and treats required dependency/native-test skips as failures. Only explicit
optional FFmpeg/LibreOffice/Poppler skips are allowed and reported as NOT TESTED.

The packaging builder now verifies PE32+ AMD64 headers, copies required runtime
and notices, performs the expanded frozen checks, creates the ZIP/checksum,
extracts it into an independent Unicode working directory, and repeats its own
runtime smoke without the build Python on PATH. Windows packaging and native
DLL presence checks remain **NOT TESTED** until a real Windows run succeeds.

Actions tags/Node runtimes and the currently supported Windows x64 runner label
were checked against official sources; exact immutable pins and the outstanding
push/dispatch dependency are recorded in PUBLICATION.md. Reports and local build
logs remain ignored in `verification/`. No public source or release was pushed.

Follow-up static validation: both workflows passed actionlint v1.7.12 (official
release binary, published SHA-256 checked) and YAML/action-pin/permissions checks.
The native-only test guard refused Linux as expected; no Windows test JSON or EXE
was created. The publication index scan reviewed 243 source/notice/document files
and found no configured secret/private-path patterns or unexpected binaries;
the only binaries are the two generated UI PNGs. This scan is supplemental,
not a complete security guarantee. Upstream notices remain verbatim; whitespace
checks are scoped to Mandarin's own code/docs to preserve those license texts.

## First actual native Windows run — 2026-10-23

The earlier NOT TESTED statements describe the pre-publication stage. After
explicit owner approval, the initial commit was pushed unchanged to the public
[o8bo/mandarin](https://github.com/o8bo/mandarin) repository and workflow
[39938803037](https://github.com/o8bo/mandarin/actions/runs/39938803037) ran on
Windows Server 2022 x64 / CPython 3.12.10. Required native Job-object startup,
process-tree cancellation, file-lock/no-overwrite and most Qt tests passed.
The run **failed**: 32 cases, 4 failure records (including subtest records),
1 error and 4 explicit optional-engine skips. Packaging correctly did not run.

Verified problems addressed for the next attempt:

- Subtitle fixture text used the Windows cp1252 default instead of explicit UTF-8.
- Windows ZipInfo normalizes backslashes when creating/reading entries. Malicious
  fixtures now preserve raw header names and validators inspect `orig_filename`
  before normalization; no archive rejection assertion was removed.
- Qt worker completion timed out under a Python loop calling QTest.qWait. Tests
  now use a real nested Qt event loop, retain the same 10-second assertion limit,
  and include the worker stack on timeout. Native rerun will establish the fix.
- Test reports now count unique failed cases when several subtests fail, while
  retaining all individual failure records and tracebacks.

The original failed logs and diagnostics remain locally under `verification/` and
in the linked GitHub run. FFmpeg (two tests), Poppler rasterization (one test) and
LibreOffice (one test) were absent and explicitly skipped, not treated as passed.
Local targeted regression after the fixes: 10 cases PASS. Native rerun pending.

## Successful native rerun

The raw ZIP-name, explicit UTF-8 fixture and Qt event-loop fixes were verified
on Windows in the linked successful rerun. No assertions were removed and the
Qt worker deadline stayed 10 seconds. Required tests passed; the four optional
converter skips remain visible. The runner also confirmed its Windows x64 host,
PE architecture, bundled runtime components, SHA-256, safe extraction and both
functional smoke reports. Complete build/test logs and original JSON reports
are retained locally in ignored `verification/` and in the linked run/artifacts.
The compiled Windows executable was not run on Linux.

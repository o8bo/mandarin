# First GitHub push and Windows CI — v0.1.0 candidate

## 1. Repository

Public repository: https://github.com/o8bo/mandarin . The owner explicitly
approved public publication and requested the name without a Linux suffix.
The initial approved commit `dc41d349237cdc78739e2ded40f88d6a217bc9ea` was pushed
unchanged. Verified Windows fixes followed in `08bcaf537cd39655305fa8f43504337bc4ae8b82`.
History was preserved; no force push, final tag or GitHub Release was created.
The remote SHA was compared with local Git; publication audit checked every blob.

## 2. Changes and failures fixed

The first native run exposed explicit-UTF-8 fixture omissions, ZipInfo's Windows
filename normalization and a Qt test wait that starved Python workers. Fixes
preserve raw ZIP header names before validation, use UTF-8 fixtures and pump a
real Qt event loop without extending the 10-second deadline. Reports retain all
failure/subtest records and count unique failing cases accurately. Linux GTK/X11
and the existing conversion paths remain intact. Original failure evidence stays
available; no test assertion or required failure was suppressed.

## 3. Workflow

Successful manual run:
https://github.com/o8bo/mandarin/actions/runs/39939527182 .
Real GitHub-hosted Windows Server 2022 x64, Python 3.12.10, SHA-pinned Node 24
Actions. Read-only repository permissions; no release or tag operation.
First failed run: https://github.com/o8bo/mandarin/actions/runs/39938803037 .

## 4. Actual tests

32 source tests: **28 PASS, 0 failures/errors, 4 explicit skips**. The skips are
2 FFmpeg tests, 1 Poppler rasterization and 1 LibreOffice document test; these
engines were absent. Required native Job startup, process tree, file-lock/no-
overwrite, Unicode, PDF/image/archive/batch and Qt tests passed.

Both packaged and extracted-ZIP runtime reports passed **12/12 checks**:
image conversion, Arabic/Japanese filenames, original preservation/collisions,
batches and partial cancellation, PDF generation/rotation, safe archives,
missing dependencies, process-tree cancellation, nonzero subprocess errors and
Qt startup/selection. Extracted execution removed build Python from PATH and
isolated configuration. Actual results and limits: TEST_RESULTS.md.

## 5. EXE status

**BUILT AND AUTOMATICALLY VERIFIED on Windows Server 2022 x64.**
`Mandarin/Mandarin.exe` is PE32+ AMD64, 3,435,707 bytes. Python 3.12 and required
Qt/Pillow/pypdf files are bundled. No separate Python installation is required
for the portable application. Fresh Windows 11 desktop acceptance is separate.

## 6. Download and checksums

Candidate artifact:
https://github.com/o8bo/mandarin/actions/runs/39939527182/artifacts/12495452024 .
Diagnostics:
https://github.com/o8bo/mandarin/actions/runs/39939527182/artifacts/12495436992 .
Artifacts expire 2026-11-22; these are not a GitHub Release.

Portable `Mandarin-Windows-x64.zip`: 49,143,575 bytes, SHA-256
`37eda3a5ac8095ec1021e265153463553b9da1028cc70b8698b8f9402d81b5a0`.
EXE SHA-256:
`612a51d44a300d958214a55fa8d943002ab69c1a3457dd39b86ef47733216697`.
The downloaded archive was independently hashed/extracted, its PE inspected and
its EXE hash matched to native reports. Local copy:
`dist/Mandarin-Windows-x64.zip` with checksum. Updated source candidate:
`dist/mandarin-v0.1.0-rc-source.zip`. Neither binary ZIP is committed to Git.

## 7. Remaining manual acceptance

**NOT TESTED:** interactive Windows 11, actual Explorer OLE drops, native dialogs,
DPI/multiple monitors, fresh no-Python Windows 11 machine, extreme/denied/network
paths and optional FFmpeg/LibreOffice/Poppler conversions. The automated Qt drop
is synthetic, not real Explorer acceptance. No desktop-wide Windows hook/tray
or registry context menu is installed. WINDOWS.md contains the full checklist.

## 8. Installation

Download the Actions artifact (GitHub sign-in may be required), extract its outer
ZIP, verify the inner portable ZIP against `.sha256`, then extract it and launch
`Mandarin/Mandarin.exe`; keep `_internal` and `licenses` together. Python is
bundled. External engines are optional and configured via Engines & settings.
Linux Mint continues using its apt dependencies and `./launch.sh` (GTK default).
Source and workflow details are in BUILDING.md and PUBLICATION.md.

## 9. Publication state and next gate

Public source push and first successful Windows CI build are complete. No further
publication approval is needed for the already approved source/CI work. No final
v0.1.0 tag or GitHub Release has been created. The remaining acceptance gate is
a real Windows 11 tester following WINDOWS.md; the CI result does not certify
full Windows 11 GUI compatibility. Documentation-only updates may follow the
artifact's source commit; see Git history for that distinction.

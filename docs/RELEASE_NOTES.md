# v0.1.0 release candidate — unpublished

- Retains Linux Mint GTK and desktop X11 drag wheel.
- Adds Windows-targeted PySide6 desktop frontend, in-app radial menu, native
  local-file drop handling, batch/output settings and session history.
- Shares conversions, portable archive validation, encoder discovery and safe
  publication. Adds Windows executable discovery and Job-object cancellation.
- Adds real Qt integration, process-tree and document tests.
- Adds SHA-pinned current GitHub Actions, native Windows test gating, PE32+
  inspection, expanded frozen checks, ZIP extraction/relaunch, diagnostic reports,
  licenses and checksums.
- Reviews public source separately from retained local investigation evidence;
  prepares an initial local commit without pushing or publishing.

This is a development candidate. [Native Windows Server CI](https://github.com/o8bo/mandarin/actions/runs/39939527182) passed
28 automated tests with 4 explicit optional-engine skips, built a PE32+ AMD64
portable ZIP, and passed 12 frozen checks before and after extraction. The initial
failed run remains documented. Fresh Windows 11, Explorer dragging, native dialogs,
DPI/multiple-monitor acceptance and optional external converters remain untested.
No GitHub Release or final v0.1.0 tag has been published. See TEST_RESULTS.md and
WINDOWS.md for scope, checksum and remaining acceptance gates.

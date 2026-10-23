# Windows verification and first-publication readiness — v0.1.0 candidate

## 1. Git repository status

Initial local commit prepared after review of the actual Git index blobs. See
`git log -1` for its SHA and `git status --short` for current changes. The branch
is `main`; no remote, push, final release tag or GitHub release is configured.
Project-only attribution avoids exposing a personal email address.

## 2. Changes made

Retained the working Linux GTK/X11 frontend and conversion engine. Hardened the
Windows build/verification workflow, pinned current official Actions to SHA,
added PE/ZIP rejection checks, expanded source/frozen runtime smoke, and added
extracted-archive launch verification. Historical local investigation files are
excluded from publication while remaining on disk. MIT/license provenance,
README, build/setup/test documentation and artifact instructions were reviewed.
The staged-source checker audits actual blobs, modes, sizes, binary content,
secret patterns/private paths and the publication allowlist.

## 3. Windows workflow readiness

Manual `build-windows.yml` targets the currently supported `windows-2022` x64
GitHub-hosted runner and Python 3.12 x64. It runs native tests, requires bundled
Python/PDF/image libraries, creates PE32+ AMD64 output, tests frozen startup and
functional operations, then verifies checksum/unpacking and repeats runtime
checks without the build Python on PATH. Required failures fail the job; logs,
JSON and a summary survive failure. Optional external engines are not bundled;
missing-engine conversions remain explicit skips. See PUBLICATION.md for exact
current action versions/SHAs and official references.

## 4. Exact Windows automated results

**NOT EXECUTED. No Windows test results exist.** The workflow has not been
pushed/dispatched and no native Windows host is available in this workspace.
No Linux result has been reclassified as a Windows result. New local checks:
2 build-tool tests PASS, expanded source/frozen/unpacked Linux smoke each 12
checks PASS. The prior documented Linux tests remain valid historical evidence.

## 5. Windows EXE status

**NOT BUILT.** A genuine Windows executable is gated on execution of the native
Windows build workflow (or a Windows machine following BUILDING.md). The Linux
builder refuses Windows output. Automated GUI smoke will not certify Explorer
OLE drag/drop, native dialogs or clean Windows 11 desktop acceptance.

## 6. Artifacts

Local source candidate:
`dist/mandarin-linux-v0.1.0-rc-source.zip`, with `.zip.sha256` and an internal
per-file manifest. No private runtime, vendor binary, Git data or logs are in it.

Local packaging diagnostic only:
`dist/Mandarin-Linux-Qt-validation.zip` and `.zip.sha256`;
`dist/Mandarin-Linux-Qt-validation-portable-verification.json` reports the
actual Linux frozen/unpacked checks. It is not a Windows distribution.

Expected Windows success paths (not present yet):
`dist/Mandarin/Mandarin.exe`, `dist/Mandarin-Windows-x64.zip`, `.zip.sha256`,
`dist/Mandarin-smoke.json`, `dist/Mandarin-portable-verification.json`,
`dist/Mandarin-portable-verification-smoke.json`,
`verification/windows-tests.json`. Actions artifacts will be named
`Mandarin-Windows-x64-candidate` and `Mandarin-Windows-diagnostics`.

## 7. Remaining acceptance tests

Native Windows source tests, PE/runtime build and ZIP launch remain unexecuted.
Interactive Windows 11 with no Python, native Explorer drops/dialogs, DPI and
multiple monitors, long/locked/denied paths, optional FFmpeg/LibreOffice/Poppler
conversions and final dependency/license inventory remain pending. WINDOWS.md
lists the exact manual checklist. No desktop-wide Windows wheel or tray is
provided. Linux defaults and existing Wayland fallback design remain unchanged.

## 8. Publication instructions

After explicit owner approval, create the empty public `mandarin-linux`
repository, push the existing `main` commit without force, confirm the default
branch, then manually run **Build Windows portable candidate**. Read actual tests,
skips and diagnostic artifacts before downloading the candidate. Verify SHA-256,
extract both the outer Actions artifact and inner portable ZIP, and launch
`Mandarin/Mandarin.exe`. Python is bundled for end users; optional external engines
need separate installation/configuration. PUBLICATION.md contains all steps.
Do not create a final v0.1.0 release or advertise Windows verification prematurely.

## 9. Blocker requiring owner intervention

The GitHub-hosted Windows workflow must first be pushed to a repository's default
branch. Public visibility is not technically required, but the owner has barred
any push/publication without explicit approval. No temporary repository was
created to bypass that boundary. Approval to create/push `mandarin-linux` is the
remaining publication prerequisite; a Windows host is the offline alternative.

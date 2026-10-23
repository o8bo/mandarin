# Publication and Windows build readiness — 2026-10-23

## Current state

v0.1.0 is a release candidate with **no GitHub Release or final tag**. Public
repository: [o8bo/mandarin](https://github.com/o8bo/mandarin), approved by the owner
with the name requested without a Linux suffix. The original initial commit
`dc41d349237cdc78739e2ded40f88d6a217bc9ea` was pushed unchanged; verified fixes
followed without history rewriting. The [successful native Windows run](https://github.com/o8bo/mandarin/actions/runs/39939527182)
built source `08bcaf537cd39655305fa8f43504337bc4ae8b82` on Windows Server 2022 x64:
**32 tests, 28 passed, 4 optional-engine skips**, and 12/12 functional checks in
both the frozen and extracted-ZIP reports. Source/EXE/ZIP hashes are recorded in
TEST_RESULTS.md. Physical Windows 11 and Explorer acceptance remain NOT TESTED.
Documentation-only updates may follow the compiled artifact's source commit.

## Publication review

The actual staged Git blobs are checked with `python3 scripts/review_staged.py`.
The check compares the index to the source allowlist, reviews file modes/sizes,
restricts binary files to generated PNG screenshots, and scans private-key/token
patterns, credential literals and private local paths. It fails on unexpected
files or differences between staged/working source. Pattern checks supplement
human source review; they are not a proof against every possible secret.

The existing MIT license remains unchanged. Third-party notices/provenance are
retained and are separately licensed. The two PNGs depict generated fixtures in
Mandarin's own Linux Qt windows. No shipped proprietary application/assets,
optional conversion binaries, runtime folders, personal input files or machine
reports belong to the public Git tree. Historical investigation/evidence files
are retained locally but excluded from Git and the source ZIP. Architecture
and data-flow documentation for Mandarin remains public.

## Verified Actions versions and runner

Official release tags and exact source commits were resolved through GitHub's
API and their action.yml files checked on 2026-10-23:

| Action | Version | Pinned commit |
|---|---|---|
| [checkout](https://github.com/actions/checkout/releases/tag/v7.0.1) | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| [setup-python](https://github.com/actions/setup-python/releases/tag/v7.1.0) | v7.1.0 | `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` |
| [upload-artifact](https://github.com/actions/upload-artifact/releases/tag/v7.0.2) | v7.0.2 | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` |

All use Node 24. `windows-2022` is a currently listed GitHub-hosted Windows Server
2022 **x64** runner in the [official runner inventory](https://github.com/actions/runner-images).
It is not an interactive Windows 11 desktop. Both workflows use these immutable
pins. The build workflow is manual, has contents:read, does not persist checkout
credentials, and contains no release/deployment/tag operation. Update pins after
review as official versions change.

## Actual native execution

Publication approval, repository creation and the first source push are complete.
The [first Windows attempt](https://github.com/o8bo/mandarin/actions/runs/39938803037)
failed at required tests; its logs/diagnostics are preserved. Verified fixes led
to the successful run above. No required failure was bypassed. FFmpeg, Poppler
rasterization and LibreOffice absence remains visible in the four explicit skips.
Workflow dispatch uses the default branch as [required by GitHub](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

## Repeatable publication/build procedure

1. The public `o8bo/mandarin` repository already exists. Preserve the existing
   history; do not reinitialize it or force-push.
2. `origin` is configured and `main` is the default. Normal reviewed pushes
   retain the existing initial commit and successful build source.
   Do not push a final v0.1.0 tag or publish a release yet.
3. Open **Actions → Build Windows portable candidate → Run workflow → main**.
   If Actions is disabled, enable it through the repository's approved settings.
4. Wait for required native tests and the build/ZIP verification step. Read the
   actual JSON reports, failure log and job summary. Record run URL, source SHA,
   runner version, test totals, skip reasons, artifact checksum and result.
5. Fix real failures, rerun and update README/TEST_RESULTS.md with evidence.
   A green workflow alone must not change Explorer/fresh Windows 11 to PASS.
6. Download the candidate and complete WINDOWS.md on Windows 11 x64. Audit the
   resulting DLL/license inventory and signing status. Only after those results
   and a separate release approval should a public v0.1.0 release be considered.

The first approved push is complete. No final tag or GitHub Release has been created.

## Download the Windows artifact

The verified candidate is available in [run 39939527182](https://github.com/o8bo/mandarin/actions/runs/39939527182).
[Download candidate](https://github.com/o8bo/mandarin/actions/runs/39939527182/artifacts/12495452024) ·
[download diagnostics](https://github.com/o8bo/mandarin/actions/runs/39939527182/artifacts/12495436992).
These artifacts expire 2026-11-22 and are not a GitHub Release.

Portable ZIP SHA-256:
`37eda3a5ac8095ec1021e265153463553b9da1028cc70b8698b8f9402d81b5a0`.
The outer Actions artifact has its own separate digest; compare the inner ZIP
against the accompanying `.zip.sha256` file rather than the outer digest.

Download procedure:

- Open its Actions run and download **Mandarin-Windows-x64-candidate** under
  Artifacts. GitHub may require sign-in. Artifacts expire after 30 days.
- Extract the downloaded Actions ZIP; it contains `Mandarin-Windows-x64.zip`
  and `Mandarin-Windows-x64.zip.sha256`.
- In PowerShell, calculate `Get-FileHash .\Mandarin-Windows-x64.zip -Algorithm SHA256`
  and compare it with `Get-Content .\Mandarin-Windows-x64.zip.sha256`.
- Extract that inner portable ZIP to a user-writable directory. Launch
  `Mandarin\Mandarin.exe` and keep `_internal` and `licenses` with it. Python is
  bundled. No Python installation is required for end users.
- Download **Mandarin-Windows-diagnostics** separately for test JSON, resolved
  dependencies, build log, both frozen reports and the ZIP verification report.
  Diagnostics are retained even on failed builds; a diagnostics artifact is not
  a verified executable artifact.

On the runner, success paths are `dist/Mandarin/Mandarin.exe`,
`dist/Mandarin-Windows-x64.zip`, its checksum, `dist/Mandarin-smoke.json`,
`dist/Mandarin-portable-verification.json`,
`dist/Mandarin-portable-verification-smoke.json`, and
`verification/windows-tests.json`. The downloaded portable ZIP/checksum are also retained locally under ignored
`dist/`, with actual reports/logs under ignored `verification/`.
Optional external engines and remaining manual tests are listed in WINDOWS.md.

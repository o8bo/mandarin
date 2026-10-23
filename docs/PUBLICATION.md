# Publication and Windows build readiness — 2026-10-23

## Current state

v0.1.0 is a release candidate with **no GitHub Release or final tag**. The owner
approved public publication under [o8bo/mandarin](https://github.com/o8bo/mandarin).
The existing initial commit `dc41d349237cdc78739e2ded40f88d6a217bc9ea` was pushed
without rewriting history and the remote SHA matched exactly. Linux GTK/X11 has
the documented verified behavior. The [first native Windows run](https://github.com/o8bo/mandarin/actions/runs/39938803037)
failed at source tests; fixes/build verification are in progress. No verified
Windows ZIP or interactive Windows 11 acceptance result exists yet.

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

## Publication authorization and native execution

The publication/push approval prerequisite has been satisfied. The workflow now
runs on the real GitHub-hosted Windows executor. The initial run stopped before
packaging because required tests failed; those failures are retained rather than
bypassed. Current results and remaining gates are recorded in TEST_RESULTS.md.
Workflow dispatch uses the default branch as [required by GitHub](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

## Repeatable publication/build procedure

1. Create the public `mandarin` repository with **no generated README,
   license, .gitignore or initial commit**, since those exist locally. Confirm
   the intended owner. Preserve the existing local commit; do not force-push.
2. Add that repository as origin, push `main`, and confirm `main` is the default.
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

**No Windows artifact is available yet.** Following a successful approved run:

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
`verification/windows-tests.json`. These Windows files do not exist locally.
Optional external engines and remaining manual tests are listed in WINDOWS.md.

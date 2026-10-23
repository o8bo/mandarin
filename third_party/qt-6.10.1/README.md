# Upstream Qt/PySide notices

Collected from the exact official v6.10.1 QtBase, QtSvg and PySide source tags.
PROVENANCE.json records source URLs, archive SHA-256 and notice counts.
The collection includes top-level license texts, attribution JSON and upstream
files referenced by LicenseFile/CopyrightFile (some notices live in headers).
It includes notices for additional source components beyond the app's imports;
inclusion of a notice does not imply that component's binary is distributed.
ICU 73.2 notices cover the ICU 73 shared libraries in the Linux Qt wheel.

The one-directory build copies these notices and the package/Python license
files into its `licenses/` folder. Keep libraries replaceable and retain these
notices when redistributing. Review the exact target artifact's dependency
inventory before releasing; a Linux inventory does not establish Windows DLL
license coverage. The Windows build and final redistribution review are pending.

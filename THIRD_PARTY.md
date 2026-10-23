# Third-party components and distribution

Mandarin's existing MIT license covers its own source and original icon only.
This project is independent of Tangerine; no Tangerine code/assets are included.
The local Linux development `vendor/` directory is excluded from public source
archives. Source requirements install the following independently licensed code:

| Component | Use | License / source |
|---|---|---|
| Pillow 12.0.0 (Linux system 10.2 also tested) | Images | MIT-CMU / HPND; https://github.com/python-pillow/Pillow |
| pypdf 6.21.2 | PDF | BSD-3-Clause; https://github.com/py-pdf/pypdf |
| PySide6 Essentials / shiboken6 6.10.1 and Qt | Windows GUI | LGPLv3/GPLv3 or commercial, module-dependent; https://doc.qt.io/qtforpython-6/licenses.html |
| PyInstaller 6.16.0 | Build tool/bootloader | GPLv2+ with distribution exception; https://pyinstaller.org/en/stable/license.html |
| Python 3.12 | Portable runtime | PSF and included notices; https://docs.python.org/3/license.html |
| GTK/PyGObject/Cairo | Linux system GUI | Upstream LGPL-family licenses; system packages |
| FFmpeg | Optional installed media engine | LGPL/GPL depending on build; https://ffmpeg.org/legal.html |
| LibreOffice | Optional installed document engine | MPLv2/LGPLv3+ and third-party terms; https://www.libreoffice.org/about-us/licenses/ |
| Poppler | Optional installed PDF utilities | GPLv2/GPLv3; https://poppler.freedesktop.org/ |

Portable builds dynamically bundle Python, Qt, Pillow, pypdf and their wheel
libraries. The builder copies package license/notice files plus Python's license
into `licenses/`, adds the exact Qt/PySide upstream license/attribution collection
from `third_party/qt-6.10.1/`, and leaves shared Qt libraries replaceable in the one-directory
distribution. The unmodified Qt/PySide source for the exact bundled version is
available from https://download.qt.io/official_releases/QtForPython/pyside6/ .
Retain all upstream notices, Qt module notices and applicable source/relinking
rights when redistributing. Do not add restrictions preventing library
replacement or reverse engineering for debugging modifications under the LGPL.
Review the generated licenses and full dependency inventory before public release.

FFmpeg, LibreOffice and Poppler are not bundled by the new portable builder;
users select their own trusted installed executable. If adding these binaries
later, fulfill the obligations of the specific build, including corresponding
source where required; the app's MIT license does not override those terms.

The pre-port private Linux vendor used Ubuntu FFmpeg `7:6.1.1-3ubuntu5` and pypdf
6.21.2. Its provenance/notices remain locally in `vendor/`; this is not a portable
Windows distribution. FFmpeg Ubuntu source:
https://launchpad.net/ubuntu/+source/ffmpeg/7:6.1.1-3ubuntu5 .

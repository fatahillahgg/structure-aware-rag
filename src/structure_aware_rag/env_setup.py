"""Ensures Tesseract OCR and Poppler are resolvable on PATH before unstructured
imports them. Only needed on Windows where these ship as external installs
(via winget) rather than Python packages, and PATH changes from an installer
don't reach a shell that was already open when it ran.
"""

import os
import shutil
from pathlib import Path

_CANDIDATE_DIRS = [
    Path(r"C:\Program Files\Tesseract-OCR"),
    Path(
        os.path.expandvars(
            r"%LOCALAPPDATA%\Microsoft\WinGet\Packages"
            r"\oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe"
        )
    ),
]


def ensure_ocr_tools_on_path() -> None:
    if shutil.which("tesseract") and shutil.which("pdftoppm"):
        return

    for base in _CANDIDATE_DIRS:
        if not base.is_dir():
            continue
        for bin_dir in {base, *base.glob("*/Library/bin")}:
            if bin_dir.is_dir() and str(bin_dir) not in os.environ["PATH"]:
                os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]

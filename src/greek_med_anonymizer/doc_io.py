from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from greek_med_anonymizer.docx_io import extract_docx_text


CONVERSION_TIMEOUT_SECONDS = 120

# Fallback decodings for legacy Greek text that is not valid UTF-8.
TEXT_ENCODINGS = ("utf-8", "utf-8-sig", "cp1253", "iso-8859-7", "cp1252", "latin-1")

_LIBREOFFICE_CANDIDATES = (
    "soffice",
    "libreoffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/bin/soffice",
    "/usr/local/bin/soffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
)


def decode_text_bytes(raw: bytes) -> str:
    """Decode text that may be UTF-8 or a legacy Greek/Windows codepage."""
    for encoding in TEXT_ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def sniff_document_kind(path: str | Path) -> str:
    """Identify what a file really is, regardless of its extension.

    Returns one of: "ooxml" (a .docx in disguise), "ole2" (a real legacy .doc),
    "rtf", or "text".
    """
    with open(path, "rb") as handle:
        magic = handle.read(8)

    if magic.startswith(b"PK\x03\x04"):
        return "ooxml"
    if magic.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "ole2"
    if magic.startswith(b"{\\rt"):
        return "rtf"
    return "text"


def _find_libreoffice() -> str | None:
    for candidate in _LIBREOFFICE_CANDIDATES:
        is_path = os.sep in candidate or "\\" in candidate
        if is_path:
            if Path(candidate).exists():
                return candidate
            continue
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _run(command: list[str]) -> bool:
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=CONVERSION_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def _convert_with_libreoffice(source: Path, out_dir: Path) -> Path | None:
    binary = _find_libreoffice()
    if binary is None:
        return None

    # LibreOffice refuses to run headless while a desktop instance holds the
    # default profile, so give it a private one.
    profile_dir = out_dir / "_lo_profile"
    profile_uri = Path(profile_dir).absolute().as_uri()

    ok = _run(
        [
            binary,
            "--headless",
            "--norestore",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to",
            "docx",
            "--outdir",
            str(out_dir),
            str(source),
        ]
    )
    if not ok:
        return None

    converted = out_dir / (source.stem + ".docx")
    return converted if converted.exists() else None


def _convert_with_textutil(source: Path, out_dir: Path) -> Path | None:
    """macOS only. textutil ships with the OS, so this needs no install."""
    if shutil.which("textutil") is None:
        return None

    converted = out_dir / (source.stem + ".docx")
    ok = _run(
        [
            "textutil",
            "-convert",
            "docx",
            "-output",
            str(converted),
            str(source),
        ]
    )
    if not ok:
        return None

    return converted if converted.exists() else None


def _extract_with_textutil_text(source: Path, out_dir: Path) -> str | None:
    """Last-resort macOS path: convert straight to plain text.

    Lower fidelity than the docx route (headers and footers are dropped), but
    it works when textutil cannot produce docx for a particular file.
    """
    if shutil.which("textutil") is None:
        return None

    converted = out_dir / (source.stem + ".txt")
    ok = _run(
        [
            "textutil",
            "-convert",
            "txt",
            "-encoding",
            "UTF-8",
            "-output",
            str(converted),
            str(source),
        ]
    )
    if not ok or not converted.exists():
        return None

    text = decode_text_bytes(converted.read_bytes())
    return text if text.strip() else None


def _extract_with_antiword(source: Path) -> str | None:
    binary = shutil.which("antiword")
    if binary is None:
        return None

    try:
        completed = subprocess.run(
            [binary, "-m", "UTF-8.txt", str(source)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=CONVERSION_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    return decode_text_bytes(completed.stdout)


def extract_doc_text(doc_path: str | Path) -> str:
    """Read text from a legacy Word ``.doc`` file.

    Legacy ``.doc`` is a binary format that cannot be unzipped like ``.docx``,
    so it is converted first. Converters are tried in order of fidelity;
    LibreOffice preserves headers and footers, which may carry identifying
    details, so it is preferred when installed.
    """
    source = Path(doc_path)
    kind = sniff_document_kind(source)

    # Some files named .doc are really something else. Handle those directly.
    if kind == "ooxml":
        return extract_docx_text(source)
    if kind == "text":
        return decode_text_bytes(source.read_bytes())

    with tempfile.TemporaryDirectory() as temp_dir_name:
        out_dir = Path(temp_dir_name)

        # Copy in under a safe name: converters key the output on the stem.
        staged = out_dir / f"input{source.suffix.lower() or '.doc'}"
        shutil.copyfile(source, staged)

        for converter in (_convert_with_libreoffice, _convert_with_textutil):
            converted = converter(staged, out_dir)
            if converted is not None:
                return extract_docx_text(converted)

        textutil_text = _extract_with_textutil_text(staged, out_dir)
        if textutil_text is not None:
            return textutil_text

        antiword_text = _extract_with_antiword(staged)
        if antiword_text is not None:
            return antiword_text

    raise RuntimeError(
        f"Could not read '{source.name}'. Reading legacy .doc files needs a converter "
        "that is not installed on this computer.\n"
        "Either install LibreOffice from https://www.libreoffice.org/download/ and try again, "
        "or open the file in Word and use File > Save As to save it as .docx."
    )

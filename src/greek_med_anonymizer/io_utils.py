from __future__ import annotations

from pathlib import Path

from greek_med_anonymizer.doc_io import decode_text_bytes, extract_doc_text
from greek_med_anonymizer.docx_io import extract_docx_text


def collect_input_files(input_path: str | Path, glob_pattern: str) -> list[Path]:
    path = Path(input_path)
    if path.is_file():
        return [path]
    return sorted(candidate for candidate in path.rglob(glob_pattern) if candidate.is_file())


def build_output_path(input_file: Path, input_root: Path, output_root: Path, suffix: str) -> Path:
    relative_path = input_file.relative_to(input_root) if input_root.is_dir() else Path(input_file.name)
    output_file = output_root / relative_path
    output_file = output_file.with_suffix("")
    return output_file.with_name(output_file.name + suffix)


def read_input_text(path: str | Path) -> str:
    input_path = Path(path)
    suffix = input_path.suffix.lower()
    if suffix == ".docx":
        return extract_docx_text(input_path)
    if suffix == ".doc":
        return extract_doc_text(input_path)
    # Plain text may be UTF-8 or a legacy Greek codepage such as cp1253.
    return decode_text_bytes(input_path.read_bytes())

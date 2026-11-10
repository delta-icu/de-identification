"""Find the model folder, downloading it from Google Drive the first time.

Used by the web app and the Colab notebook, so both run the same model.
Choose a model with the GREEK_ANON_MODEL environment variable; the default is
DEFAULT_MODEL.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
from urllib.parse import parse_qs, urlparse
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS_ROOT = PROJECT_ROOT / "models"

# name -> Google Drive share link ("Anyone with the link") of either the model
# folder itself or a .zip with the model folder inside.
MODELS: dict[str, str | None] = {
    # XLM-R, 25 original + 40 synthetic reports, gold v2 (the local hospital is
    # PHI), threshold and word snapping stored in final_config.json.
    "xlmr_k40_s0_gold2_r2": None,
    # The model of the first release (gold v1, argmax, no word snapping).
    "xlmr_phi_final": "https://drive.google.com/file/d/1RIHFqp5Xke7t5JtMuXJBhoR_gqEVUoO_/view?usp=share_link",
}
DEFAULT_MODEL = "xlmr_k40_s0_gold2_r2"

REQUIRED_FILES = {"config.json", "tokenizer.json", "tokenizer_config.json"}
WEIGHT_FILES = {"model.safetensors", "pytorch_model.bin"}


def selected_model_name() -> str:
    return os.environ.get("GREEK_ANON_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def is_valid_model_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    names = {child.name for child in path.iterdir() if child.is_file()}
    return REQUIRED_FILES.issubset(names) and bool(names & WEIGHT_FILES)


def find_model_dir(root: Path) -> Path | None:
    """The shallowest valid model folder under ``root`` (``root`` included)."""
    candidates = [root] + [p for p in root.rglob("*") if p.is_dir()]
    valid = [p for p in candidates if is_valid_model_dir(p)]
    return min(valid, key=lambda p: len(p.parts)) if valid else None


def gdrive_download_url(share_link: str) -> str:
    parsed = urlparse(share_link)
    parts = [part for part in parsed.path.split("/") if part]
    if "d" in parts:
        index = parts.index("d") + 1
        if index < len(parts):
            return f"https://drive.google.com/uc?id={parts[index]}"
    query_id = parse_qs(parsed.query).get("id")
    if query_id:
        return f"https://drive.google.com/uc?id={query_id[0]}"
    raise ValueError(f"Unsupported Google Drive share link: {share_link}")


def ensure_model_dir(name: str | None = None, models_root: Path | None = None) -> Path:
    """Return the folder of model ``name``, downloading it if it is missing."""
    name = name or selected_model_name()
    models_root = Path(models_root) if models_root else MODELS_ROOT
    target = models_root / name
    if is_valid_model_dir(target):
        return target

    if name not in MODELS:
        known = ", ".join(sorted(MODELS))
        raise FileNotFoundError(
            f"Model '{name}' was not found in {target} and is not a known model "
            f"({known})."
        )
    share_link = MODELS[name]
    if not share_link:
        raise FileNotFoundError(
            f"Model '{name}' was not found in {target}, and no download link is set "
            "for it yet. Put the model folder there, or set the link in "
            "greek_med_anonymizer/model_store.py."
        )

    try:
        import gdown
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: gdown. Install with `pip install -e \".[ml,ui]\"`."
        ) from exc

    cache = models_root / "_download_cache"
    archive_path = cache / f"{name}.zip"
    extract_root = cache / f"{name}_extracted"
    cache.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(extract_root, ignore_errors=True)
    extract_root.mkdir(parents=True)

    if "/folders/" in share_link:
        downloaded = gdown.download_folder(share_link, output=str(extract_root), quiet=False)
        if not downloaded:
            raise RuntimeError(
                f"Could not download the model folder from {share_link}. Check that "
                "it is shared as 'Anyone with the link'."
            )
    else:
        gdown.download(gdrive_download_url(share_link), str(archive_path), quiet=False)
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(extract_root)

    found = find_model_dir(extract_root)
    if found is None:
        raise FileNotFoundError(f"No model folder was found in the download of {name}.")

    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(found, target)
    shutil.rmtree(extract_root, ignore_errors=True)
    archive_path.unlink(missing_ok=True)
    return target

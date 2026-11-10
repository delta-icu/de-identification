from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import tempfile
from typing import Iterable
import zipfile

SUPPORTED_EXTENSIONS = {".docx", ".doc", ".txt"}


def _build_pipeline(processing_mode: str, mask_token: str):
    from greek_med_anonymizer.config import AppConfig, ModelConfig, RuleConfig
    from greek_med_anonymizer.model_store import ensure_model_dir
    from greek_med_anonymizer.pipeline import AnonymizationPipeline

    config = AppConfig(
        input_glob="*.docx",
        output_suffix=".anon.txt",
        mask_token=mask_token,
        processing_mode=processing_mode,
        rules=RuleConfig(phones=True, patient_ids=True, local_hospital=True),
        model=ModelConfig(
            enabled=True,
            model_dir=str(ensure_model_dir()),
            labels_to_mask=["PHI", "PERSON_NAME", "HOSPITAL_NAME"],
        ),
    )
    return AnonymizationPipeline(config)


def _collect_uploaded_paths(uploaded_files: Iterable, workspace: Path) -> list[Path]:
    inputs_dir = workspace / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    collected: list[Path] = []

    for uploaded in uploaded_files:
        suffix = Path(uploaded.name).suffix.lower()
        if suffix == ".zip":
            zip_target = inputs_dir / uploaded.name
            zip_target.write_bytes(uploaded.getvalue())
            extract_dir = inputs_dir / Path(uploaded.name).stem
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_target, "r") as archive:
                archive.extractall(extract_dir)
            for candidate in sorted(extract_dir.rglob("*")):
                if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
                    collected.append(candidate)
            continue

        if suffix in SUPPORTED_EXTENSIONS:
            target = inputs_dir / uploaded.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(uploaded.getvalue())
            collected.append(target)

    return collected


def _serialize_entities(entities: list) -> list[dict[str, object]]:
    return [
        {
            "start": entity.start,
            "end": entity.end,
            "label": entity.label,
            "text": entity.text,
            "source": entity.source,
        }
        for entity in entities
    ]


def _build_output_zip(results: list[dict[str, object]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in results:
            base_name = Path(str(item["filename"])).stem
            archive.writestr(f"{base_name}.anon.txt", str(item["anonymized_text"]))
            archive.writestr(
                f"{base_name}.anon.json",
                json.dumps(item["metadata"], ensure_ascii=False, indent=2),
            )
    buffer.seek(0)
    return buffer.getvalue()


def render_app() -> None:
    import streamlit as st
    from greek_med_anonymizer.io_utils import read_input_text

    st.set_page_config(page_title="Greek Medical Report Anonymizer", layout="wide")
    st.title("Greek Medical Report Anonymizer")
    st.write("Upload one or more reports, or upload a `.zip` file containing a folder of reports.")
    st.caption(
        "Accepted formats: `.docx`, `.doc`, `.txt`, or a `.zip` of those. "
        "Older `.doc` files are converted automatically, which takes a few extra seconds each."
    )

    @st.cache_resource(show_spinner=False)
    def get_cached_pipeline(processing_mode: str, mask_token: str):
        return _build_pipeline(processing_mode=processing_mode, mask_token=mask_token)

    with st.sidebar:
        report_type_label = st.selectbox(
            "Report type",
            (
                "Report with template and free text",
                "Free-text-only report",
            ),
        )
        mask_token = st.text_input("Mask token", value="[REDACTED]")

        from greek_med_anonymizer.model_store import selected_model_name

        st.caption(f"Model: `{selected_model_name()}`")

    uploaded_files = st.file_uploader(
        "Upload `.docx`, `.doc`, `.txt`, or `.zip` files",
        type=["docx", "doc", "txt", "zip"],
        accept_multiple_files=True,
    )

    if st.button("Run anonymization", type="primary"):
        if not uploaded_files:
            st.error("Please upload at least one report or one `.zip` archive.")
            return

        processing_mode = (
            "free_text_only"
            if report_type_label == "Free-text-only report"
            else "mixed"
        )

        try:
            with st.spinner("Preparing model and pipeline..."):
                pipeline = get_cached_pipeline(processing_mode=processing_mode, mask_token=mask_token)

            with tempfile.TemporaryDirectory() as temp_dir_name:
                temp_dir = Path(temp_dir_name)
                input_paths = _collect_uploaded_paths(uploaded_files, temp_dir)
                if not input_paths:
                    st.error("No supported `.docx`, `.doc`, or `.txt` files were found in the uploaded input.")
                    return

                results: list[dict[str, object]] = []
                for input_path in input_paths:
                    source_text = read_input_text(input_path)
                    result = pipeline.anonymize_text(source_text)
                    results.append(
                        {
                            "filename": input_path.name,
                            "anonymized_text": result.anonymized_text,
                            "metadata": _serialize_entities(result.entities),
                        }
                    )

            output_zip = _build_output_zip(results)
        except Exception as exc:
            st.error(f"Anonymization failed: {exc}")
            return

        st.success(f"Processed {len(results)} file(s).")
        st.download_button(
            "Download anonymized outputs (.zip)",
            data=output_zip,
            file_name="anonymized_outputs.zip",
            mime="application/zip",
        )

        for item in results:
            st.subheader(str(item["filename"]))
            st.caption(f"Detected entities: {len(item['metadata'])}")
            st.text_area(
                f"Anonymized output: {item['filename']}",
                str(item["anonymized_text"]),
                height=320,
            )


def main() -> int:
    try:
        from streamlit.web import cli as stcli
    except ImportError as exc:
        raise RuntimeError("Missing dependency: streamlit. Install with `pip install -e \".[ml,ui]\"`.") from exc

    script_path = Path(__file__).resolve()
    sys.argv = ["streamlit", "run", str(script_path)]
    return stcli.main()


if __name__ == "__main__":
    render_app()

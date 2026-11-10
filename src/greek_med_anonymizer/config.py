from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class RuleConfig:
    phones: bool = True
    patient_ids: bool = True
    # Mask the local hospital (ΠΓΝΙ and its variants) with a rule. In gold v2 it
    # is PHI. Set to False only to reproduce the behaviour of gold v1 models.
    local_hospital: bool = True


@dataclass(slots=True)
class TemplateSectionConfig:
    name: str
    start_after: str | None = None
    end_before: str | None = None
    enabled_rules: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ModelConfig:
    enabled: bool = False
    model_dir: str | None = None
    labels_to_mask: list[str] = field(default_factory=lambda: ["PHI", "PERSON_NAME", "HOSPITAL_NAME"])
    # Kept for old config files; the detector no longer uses it.
    aggregation_strategy: str = "simple"
    # Threshold on P(PHI) and word snapping. None means: take them from the
    # model's final_config.json, or, for a model without one, use argmax and
    # no word snapping (the behaviour the model was evaluated with).
    threshold: float | None = None
    word_snap: bool | None = None
    # Sliding windows over long texts, as in training.
    max_length: int = 512
    stride: int = 128


@dataclass(slots=True)
class AppConfig:
    input_glob: str = "*.txt"
    output_suffix: str = ".anon.txt"
    mask_token: str = "[REDACTED]"
    processing_mode: str = "auto"
    rules: RuleConfig = field(default_factory=RuleConfig)
    template_sections: list[TemplateSectionConfig] = field(default_factory=list)
    model: ModelConfig = field(default_factory=ModelConfig)


def resolve_model_dir(model_dir: str | None) -> str | None:
    if not model_dir:
        return None

    candidate = Path(model_dir).expanduser()
    if candidate.is_absolute():
        return str(candidate)

    return str((PROJECT_ROOT / candidate).resolve())


def load_config(path: str | Path) -> AppConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return AppConfig(
        input_glob=raw.get("input_glob", "*.txt"),
        output_suffix=raw.get("output_suffix", ".anon.txt"),
        mask_token=raw.get("mask_token", "[REDACTED]"),
        processing_mode=raw.get("processing_mode", "auto"),
        rules=RuleConfig(**raw.get("rules", {})),
        template_sections=[
            TemplateSectionConfig(**section) for section in raw.get("template_sections", [])
        ],
        model=ModelConfig(**raw.get("model", {})),
    )

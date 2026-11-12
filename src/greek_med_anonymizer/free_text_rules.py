from __future__ import annotations

import re

from greek_med_anonymizer.models import Entity


PHONE_REGEX = re.compile(
    r"""
    (?:
        @\d{5,}
        |
        (?:(?:\(\s*\+30\s*\)|\+30)\s*[-–—]?\s*)?
        (?:
            69\d(?:[\s\-]?\d){7}
            |
            2\d{2}(?:[\s\-]?\d){7}
            |
            2\d{3}(?:[\s\-]?\d){6}
        )
    )
    """,
    re.VERBOSE,
)

PATIENT_ID_REGEX = re.compile(r"(?<!\d)\d{8}(?!\d)")

# The local hospital (University Hospital of Ioannina) in the forms that appear
# in the reports, with and without "Γενικό" (ΠΓΝΙ / ΠΝΙ). In gold v2 it is PHI: a model trained on gold v2 learns to
# mask it, and this rule catches it even when the model does not. A full stop
# after a bare "ΠΓΝΙ" is sentence punctuation and stays outside the span.
LOCAL_HOSPITAL_REGEX = re.compile(
    r"""
    (?<![^\W\d_])                       # not glued to a preceding letter
    (?:
        Π\.\s?(?:Γ\.\s?)?Ν\.\s?Ι\.      # Π.Γ.Ν.Ι., Π.Ν.Ι.
        |
        Π\.?\s?(?:Γ\.?\s?)?Ν\.?\s+Ιωανν[ιί]νων  # ΠΓΝ / ΠΝ Ιωαννίνων, Π.Γ.Ν. / Π.Ν. Ιωαννίνων
        |
        (?:ΠΓΝΙ|ΓΠΝΙ|ΠΝΙ)(?:ωανν[ιί]νων)?  # ΠΓΝΙ, ΠΝΙ, ΓΠΝΙ, and the typo ΓΠΝΙωαννίνων
        |
        Πανεπιστημιακ[οόώ]\w*\s+(?:Γενικ[οόώ]\w*\s+)?Νοσοκομε[ιί]\w*\s+Ιωανν[ιί]νων
    )
    (?![^\W\d_])                        # not glued to a following letter
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Units and departments a model may flag that are never PHI.
_NOISE_EQ = {"ΜΕΘ", "ΤΕΠ"}
# Older models were trained with the local hospital left unmarked (gold v1).
_LOCAL_HOSPITAL_NOISE = ("ΠΓΝΙ", "ΠΝΙ")


def detect_phone_entities(text: str) -> list[Entity]:
    if not text:
        return []
    return [
        Entity(match.start(), match.end(), "PHONE", match.group(0), "rule:free_text_phone")
        for match in PHONE_REGEX.finditer(text)
    ]


def detect_patient_id_entities(text: str) -> list[Entity]:
    if not text:
        return []
    return [
        Entity(match.start(), match.end(), "PATIENT_ID", match.group(0), "rule:free_text_patient_id")
        for match in PATIENT_ID_REGEX.finditer(text)
    ]


def detect_local_hospital_entities(text: str) -> list[Entity]:
    if not text:
        return []
    return [
        Entity(match.start(), match.end(), "HOSPITAL_NAME", match.group(0), "rule:local_hospital")
        for match in LOCAL_HOSPITAL_REGEX.finditer(text)
    ]


def normalize_model_label(label: str) -> str:
    if not label:
        return "MISC"
    normalized = str(label).upper()
    if normalized in {"PHI", "B-PHI", "I-PHI"} or normalized.endswith("-PHI"):
        return "PHI"
    if "PER" in normalized or "PERSON" in normalized:
        return "PERSON_NAME"
    if "ORG" in normalized:
        return "HOSPITAL_NAME"
    if "LOC" in normalized or "GPE" in normalized:
        return "LOCATION"
    return "MISC"


def normalize_noise_token(value: str) -> str:
    normalized = (value or "").strip().upper()
    return re.sub(r"[\s\.\-–—\(\)\[\]\{\}]+", "", normalized)


def is_noise_entity_text(entity_text: str, local_hospital_is_phi: bool = True) -> bool:
    """True for model detections that should be dropped.

    ``local_hospital_is_phi`` is True when the local hospital is masked. It is
    then not noise, so a detection of it is kept.
    """
    token = normalize_noise_token(entity_text)
    if not token:
        return True
    if token in _NOISE_EQ:
        return True
    if not local_hospital_is_phi and token.startswith(_LOCAL_HOSPITAL_NOISE):
        return True
    return False


def overlaps_any(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    for left, right in ranges:
        if max(start, left) < min(end, right):
            return True
    return False

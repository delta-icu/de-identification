from __future__ import annotations

import re
import string

from greek_med_anonymizer.models import Entity


PATIENT_ID_LABEL = r"Αρ\.\s*Μητρ\.\s*Ασθ(?:\.|(?:ενούς))?"
POSTAL_CITY_LABEL = r"(?:Τ\.\s*Κ\.?\s*[–—-]?\s*Πόλη|Τ\.\s*Κ\.?|Πόλη)"


FIELD_SAME_LINE = [
    ("patient_id", re.compile(rf"({PATIENT_ID_LABEL}\s*:\s*)([^\n\r]+)", re.IGNORECASE)),
    ("staff_name", re.compile(r"(Διευθυντής\s*:\s*)([^\n\r]+)", re.IGNORECASE)),
    ("first_name", re.compile(r"(Όνομα\s*:\s*)([^\n]+)", re.IGNORECASE)),
    ("last_name", re.compile(r"(Επώνυμο\s*:\s*)([^\n]+)", re.IGNORECASE)),
    ("address", re.compile(r"(Διεύθυνση\s*:\s*)([^\n]+)", re.IGNORECASE)),
    ("postal_city", re.compile(rf"({POSTAL_CITY_LABEL}\s*:\s*)([^\n\r]+)", re.IGNORECASE)),
    ("phone", re.compile(r"(Τηλέφωνο\s*:\s*)([^\n]+)", re.IGNORECASE)),
]

FIELD_NEXT_LINE = [
    ("patient_id", re.compile(rf"({PATIENT_ID_LABEL}\s*:\s*\n)([^\n\r]+)", re.IGNORECASE)),
    ("staff_name", re.compile(r"(Διευθυντής\s*:\s*\n)([^\n\r]+)", re.IGNORECASE)),
    ("first_name", re.compile(r"(Όνομα\s*:\s*\n)([^\n]+)", re.IGNORECASE)),
    ("last_name", re.compile(r"(Επώνυμο\s*:\s*\n)([^\n]+)", re.IGNORECASE)),
    ("address", re.compile(r"(Διεύθυνση\s*:\s*\n)([^\n]+)", re.IGNORECASE)),
    ("postal_city", re.compile(rf"({POSTAL_CITY_LABEL}\s*:\s*\n)([^\n\r]+)", re.IGNORECASE)),
    ("phone", re.compile(r"(Τηλέφωνο\s*:\s*\n)([^\n\r]+)", re.IGNORECASE)),
]

SIGNATURE_TITLE_LINE = re.compile(
    r"^\s*(?:Ο|Η)\s+"
    r"(?:Διευθυντής|Επιμελητής|Ιατρός(?:\s+ΜΕΘ)?|Εξειδικευόμεν(?:η|ος)|Καθηγητής)"
    r"\s*$",
    re.IGNORECASE,
)

SIGNATURE_TITLES_BLOCK = re.compile(
    r"((?:^\s*(?:Ο|Η)\s+"
    r"(?:Διευθυντής|Επιμελητής|Ιατρός(?:\s+ΜΕΘ)?|Εξειδικευόμεν(?:η|ος)|Καθηγητής)"
    r"\s*$\n?)+)",
    re.IGNORECASE | re.MULTILINE,
)

LABEL_HINTS = [
    "Αρ.",
    "ΑΜΚΑ",
    "Διευθυντής",
    "Καθηγητής",
    "Επώνυμο",
    "Όνομα",
    "Διεύθυνση",
    "Τ.Κ",
    "Πόλη",
    "Τηλέφωνο",
    "Ημ/νία",
    "Ηλικία",
    "Τμήμα",
    "Κλινική",
    "Ο Διευθυντής",
    "Ο Επιμελητής",
    "Η Εξειδικευόμενη",
    "Ο Εξειδικευόμενος",
    "Ο Ιατρός ΜΕΘ",
    "Η Ιατρός ΜΕΘ",
    "Ο Ιατρός",
    "Η Ιατρός",
    "Η ιατρός",
    "ΠΡΟΣΟΧΗ",
]

TITLE_VALUE_PATTERNS = [
    re.compile(r"^(?:Καθηγητής|Καθηγήτρια)\s*:\s*\S", re.IGNORECASE),
    re.compile(r"^(?:Αν\.?\s*Καθηγητής|Αν\.?\s*Καθηγήτρια)\s*:\s*\S", re.IGNORECASE),
    re.compile(r"^(?:Ιατρός|Η\s+Ιατρός|Ο\s+Ιατρός)\s*:\s*\S", re.IGNORECASE),
    re.compile(r"^(?:Επιμελητής|Επιμελήτρια)\s*:\s*\S", re.IGNORECASE),
]

_ONLY_PUNCT = set(string.punctuation) | {"·", "…", "«", "»", "–", "—", "―", "’", "“", "”", "„", "•", "▪", "►", "‐"}
PHONE_PAT = re.compile(r"(?:\+30\s*)?(?:69\d|2\d{2})[\s\-]?\d{3}[\s\-]?\d{4}")
PHONE_LINE_PAT = re.compile(r"^\s*(?:@?\+30\s*)?(?:69\d|2\d{2})[\d\s\-\(\)]{7,}\s*$")


def looks_like_label(value: str) -> bool:
    value = (value or "").strip()
    if not value:
        return True

    for pattern in TITLE_VALUE_PATTERNS:
        if pattern.match(value):
            return False

    if value.endswith(":"):
        return True
    lower_value = value.lower()
    for hint in LABEL_HINTS:
        if hint.lower() in lower_value and len(value) <= 60:
            return True
    return False


def trim_span(text: str, start: int, end: int) -> tuple[int, int] | None:
    chunk = text[start:end]
    left = len(chunk) - len(chunk.lstrip())
    right = len(chunk.rstrip())
    normalized_start = start + left
    normalized_end = start + right
    if normalized_start >= normalized_end:
        return None
    return normalized_start, normalized_end


def _strip_edge_punct(value: str) -> str:
    normalized = (value or "").strip()
    while normalized and normalized[0] in _ONLY_PUNCT:
        normalized = normalized[1:].lstrip()
    while normalized and normalized[-1] in _ONLY_PUNCT:
        normalized = normalized[:-1].rstrip()
    return normalized


def _is_only_punct_line(value: str) -> bool:
    normalized = (value or "").strip()
    if not normalized:
        return False
    return all(char in _ONLY_PUNCT for char in normalized)


def is_phone_line(value: str) -> bool:
    return bool(PHONE_LINE_PAT.match(value or ""))


def add_phone_spans_from_value(text: str, base_start: int, base_end: int, entities: list[Entity]) -> None:
    value = text[base_start:base_end]
    found = [(match.start(), match.end()) for match in PHONE_PAT.finditer(value)]

    if not found:
        entities.append(
            Entity(base_start, base_end, "PHONE", text[base_start:base_end], "rule:template_phone")
        )
        return

    found.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    kept: list[tuple[int, int]] = []
    last_end = -1
    for start, end in found:
        if start >= last_end:
            kept.append((start, end))
            last_end = end

    for start, end in kept:
        abs_start = base_start + start
        abs_end = base_start + end
        entities.append(Entity(abs_start, abs_end, "PHONE", text[abs_start:abs_end], "rule:template_phone"))


def detect_template_entities(template_text: str) -> list[Entity]:
    text = "" if template_text is None else str(template_text)
    entities: list[Entity] = []

    for match in re.finditer(r"(Τηλέφωνο\s*:\s*)\n", text):
        position = match.end()
        offset = position
        got = 0

        for line in text[position:].splitlines(True):
            raw = line.strip()
            if not raw:
                offset += len(line)
                continue
            if is_phone_line(raw):
                start = offset + line.find(raw)
                end = start + len(raw)
                add_phone_spans_from_value(text, start, end, entities)
                got += 1
                offset += len(line)
                if got == 2:
                    break
                continue
            break

    for label, pattern in FIELD_NEXT_LINE + FIELD_SAME_LINE:
        for match in pattern.finditer(text):
            start, end = match.span(2)
            trimmed = trim_span(text, start, end)
            if not trimmed:
                continue
            span_start, span_end = trimmed
            value = text[span_start:span_end]
            if looks_like_label(value):
                continue
            if label == "phone":
                add_phone_spans_from_value(text, span_start, span_end, entities)
            else:
                entities.append(
                    Entity(span_start, span_end, label.upper(), value, f"rule:template_{label}")
                )

    for match in SIGNATURE_TITLES_BLOCK.finditer(text):
        position = match.end(1)
        offset = position
        for line in text[position:].splitlines(True):
            raw = line.strip()
            if not raw:
                offset += len(line)
                continue
            if raw.startswith("ΠΡΟΣΟΧΗ"):
                break
            if _is_only_punct_line(raw):
                offset += len(line)
                continue
            cleaned = _strip_edge_punct(raw)
            if not cleaned or looks_like_label(cleaned):
                offset += len(line)
                continue
            local_idx = raw.find(cleaned)
            if local_idx == -1:
                start = offset + line.find(raw)
                end = start + len(raw)
            else:
                start = offset + line.find(raw) + local_idx
                end = start + len(cleaned)
            entities.append(Entity(start, end, "STAFF_NAME", text[start:end], "rule:template_signature"))
            offset += len(line)

    lines = text.splitlines(True)
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line)

    index = 0
    while index < len(lines):
        raw = lines[index].strip()
        if raw.startswith("ΠΡΟΣΟΧΗ"):
            break
        if raw and SIGNATURE_TITLE_LINE.match(raw):
            probe = index + 1
            while probe < len(lines):
                next_raw = lines[probe].strip()
                if next_raw.startswith("ΠΡΟΣΟΧΗ"):
                    probe = -1
                    break
                if not next_raw or _is_only_punct_line(next_raw):
                    probe += 1
                    continue
                cleaned = _strip_edge_punct(next_raw)
                if not cleaned or looks_like_label(cleaned):
                    probe = -1
                    break
                base_offset = offsets[probe]
                start_in_line = lines[probe].find(next_raw)
                if start_in_line < 0:
                    start_in_line = 0
                local_idx = next_raw.find(cleaned)
                if local_idx < 0:
                    start = base_offset + start_in_line
                    end = start + len(next_raw)
                else:
                    start = base_offset + start_in_line + local_idx
                    end = start + len(cleaned)
                entities.append(Entity(start, end, "STAFF_NAME", text[start:end], "rule:template_signature"))
                break
            if probe != -1:
                index = probe + 1
                continue
        index += 1

    entities.sort(key=lambda item: (item.start, -(item.end - item.start)))
    kept: list[Entity] = []
    last_end = -1
    for entity in entities:
        if entity.start >= last_end:
            kept.append(entity)
            last_end = entity.end
    return kept

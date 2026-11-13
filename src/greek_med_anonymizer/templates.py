from __future__ import annotations

from dataclasses import dataclass
import re


START_PAT = re.compile(
    r"ΑΙΤΙΑ\s+ΕΙΣΟΔΟΥ\s*[-–—]\s*ΙΣΤΟΡΙΚΟ",
    re.IGNORECASE,
)
# Some reports write the heading differently ("ΙΣΤΟΡΙΚΟ - ΑΙΤΙΑ ΕΙΣΟΔΟΥ – ΠΑΡΟΥΣΑ ΝΟΣΟΣ",
# "ΑΙΤΙΑ ΕΙΣΟΔΟΥ-ΑΤΟΜΙΚΟ ΑΝΑΜΝΗΣΤΙΚΟ-ΠΟΡΕΙΑ ΝΟΣΟΥ"). When the usual heading is missing,
# the free text starts at the line that contains "ΑΙΤΙΑ ΕΙΣΟΔΟΥ".
ALT_START_PAT = re.compile(
    r"^[^\n]*ΑΙΤΙΑ\s+ΕΙΣΟΔΟΥ[^\n]*$",
    re.IGNORECASE | re.MULTILINE,
)
END_PAT = re.compile(
    r"\bΟ\s+Διευθυντής\b",
    re.IGNORECASE,
)


def find_free_text_start(text: str) -> re.Match[str] | None:
    """The free-text heading: the usual one, or else a line with "ΑΙΤΙΑ ΕΙΣΟΔΟΥ"."""
    return START_PAT.search(text) or ALT_START_PAT.search(text)


@dataclass(slots=True)
class TextSection:
    name: str
    start: int
    end: int
    text: str


def split_template_free(text: str | None) -> tuple[str, str]:
    text = "" if text is None else str(text)

    start_match = find_free_text_start(text)
    if not start_match:
        return text, ""

    start = start_match.start()
    end_match = END_PAT.search(text, start_match.end())
    if not end_match:
        return text[:start], text[start:]

    end = end_match.start()
    template_top = text[:start]
    free_text = text[start:end]
    template_bottom = text[end:]
    return template_top + template_bottom, free_text


def split_template_sections(text: str, sections: list | None = None) -> list[TextSection]:
    text = "" if text is None else str(text)
    resolved_sections: list[TextSection] = []
    start_match = find_free_text_start(text)

    if not start_match:
        return [TextSection(name="full_text", start=0, end=len(text), text=text)]

    free_start = start_match.start()
    end_match = END_PAT.search(text, start_match.end())

    if free_start > 0:
        resolved_sections.append(
            TextSection(
                name="template_top",
                start=0,
                end=free_start,
                text=text[:free_start],
            )
        )

    if not end_match:
        resolved_sections.append(
            TextSection(
                name="free_text",
                start=free_start,
                end=len(text),
                text=text[free_start:],
            )
        )
        return resolved_sections

    free_end = end_match.start()
    resolved_sections.append(
        TextSection(
            name="free_text",
            start=free_start,
            end=free_end,
            text=text[free_start:free_end],
        )
    )

    if free_end < len(text):
        resolved_sections.append(
            TextSection(
                name="template_bottom",
                start=free_end,
                end=len(text),
                text=text[free_end:],
            )
        )

    if resolved_sections:
        return resolved_sections

    return [TextSection(name="full_text", start=0, end=len(text), text=text)]


def build_sections_for_mode(text: str, processing_mode: str = "auto") -> list[TextSection]:
    normalized_mode = (processing_mode or "auto").strip().lower()
    text = "" if text is None else str(text)

    if normalized_mode == "free_text_only":
        return [TextSection(name="free_text", start=0, end=len(text), text=text)]

    if normalized_mode == "template_only":
        return [TextSection(name="template_text", start=0, end=len(text), text=text)]

    if normalized_mode in {"mixed", "auto"}:
        return split_template_sections(text)

    raise ValueError(
        f"Unsupported processing_mode: {processing_mode}. "
        "Expected one of: auto, mixed, free_text_only, template_only."
    )

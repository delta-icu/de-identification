from __future__ import annotations

from greek_med_anonymizer.config import AppConfig, resolve_model_dir
from greek_med_anonymizer.free_text_rules import (
    detect_local_hospital_entities,
    detect_patient_id_entities as detect_free_text_patient_id_entities,
    detect_phone_entities as detect_free_text_phone_entities,
    is_noise_entity_text,
    overlaps_any,
)
from greek_med_anonymizer.models import AnonymizationResult, Entity
from greek_med_anonymizer.rules import detect_patient_id_entities, detect_phone_entities
from greek_med_anonymizer.template_rules import detect_template_entities
from greek_med_anonymizer.templates import build_sections_for_mode
from greek_med_anonymizer.xlm_inference import XLMRDetector


class AnonymizationPipeline:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.model_detector = None
        if config.model.enabled and config.model.model_dir:
            resolved_model_dir = resolve_model_dir(config.model.model_dir)
            self.model_detector = XLMRDetector(
                model_dir=resolved_model_dir,
                labels_to_mask=config.model.labels_to_mask,
                threshold=config.model.threshold,
                word_snap=config.model.word_snap,
                max_length=config.model.max_length,
                stride=config.model.stride,
            )

    def anonymize_text(self, text: str) -> AnonymizationResult:
        entities = self._collect_entities(text)
        anonymized_text = self._apply_mask(text, entities)
        return AnonymizationResult(
            original_text=text,
            anonymized_text=anonymized_text,
            entities=entities,
        )

    def _collect_entities(self, text: str) -> list[Entity]:
        sections = build_sections_for_mode(text, self.config.processing_mode)
        entities: list[Entity] = []

        for section in sections:
            section_text = section.text
            section_entities: list[Entity] = []

            if section.name.startswith("template"):
                section_entities.extend(detect_template_entities(section_text))
                if self.config.rules.phones:
                    section_entities.extend(detect_phone_entities(section_text))
                if self.config.rules.patient_ids:
                    section_entities.extend(detect_patient_id_entities(section_text))
                # The hospital name is often in the letterhead or a field.
                if self.config.rules.local_hospital:
                    section_entities.extend(detect_local_hospital_entities(section_text))

            elif section.name == "free_text":
                section_entities.extend(self._free_text_rule_entities(section_text))
                section_entities.extend(self._model_entities(section_text, section_entities))

            else:
                # "full_text": the report has no recognisable free-text heading,
                # so template fields may be anywhere. The template rules are
                # anchored on field labels ("Όνομα:", "Ο Διευθυντής", ...), so
                # they are safe to run on the whole text, and the model output
                # gets the same filtering as in free text.
                section_entities.extend(detect_template_entities(section_text))
                section_entities.extend(self._free_text_rule_entities(section_text))
                section_entities.extend(self._model_entities(section_text, section_entities))

            entities.extend(self._offset_entities(section.start, section_entities))

        return self._merge_entities(entities)

    def _free_text_rule_entities(self, text: str) -> list[Entity]:
        found: list[Entity] = []
        if self.config.rules.phones:
            found.extend(detect_free_text_phone_entities(text))
        if self.config.rules.patient_ids:
            found.extend(detect_free_text_patient_id_entities(text))
        if self.config.rules.local_hospital:
            found.extend(detect_local_hospital_entities(text))
        return found

    def _model_entities(self, text: str, rule_entities: list[Entity]) -> list[Entity]:
        """Model detections, minus noise and minus spans a rule already covers."""
        if self.model_detector is None:
            return []
        protected = [(entity.start, entity.end) for entity in rule_entities]
        kept: list[Entity] = []
        for entity in self.model_detector.detect(text):
            if overlaps_any(entity.start, entity.end, protected):
                continue
            if is_noise_entity_text(
                entity.text, local_hospital_is_phi=self.config.rules.local_hospital
            ):
                continue
            kept.append(entity)
        return kept

    @staticmethod
    def _offset_entities(offset: int, entities: list[Entity]) -> list[Entity]:
        return [
            Entity(
                start=entity.start + offset,
                end=entity.end + offset,
                label=entity.label,
                text=entity.text,
                source=entity.source,
            )
            for entity in entities
        ]

    @staticmethod
    def _merge_entities(entities: list[Entity]) -> list[Entity]:
        if not entities:
            return []

        ordered = sorted(entities, key=lambda item: (item.start, -(item.end - item.start)))
        merged = [ordered[0]]

        for entity in ordered[1:]:
            previous = merged[-1]
            if entity.start < previous.end:
                if entity.end > previous.end:
                    merged[-1] = Entity(
                        start=previous.start,
                        end=entity.end,
                        label=previous.label,
                        text=previous.text,
                        source=f"{previous.source}|{entity.source}",
                    )
                continue
            merged.append(entity)

        return merged

    def _apply_mask(self, text: str, entities: list[Entity]) -> str:
        if not entities:
            return text

        parts: list[str] = []
        cursor = 0
        for entity in entities:
            parts.append(text[cursor:entity.start])
            parts.append(self.config.mask_token)
            cursor = entity.end
        parts.append(text[cursor:])
        return "".join(parts)

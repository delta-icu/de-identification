"""XLM-R PHI detector: sliding windows, threshold on P(PHI), word snapping.

This reproduces how the final models were evaluated:

1. The text is tokenized once and split into windows of ``max_length`` tokens
   that overlap by ``stride`` tokens, so nothing past token 512 is lost.
2. For every token, P(PHI) = P(B-PHI) + P(I-PHI). A token seen in several
   windows keeps the probability from the window where it is furthest from the
   edge, i.e. where the model saw the most context on both sides.
3. Consecutive tokens with P(PHI) >= threshold form a span.
4. With word snapping, each span is widened to whole words, so a name whose
   first subword scored low is still masked in full.

Models with a ``final_config.json`` next to the weights carry their threshold
and word-snapping setting there. A model without one (the first release) keeps
the behaviour it was evaluated with: argmax over the labels, no snapping.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re

from greek_med_anonymizer.free_text_rules import normalize_model_label
from greek_med_anonymizer.models import Entity

FINAL_CONFIG_NAME = "final_config.json"
_WORD = re.compile(r"\w+")


def load_final_config(model_dir: str | Path) -> dict:
    path = Path(model_dir) / FINAL_CONFIG_NAME
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def snap_to_words(text: str, start: int, end: int) -> tuple[int, int]:
    """Widen [start, end) so it does not cut a word in two."""
    for match in _WORD.finditer(text, max(0, start - 200), min(len(text), end + 200)):
        if match.end() <= start or match.start() >= end:
            continue
        start = min(start, match.start())
        end = max(end, match.end())
    return start, end


def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


class XLMRDetector:
    def __init__(
        self,
        model_dir: str,
        labels_to_mask: list[str],
        threshold: float | None = None,
        word_snap: bool | None = None,
        max_length: int = 512,
        stride: int = 128,
        aggregation_strategy: str | None = None,  # accepted for old callers, unused
    ) -> None:
        self.model_dir = model_dir
        self.labels_to_mask = set(labels_to_mask)
        self.max_length = max_length
        self.stride = stride

        final_config = load_final_config(model_dir)
        self.final_config = final_config
        self.threshold = threshold if threshold is not None else final_config.get("threshold")
        if word_snap is None:
            word_snap = bool(final_config.get("word_snap", False))
        self.word_snap = word_snap

        self._tokenizer = None
        self._model = None
        self._torch = None

    # ------------------------------------------------------------------ loading
    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModelForTokenClassification
        except ImportError as exc:
            raise RuntimeError(
                "The optional 'ml' dependencies are not installed. Install with: pip install -e .[ml]"
            ) from exc

        self._torch = torch
        self._tokenizer = self._load_tokenizer()
        model = AutoModelForTokenClassification.from_pretrained(self.model_dir)
        model.to(self._resolve_device())
        model.eval()
        self._model = model

        labels = {int(i): normalize_model_label(name) for i, name in model.config.id2label.items()}
        self._mask_label_ids = [i for i, label in labels.items() if label in self.labels_to_mask]
        if not self._mask_label_ids:
            raise RuntimeError(
                f"None of the model's labels ({sorted(model.config.id2label.values())}) "
                f"maps to the labels to mask ({sorted(self.labels_to_mask)})."
            )
        self._label_names = labels

    @staticmethod
    def _resolve_device() -> str:
        """Choose the device to run the model on.

        CPU by default, deliberately. Apple's Metal backend (mps) crashes the
        whole process with a segmentation fault when it is driven from a worker
        thread, which is exactly how Streamlit runs this code. The model is
        small and the reports are short, so CPU is fast enough and does not take
        the app down with it.

        Set GREEK_ANON_DEVICE=mps (or cuda) to override.
        """
        return os.environ.get("GREEK_ANON_DEVICE", "cpu")

    def _load_tokenizer(self):
        """Load the tokenizer, tolerating a model exported by transformers 5.x.

        transformers 5 writes ``extra_special_tokens`` in tokenizer_config.json
        as a list, while transformers 4 expects a mapping and fails with
        "'list' object has no attribute 'keys'". Passing the key explicitly
        overrides the value from the file, so the model folder is left alone.
        """
        from transformers import AutoTokenizer

        try:
            return AutoTokenizer.from_pretrained(self.model_dir)
        except AttributeError as exc:
            if "has no attribute 'keys'" not in str(exc):
                raise
            try:
                return AutoTokenizer.from_pretrained(self.model_dir, extra_special_tokens={})
            except Exception as retry_exc:
                raise RuntimeError(
                    "The tokenizer in this model folder was saved by a newer "
                    "version of transformers than the one installed, and it "
                    "could not be loaded.\n"
                    f"Model folder: {self.model_dir}\n"
                    f"Underlying error: {type(retry_exc).__name__}: {retry_exc}"
                ) from retry_exc

    # ---------------------------------------------------------------- inference
    def token_scores(self, text: str) -> list[tuple[int, int, float, bool]]:
        """(char_start, char_end, P(PHI), argmax is PHI) for every token of ``text``."""
        self._load()
        torch = self._torch
        encoded = self._tokenizer(
            text,
            truncation=True,
            max_length=self.max_length,
            stride=self.stride,
            return_overflowing_tokens=True,
            return_offsets_mapping=True,
            padding=True,
            return_tensors="pt",
        )
        offsets = encoded.pop("offset_mapping").tolist()
        encoded.pop("overflow_to_sample_mapping", None)
        n_windows = len(offsets)
        device = next(self._model.parameters()).device
        inputs = {key: value.to(device) for key, value in encoded.items()}

        with torch.no_grad():
            logits = self._model(**inputs).logits
        probs = torch.softmax(logits.float(), dim=-1).cpu()
        p_phi = probs[..., self._mask_label_ids].sum(dim=-1).tolist()
        argmax = probs.argmax(dim=-1).tolist()
        mask_ids = set(self._mask_label_ids)

        # The same token appears in several windows: keep the window where it
        # has the most context on both sides.
        best: dict[tuple[int, int], tuple[int, float, bool]] = {}
        for w in range(n_windows):
            positions = [
                i for i, (s, e) in enumerate(offsets[w]) if e > s
            ]  # real tokens only (special and padding tokens have empty offsets)
            if not positions:
                continue
            first, last = positions[0], positions[-1]
            for i in positions:
                key = (offsets[w][i][0], offsets[w][i][1])
                context = min(i - first, last - i)
                if key not in best or context > best[key][0]:
                    best[key] = (context, p_phi[w][i], argmax[w][i] in mask_ids)
        return [(s, e, score, is_phi) for (s, e), (_, score, is_phi) in sorted(best.items())]

    def detect(self, text: str) -> list[Entity]:
        if not text or not text.strip():
            return []
        tokens = self.token_scores(text)

        spans: list[tuple[int, int]] = []
        current: list[int] | None = None
        for start, end, score, is_phi in tokens:
            positive = is_phi if self.threshold is None else score >= self.threshold
            if positive:
                if current is None:
                    current = [start, end]
                else:
                    current[1] = end
            elif current is not None:
                spans.append((current[0], current[1]))
                current = None
        if current is not None:
            spans.append((current[0], current[1]))

        # Tokenizers include the leading space ("▁") in the offsets of some
        # tokens; spans should start and end on text, not whitespace.
        cleaned = []
        for start, end in spans:
            while start < end and text[start].isspace():
                start += 1
            while end > start and text[end - 1].isspace():
                end -= 1
            if end > start:
                cleaned.append((start, end))
        spans = cleaned

        if self.word_snap:
            spans = [snap_to_words(text, s, e) for s, e in spans]
        spans = merge_spans(spans)

        return [
            Entity(start=s, end=e, label="PHI", text=text[s:e], source="model:xlmr")
            for s, e in spans
        ]

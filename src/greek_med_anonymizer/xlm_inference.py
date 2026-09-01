from __future__ import annotations

from greek_med_anonymizer.models import Entity
from greek_med_anonymizer.free_text_rules import normalize_model_label


class XLMRDetector:
    def __init__(
        self,
        model_dir: str,
        labels_to_mask: list[str],
        aggregation_strategy: str = "simple",
    ) -> None:
        self.model_dir = model_dir
        self.labels_to_mask = set(labels_to_mask)
        self.aggregation_strategy = aggregation_strategy
        self._pipeline = None

    def _load(self) -> None:
        if self._pipeline is not None:
            return

        try:
            from transformers import pipeline
        except ImportError as exc:
            raise RuntimeError(
                "The optional 'ml' dependencies are not installed. Install with: pip install -e .[ml]"
            ) from exc

        self._pipeline = pipeline(
            task="token-classification",
            model=self.model_dir,
            tokenizer=self._load_tokenizer(),
            aggregation_strategy=self.aggregation_strategy,
            device=self._resolve_device(),
        )

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
        import os

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
                return AutoTokenizer.from_pretrained(
                    self.model_dir, extra_special_tokens={}
                )
            except Exception as retry_exc:
                raise RuntimeError(
                    "The tokenizer in this model folder was saved by a newer "
                    "version of transformers than the one installed, and it "
                    "could not be loaded.\n"
                    f"Model folder: {self.model_dir}\n"
                    f"Underlying error: {type(retry_exc).__name__}: {retry_exc}"
                ) from retry_exc

    def detect(self, text: str) -> list[Entity]:
        self._load()
        predictions = self._pipeline(text)
        entities: list[Entity] = []
        for prediction in predictions:
            raw_label = prediction.get("entity_group") or prediction.get("entity")
            normalized_label = normalize_model_label(raw_label)
            if normalized_label not in self.labels_to_mask:
                continue
            start = int(prediction["start"])
            end = int(prediction["end"])
            entities.append(
                Entity(
                    start=start,
                    end=end,
                    label=normalized_label,
                    text=text[start:end],
                    source="model:xlmr",
                )
            )
        return entities

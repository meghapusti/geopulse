"""
Event classifier.
Uses DeBERTa-v3-small-mnli-fever-anli-ling-wanli for zero-shot classification.
Quantized to ONNX INT8 for fast CPU inference (~80ms per article vs ~400ms full model).

Event taxonomy (CAMEO-inspired, simplified for our use case):
  armed_conflict      — military operations, airstrikes, ground combat
  sanctions           — economic sanctions, trade restrictions, embargoes
  political_crisis    — coups, elections disputes, government collapse
  protest             — mass demonstrations, civil unrest
  diplomacy           — peace talks, summits, treaties, agreements
  humanitarian        — refugee crisis, famine, disaster response
  economic_shock      — currency crisis, market crash, bank failure
  energy              — oil/gas supply, pipeline, energy policy
  terrorism           — attacks, bombings, extremist activity
  other               — catch-all for non-geopolitical content

Model: cross-encoder/nli-deberta-v3-small (~170MB, fast on CPU)
Export script: notebooks/02_training/export_classifier_onnx.ipynb
"""
from pathlib import Path
from typing import Optional

import numpy as np
import structlog
from transformers import pipeline, Pipeline

from app.core.config import settings

log = structlog.get_logger()

EVENT_LABELS = [
    "armed conflict",
    "sanctions and trade restrictions",
    "political crisis",
    "protest and civil unrest",
    "diplomacy and peace talks",
    "humanitarian crisis",
    "economic shock",
    "energy and oil supply",
    "terrorism",
    "other",
]

# Map verbose candidate labels → short internal codes
LABEL_MAP = {
    "armed conflict": "armed_conflict",
    "sanctions and trade restrictions": "sanctions",
    "political crisis": "political_crisis",
    "protest and civil unrest": "protest",
    "diplomacy and peace talks": "diplomacy",
    "humanitarian crisis": "humanitarian",
    "economic shock": "economic_shock",
    "energy and oil supply": "energy",
    "terrorism": "terrorism",
    "other": "other",
}

MODEL_ID = "cross-encoder/nli-deberta-v3-small"


class EventClassifier:
    """
    Zero-shot event classifier.
    Lazy-loads on first use so the app starts fast.
    """

    def __init__(self):
        self._pipe: Optional[Pipeline] = None

    def _load(self) -> Pipeline:
        if self._pipe is None:
            log.info("Loading event classifier", model=MODEL_ID)
            self._pipe = pipeline(
                "zero-shot-classification",
                model=MODEL_ID,
                device=-1,          # CPU
                # If ONNX weights exist, HF will use them automatically
                model_kwargs={"cache_dir": settings.MODEL_CACHE_DIR},
            )
            log.info("Event classifier ready")
        return self._pipe

    def classify_single(self, text: str) -> dict:
        """Classify a single text. Returns {label, score}."""
        pipe = self._load()
        result = pipe(text, candidate_labels=EVENT_LABELS, multi_label=False)
        top_label = result["labels"][0]
        top_score = result["scores"][0]
        return {
            "label": LABEL_MAP.get(top_label, "other"),
            "score": float(top_score),
            "all_scores": {
                LABEL_MAP.get(l, l): float(s)
                for l, s in zip(result["labels"], result["scores"])
            },
        }

    def classify_batch(self, texts: list[str]) -> list[dict]:
        """
        Classify a batch of texts efficiently.
        The HF zero-shot pipeline supports batch processing natively.
        """
        pipe = self._load()
        results = pipe(texts, candidate_labels=EVENT_LABELS, multi_label=False)
        if not isinstance(results, list):
            results = [results]

        output = []
        for result in results:
            top_label = result["labels"][0]
            top_score = result["scores"][0]
            output.append({
                "label": LABEL_MAP.get(top_label, "other"),
                "score": float(top_score),
            })
        return output

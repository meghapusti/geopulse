"""
Sentiment analyser.
Two components:
  1. FinBERT — financial sentiment (positive/negative/neutral)
     Model: ProsusAI/finbert (~400MB) or yiyanghkust/finbert-tone (lighter)
  2. Geopolitical stress score — derived from sentiment + keyword weighting.
     This is a heuristic composite that we'll replace with a fine-tuned model
     once we've collected labelled data (see notebooks/02_training/).

Geopolitical stress (0.0–1.0):
  0.0 = stable / positive news
  0.5 = neutral / mixed signals
  1.0 = acute conflict / humanitarian crisis
"""
import re
from typing import Optional

import structlog
from transformers import pipeline, Pipeline

from app.core.config import settings

log = structlog.get_logger()

# FinBERT model — lighter tone variant works well for our use case
FINBERT_MODEL = "yiyanghkust/finbert-tone"

# Stress-amplifying keyword patterns (case-insensitive)
# Higher weight = more stress when present in article
STRESS_KEYWORDS: list[tuple[str, float]] = [
    (r"\b(war|warfare|combat|airstrike|bombing|invasion)\b", 0.35),
    (r"\b(missile|nuclear|chemical weapon|wmd)\b", 0.40),
    (r"\b(sanction|embargo|trade ban|export control)\b", 0.20),
    (r"\b(coup|overthrow|regime change|martial law)\b", 0.28),
    (r"\b(famine|refugee|humanitarian crisis|displacement)\b", 0.22),
    (r"\b(assassination|terrorist|attack|explosion)\b", 0.30),
    (r"\b(recession|default|currency crisis|bank run)\b", 0.18),
    (r"\b(protest|unrest|riot|clashes)\b", 0.12),
    (r"\b(ceasefire|peace talks|agreement|treaty)\b", -0.15),  # de-escalation
    (r"\b(election|vote|democracy|transition)\b", -0.05),
]


class SentimentAnalyser:
    def __init__(self):
        self._pipe: Optional[Pipeline] = None

    def _load(self) -> Pipeline:
        if self._pipe is None:
            log.info("Loading FinBERT", model=FINBERT_MODEL)
            self._pipe = pipeline(
                "text-classification",
                model=FINBERT_MODEL,
                device=-1,
                model_kwargs={"cache_dir": settings.MODEL_CACHE_DIR},
                truncation=True,
                max_length=512,
            )
            log.info("FinBERT ready")
        return self._pipe

    def _compute_stress(self, text: str, sentiment_score: float) -> float:
        """
        Heuristic geopolitical stress score.
        Base: inverted sentiment (negative sentiment → higher stress).
        Adjusted by keyword presence.
        """
        # Base stress from sentiment: negative=0.7, neutral=0.4, positive=0.1
        base = max(0.0, 0.5 - sentiment_score * 0.5)

        keyword_adjustment = 0.0
        text_lower = text.lower()
        for pattern, weight in STRESS_KEYWORDS:
            if re.search(pattern, text_lower):
                keyword_adjustment += weight

        stress = base + keyword_adjustment
        return float(max(0.0, min(1.0, stress)))

    def _normalise_score(self, label: str, raw_score: float) -> float:
        """Convert FinBERT output to -1 (negative) → +1 (positive)."""
        label = label.lower()
        if label in ("positive", "pos"):
            return raw_score
        elif label in ("negative", "neg"):
            return -raw_score
        else:
            return 0.0

    def analyse_single(self, text: str) -> dict:
        pipe = self._load()
        result = pipe(text, truncation=True)[0]
        label = result["label"]
        norm_score = self._normalise_score(label, result["score"])
        stress = self._compute_stress(text, norm_score)
        return {
            "label": label.lower(),
            "score": norm_score,
            "stress": stress,
        }

    def analyse_batch(self, texts: list[str]) -> list[dict]:
        pipe = self._load()
        results = pipe(texts, truncation=True, batch_size=16)
        output = []
        for text, result in zip(texts, results):
            label = result["label"]
            norm_score = self._normalise_score(label, result["score"])
            stress = self._compute_stress(text, norm_score)
            output.append({
                "label": label.lower(),
                "score": norm_score,
                "stress": stress,
            })
        return output

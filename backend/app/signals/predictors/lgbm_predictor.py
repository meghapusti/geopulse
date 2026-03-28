"""
LightGBM market signal predictor.
Predicts: VIX direction, gold bias, oil bias, macro risk quartile
given the current tension index features + market data.

Feature vector (per prediction run):
  Global features:
    - global_tension_mean, global_tension_max, global_tension_std
    - n_high_tension_regions (tension > 60)
    - n_armed_conflict_articles_24h
    - n_sanctions_articles_24h
    - global_stress_delta_24h
  Market features (from cache):
    - vix_current, vix_pct_change_1h
    - gold_price, gold_pct_change
    - oil_wti_price, oil_pct_change
    - dxy_price (dollar index)
    - us10y (10Y yield)

Training: see notebooks/02_training/train_lgbm_predictor.ipynb
The training notebook loads historical GDELT + Yahoo Finance data,
constructs the same feature vector historically, and trains on actual
VIX/gold/oil outcomes.

Model file: data/models/lgbm_predictor.pkl
"""
import json
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import RegionSignal, MarketSignal
from app.ingestion.sources.market import MarketDataIngestor
from app.schemas.schemas import CounterfactualResponse

log = structlog.get_logger()

MODEL_PATH = Path(settings.MODEL_CACHE_DIR) / "lgbm_predictor.pkl"

# Horizons to predict at each run
HORIZONS = [24, 48, 72]


class LGBMPredictor:
    def __init__(self):
        self._models: Optional[dict] = None   # {horizon: {target: model}}

    def _load_models(self) -> dict:
        """
        Load pre-trained LightGBM models from disk.
        The notebook saves models under day-keys {1, 2, 3}.
        The API uses horizon_hours {24, 48, 72}.
        We normalise to hour-keys here so the rest of the code is consistent.
        """
        if self._models is not None:
            return self._models

        if not MODEL_PATH.exists():
            log.warning(
                "LightGBM model not found — run training notebook first",
                path=str(MODEL_PATH),
            )
            return {}

        with open(MODEL_PATH, "rb") as f:
            raw = pickle.load(f)

        meta = raw.get("__meta__", {})
        horizon_map: dict = meta.get("horizon_map", {24: 1, 48: 2, 72: 3})
        # horizon_map is {hours: days} e.g. {24: 1, 48: 2, 72: 3}
        # Remap so self._models keys are hours (24/48/72) not days (1/2/3)
        self._models = {}
        for hours, days in horizon_map.items():
            if days in raw:
                self._models[hours] = raw[days]

        log.info("LightGBM models loaded", horizons=list(self._models.keys()))
        return self._models

    async def _build_feature_vector(self, db: AsyncSession) -> dict:
        """
        Assemble the feature vector from current DB state + market cache.
        """
        # Tension features — last snapshot per region
        stmt = (
            select(RegionSignal)
            .where(RegionSignal.timestamp >= text("NOW() - INTERVAL '2 hours'"))
        )
        result = await db.execute(stmt)
        signals = result.scalars().all()

        tensions = [s.tension_index for s in signals]
        features = {
            "global_tension_mean": float(np.mean(tensions)) if tensions else 50.0,
            "global_tension_max": float(np.max(tensions)) if tensions else 50.0,
            "global_tension_std": float(np.std(tensions)) if tensions else 0.0,
            "n_high_tension_regions": sum(1 for t in tensions if t > 60),
            "global_stress_delta_24h": float(
                np.mean([s.tension_delta_24h for s in signals if s.tension_delta_24h is not None])
            ) if signals else 0.0,
        }

        # Market features from cache
        market = MarketDataIngestor.load_cache()
        features["vix_current"] = market.get("vix", {}).get("price", 20.0)
        features["vix_pct_change_1h"] = market.get("vix", {}).get("pct_change_1h", 0.0)
        features["gold_price"] = market.get("gold", {}).get("price", 2000.0)
        features["gold_pct_change"] = market.get("gold", {}).get("pct_change_1h", 0.0)
        features["oil_wti_price"] = market.get("oil_wti", {}).get("price", 80.0)
        features["oil_pct_change"] = market.get("oil_wti", {}).get("pct_change_1h", 0.0)
        features["dxy"] = market.get("dxy", {}).get("price", 104.0)
        features["us10y"] = market.get("us10y", {}).get("price", 4.5)

        return features

    def _feature_vector_to_array(self, features: dict) -> np.ndarray:
        """Convert feature dict to ordered numpy array for model input."""
        feature_order = [
            "global_tension_mean", "global_tension_max", "global_tension_std",
            "n_high_tension_regions", "global_stress_delta_24h",
            "vix_current", "vix_pct_change_1h",
            "gold_price", "gold_pct_change",
            "oil_wti_price", "oil_pct_change",
            "dxy", "us10y",
        ]
        return np.array([[features.get(k, 0.0) for k in feature_order]])

    def _predict_from_features(self, features: dict, horizon: int = 24) -> dict:
        """
        Run model inference. Falls back to rule-based heuristic if no model.
        """
        models = self._load_models()

        if not models or horizon not in models:
            # Rule-based fallback (deterministic, interpretable)
            return self._heuristic_predict(features)

        X = self._feature_vector_to_array(features)
        horizon_models = models[horizon]

        vix_pred = horizon_models["vix"].predict(X)[0]        # class: 0=down, 1=neutral, 2=up
        gold_pred = horizon_models["gold"].predict(X)[0]
        oil_pred = horizon_models["oil"].predict(X)[0]
        risk_pred = horizon_models["risk"].predict(X)[0]      # 1–4

        label_map = {0: "down", 1: "neutral", 2: "up"}
        bias_map = {0: "bearish", 1: "neutral", 2: "bullish"}

        vix_proba = horizon_models["vix"].predict_proba(X)[0]
        gold_proba = horizon_models["gold"].predict_proba(X)[0]
        oil_proba = horizon_models["oil"].predict_proba(X)[0]

        return {
            "vix_direction": label_map.get(int(vix_pred), "neutral"),
            "vix_confidence": float(max(vix_proba)),
            "gold_bias": bias_map.get(int(gold_pred), "neutral"),
            "gold_confidence": float(max(gold_proba)),
            "oil_bias": bias_map.get(int(oil_pred), "neutral"),
            "oil_confidence": float(max(oil_proba)),
            "macro_risk_quartile": int(risk_pred),
        }

    def _heuristic_predict(self, features: dict) -> dict:
        """
        Deterministic rule-based fallback used when model isn't trained yet.
        Good enough for early demos. Replace with trained model ASAP.
        """
        tension = features.get("global_tension_mean", 50.0)
        delta = features.get("global_stress_delta_24h", 0.0)
        vix = features.get("vix_current", 20.0)

        # VIX: high tension + rising → up
        if tension > 65 or delta > 10:
            vix_dir, vix_conf = "up", 0.65
        elif tension < 35 and delta < 0:
            vix_dir, vix_conf = "down", 0.60
        else:
            vix_dir, vix_conf = "neutral", 0.50

        # Gold: safe haven — high tension = bullish
        if tension > 60:
            gold_bias, gold_conf = "bullish", 0.60
        elif tension < 40:
            gold_bias, gold_conf = "bearish", 0.55
        else:
            gold_bias, gold_conf = "neutral", 0.45

        # Oil: conflict = bullish, sanctions on producers = bullish
        oil_bias, oil_conf = ("bullish", 0.60) if tension > 55 else ("neutral", 0.45)

        # Risk quartile
        if tension > 75:
            risk_q = 4
        elif tension > 55:
            risk_q = 3
        elif tension > 35:
            risk_q = 2
        else:
            risk_q = 1

        return {
            "vix_direction": vix_dir,
            "vix_confidence": vix_conf,
            "gold_bias": gold_bias,
            "gold_confidence": gold_conf,
            "oil_bias": oil_bias,
            "oil_confidence": oil_conf,
            "macro_risk_quartile": risk_q,
        }

    async def run_and_store(self, db: AsyncSession) -> None:
        """Run predictions for all horizons and persist to DB."""
        features = await self._build_feature_vector(db)
        now = datetime.now(timezone.utc)

        for horizon in HORIZONS:
            pred = self._predict_from_features(features, horizon)
            signal = MarketSignal(
                timestamp=now,
                horizon_hours=horizon,
                feature_snapshot=features,
                **pred,
            )
            db.add(signal)

        await db.flush()
        log.info("Market signals written", horizons=HORIZONS)

    async def predict_counterfactual(
        self,
        region_code: str,
        tension_override: float,
        horizon_hours: int,
        db: AsyncSession,
    ) -> CounterfactualResponse:
        """
        Predict market signals with a hypothetical tension level for one region.
        Compares against current actual prediction to show delta.
        """
        # Build real features
        real_features = await self._build_feature_vector(db)
        real_pred = self._predict_from_features(real_features, horizon_hours)

        # Modify global tension to simulate the override
        # Simple approach: shift global_tension_mean by the delta
        stmt = select(RegionSignal.tension_index).where(
            RegionSignal.region_code == region_code
        ).order_by(RegionSignal.timestamp.desc()).limit(1)
        result = await db.execute(stmt)
        current_regional_tension = result.scalar_one_or_none() or real_features["global_tension_mean"]

        delta = tension_override - current_regional_tension
        cf_features = dict(real_features)
        cf_features["global_tension_mean"] = min(100, max(0, real_features["global_tension_mean"] + delta * 0.3))
        cf_features["global_tension_max"] = min(100, max(0, real_features["global_tension_max"] + delta * 0.5))

        cf_pred = self._predict_from_features(cf_features, horizon_hours)

        return CounterfactualResponse(
            region_code=region_code,
            tension_override=tension_override,
            predicted_vix_direction=cf_pred["vix_direction"],
            predicted_gold_bias=cf_pred["gold_bias"],
            predicted_oil_bias=cf_pred["oil_bias"],
            macro_risk_quartile=cf_pred["macro_risk_quartile"],
            confidence=(cf_pred["vix_confidence"] + cf_pred["gold_confidence"]) / 2,
            delta_vs_current={
                "vix_direction_changed": cf_pred["vix_direction"] != real_pred["vix_direction"],
                "gold_bias_changed": cf_pred["gold_bias"] != real_pred["gold_bias"],
                "oil_bias_changed": cf_pred["oil_bias"] != real_pred["oil_bias"],
                "risk_quartile_delta": cf_pred["macro_risk_quartile"] - real_pred["macro_risk_quartile"],
            },
        )

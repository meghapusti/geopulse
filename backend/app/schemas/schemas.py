"""
Pydantic v2 schemas — API request/response shapes.
Kept separate from ORM models (never expose ORM directly).
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ─── Article ──────────────────────────────────────────────────────────────────

class ArticleBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: str
    source_tier: int
    url: str
    title: str
    published_at: datetime
    countries: Optional[List[str]] = None
    event_type: Optional[str] = None
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None
    geopolitical_stress: Optional[float] = None
    cluster_id: Optional[int] = None
    cluster_label: Optional[str] = None


class ArticleDetail(ArticleBase):
    body: Optional[str] = None
    actors: Optional[List[str]] = None
    locations: Optional[Dict[str, Any]] = None
    event_confidence: Optional[float] = None


# ─── Region signals ───────────────────────────────────────────────────────────

class RegionSignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    region_code: str
    timestamp: datetime
    tension_index: float
    tension_delta_24h: Optional[float]
    conflict_score: Optional[float]
    sanctions_score: Optional[float]
    political_instability_score: Optional[float]
    economic_stress_score: Optional[float]
    article_count: int


class RegionSummary(BaseModel):
    """Lightweight summary used to colour the globe."""
    region_code: str
    tension_index: float
    tension_delta_24h: Optional[float]
    top_event_type: Optional[str]
    article_count: int
    last_updated: datetime


# ─── Market signals ───────────────────────────────────────────────────────────

class MarketSignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    horizon_hours: int
    vix_direction: Optional[str]
    vix_confidence: Optional[float]
    gold_bias: Optional[str]
    gold_confidence: Optional[float]
    oil_bias: Optional[str]
    oil_confidence: Optional[float]
    macro_risk_quartile: Optional[int]


# ─── Narratives ───────────────────────────────────────────────────────────────

class NarrativeClusterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cluster_id: int
    label: str
    keywords: Optional[List[str]]
    article_count: int
    avg_stress: Optional[float]
    countries: Optional[List[str]]
    stress_delta_7d: Optional[float]
    is_emerging: bool
    detected_at: datetime
    last_seen_at: datetime


# ─── Counterfactual ───────────────────────────────────────────────────────────

class CounterfactualRequest(BaseModel):
    region_code: str
    tension_override: float = Field(..., ge=0, le=100, description="Hypothetical tension index 0–100")
    horizon_hours: int = Field(24, ge=1, le=168)


class CounterfactualResponse(BaseModel):
    region_code: str
    tension_override: float
    predicted_vix_direction: str
    predicted_gold_bias: str
    predicted_oil_bias: str
    macro_risk_quartile: int
    confidence: float
    delta_vs_current: Dict[str, Any]  # how predictions shift vs current tension


# ─── Globe ────────────────────────────────────────────────────────────────────

class GlobeDataPoint(BaseModel):
    """One data point per country for the globe renderer."""
    region_code: str
    lat: float
    lon: float
    tension_index: float
    tension_delta_24h: Optional[float]
    article_count: int
    top_event_type: Optional[str]
    top_cluster_label: Optional[str]


class GlobeResponse(BaseModel):
    points: List[GlobeDataPoint]
    generated_at: datetime
    global_tension_avg: float


# ─── Alerts ───────────────────────────────────────────────────────────────────

class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    alert_type: str
    region_code: Optional[str]
    severity: str
    title: str
    body: str


class AlertSubscribeRequest(BaseModel):
    email: str
    regions: Optional[List[str]] = None         # None = all regions
    min_severity: str = "medium"
    commodities: Optional[List[str]] = None     # ["gold", "oil", "wheat"]


# ─── Backtesting ──────────────────────────────────────────────────────────────

class BacktestResult(BaseModel):
    start_date: datetime
    end_date: datetime
    accuracy: float
    precision: float
    recall: float
    f1: float
    correlation_with_vix: float
    notable_hits: List[Dict[str, Any]]   # events where model predicted correctly
    notable_misses: List[Dict[str, Any]]

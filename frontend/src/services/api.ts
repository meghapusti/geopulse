/**
 * GeoPulse API service.
 * All calls go through here — type-safe wrappers around axios.
 */
import axios from 'axios'

// In dev: Vite proxies /api → localhost:8000 (see vite.config.ts)
// In prod: VITE_API_BASE_URL is set to the Railway backend URL
const BASE = import.meta.env.VITE_API_BASE_URL
  ? `${import.meta.env.VITE_API_BASE_URL}/api/v1`
  : '/api/v1'

const api = axios.create({
  baseURL: BASE,
  timeout: 15000,
})

// ── Types ──────────────────────────────────────────────────────────────────

export interface GlobeDataPoint {
  region_code: string
  lat: number
  lon: number
  tension_index: number
  tension_delta_24h: number | null
  article_count: number
  top_event_type: string | null
  top_cluster_label: string | null
}

export interface GlobeResponse {
  points: GlobeDataPoint[]
  generated_at: string
  global_tension_avg: number
}

export interface RegionDetail {
  region_code: string
  tension_history: { timestamp: string; tension_index: number }[]
  recent_articles: {
    title: string
    url: string
    published_at: string
    source: string
    event_type: string | null
    sentiment_score: number | null
    geopolitical_stress: number | null
  }[]
}

export interface MarketSignal {
  timestamp: string
  horizon_hours: number
  vix_direction: 'up' | 'down' | 'neutral' | null
  vix_confidence: number | null
  gold_bias: 'bullish' | 'bearish' | 'neutral' | null
  gold_confidence: number | null
  oil_bias: 'bullish' | 'bearish' | 'neutral' | null
  oil_confidence: number | null
  macro_risk_quartile: 1 | 2 | 3 | 4 | null
}

export interface NarrativeCluster {
  id: number
  cluster_id: number
  label: string
  keywords: string[] | null
  article_count: number
  avg_stress: number | null
  countries: string[] | null
  stress_delta_7d: number | null
  is_emerging: boolean
  detected_at: string
  last_seen_at: string
}

export interface Article {
  id: string
  source: string
  source_tier: number
  url: string
  title: string
  published_at: string
  countries: string[] | null
  event_type: string | null
  sentiment_label: string | null
  sentiment_score: number | null
  geopolitical_stress: number | null
  cluster_id: number | null
  cluster_label: string | null
}

export interface CounterfactualResult {
  region_code: string
  tension_override: number
  predicted_vix_direction: string
  predicted_gold_bias: string
  predicted_oil_bias: string
  macro_risk_quartile: number
  confidence: number
  delta_vs_current: {
    vix_direction_changed: boolean
    gold_bias_changed: boolean
    oil_bias_changed: boolean
    risk_quartile_delta: number
  }
}

export interface BacktestResult {
  start_date: string
  end_date: string
  accuracy: number
  precision: number
  recall: number
  f1: number
  correlation_with_vix: number
  notable_hits: Record<string, unknown>[]
  notable_misses: Record<string, unknown>[]
}

// ── API calls ──────────────────────────────────────────────────────────────

export const globeApi = {
  getData: () => api.get<GlobeResponse>('/globe').then(r => r.data),
  getRegion: (code: string) => api.get<RegionDetail>(`/globe/region/${code}`).then(r => r.data),
}

export const signalsApi = {
  getLatest: (horizon = 24) =>
    api.get<MarketSignal[]>('/signals/latest', { params: { horizon } }).then(r => r.data),
  getHistory: (horizon = 24, days = 30) =>
    api.get<MarketSignal[]>('/signals/history', { params: { horizon, days } }).then(r => r.data),
}

export const narrativesApi = {
  getAll: (emergingOnly = false) =>
    api.get<NarrativeCluster[]>('/narratives', { params: { emerging_only: emergingOnly } }).then(r => r.data),
}

export const articlesApi = {
  getRecent: (params?: { region?: string; event_type?: string; hours?: number; limit?: number }) =>
    api.get<Article[]>('/articles', { params }).then(r => r.data),
}

export const counterfactualApi = {
  predict: (region_code: string, tension_override: number, horizon_hours = 24) =>
    api.post<CounterfactualResult>('/counterfactual', {
      region_code, tension_override, horizon_hours,
    }).then(r => r.data),
}

export const alertsApi = {
  subscribe: (email: string, regions?: string[], commodities?: string[]) =>
    api.post('/alerts/subscribe', { email, regions, commodities }).then(r => r.data),
}

export const backtestApi = {
  run: (start_date: string, end_date: string, horizon_hours = 24) =>
    api.get<BacktestResult>('/backtesting', {
      params: { start_date, end_date, horizon_hours },
    }).then(r => r.data),
}

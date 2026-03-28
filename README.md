# GeoPulse

A real-time geopolitical intelligence platform that ingests global news, runs transformer-based NLP analysis, clusters emerging macro narratives, and predicts commodity/volatility signals — visualised on an interactive 3D world map.

## Architecture

```
geopulse/
├── backend/          # FastAPI — ingestion, NLP, signals, REST API
├── frontend/         # React + Globe.gl — 3D map, dashboard, event cards
├── notebooks/        # Colab/Kaggle training notebooks
├── infra/            # Docker, Railway configs
├── data/             # Gitignored local data cache
└── docs/             # Architecture diagrams, API docs
```

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy, Celery, Redis |
| Database | PostgreSQL + TimescaleDB |
| NLP | HuggingFace Transformers, SBERT, spaCy, HDBSCAN |
| Signals | LightGBM, scikit-learn |
| Frontend | React, Vite, Globe.gl, Recharts, Zustand |
| Deploy | Railway (backend + db), Vercel (frontend) |

## Data Sources

- **GDELT** — free geopolitical events database with geo-coordinates
- **RSS feeds** — Reuters, BBC, Al Jazeera, AP, Financial Times
- **Yahoo Finance / FRED** — oil, gold, VIX, macro indicators

## Layers

### 1. Ingestion
Scheduled RSS + GDELT pulls every 15 minutes. Raw articles normalised into a common schema and queued for NLP processing.

### 2. NLP Pipeline
- **Event classification** — DeBERTa-v3-small zero-shot (CPU-friendly, ~180MB)
- **Sentiment analysis** — FinBERT fine-tuned on geopolitical text
- **Narrative clustering** — SBERT embeddings + HDBSCAN (no fixed k)
- **NER** — spaCy `en_core_web_trf` for country/actor extraction

### 3. Signal Aggregation
- Per-region tension index with exponential time decay
- LightGBM predictor for VIX direction, gold/oil bias, macro risk quartile
- Temporal Fusion Transformer (optional upgrade) for multi-horizon forecasting
- Historical backtesting view against actual VIX

### 4. Extensions
- Commodity-specific risk screens (oil, gold, wheat, LNG)
- Narrative drift detection over time
- Counterfactual "what if" mode
- Source credibility weighting
- Push/email alerts on tension spikes

## Quickstart

```bash
# Clone and setup
git clone github.com/meghapusti/geopulse
cd geopulse

# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

## Training on Colab/Kaggle

Open notebooks in `notebooks/02_training/` on Google Colab (free T4 GPU).
Export quantized model weights to `data/models/` for CPU inference in production.

---
title: FormulAI Backend API
emoji: 🏎️
colorFrom: yellow
colorTo: yellow
sdk: docker
pinned: false
---

# 🏎️ F1 Podium Predictor

Multi-stage ML pipeline for predicting Formula 1 podium finishers using historical telemetry, live data, and state-of-the-art Learning-to-Rank (LTR) algorithms.

## Architecture

```
Auxiliary Deep Heads (DNF & Pace) → LTR Ensemble (XGBoost/LightGBM) → Softmax Calibration
```

**Data Sources:** FastF1 • Jolpica API • OpenF1 API • Open-Meteo

## Quick Start

### 1. Install

```bash
cd F1PodiumPredictor
pip install -e ".[dev]"
cp .env.example .env
```

### 2. Ingest Historical Data

```bash
python scripts/ingest_historical.py --start-year 2014 --end-year 2024
```

### 3. Train Model

```bash
# Hyperparameter tuning across 200 trials maximizing NDCG@3 (~45 min)
python scripts/deep_tune.py

# Final training (compiles ltr_ranker.joblib from config)
python -m models_v2.training --no-optimize
```

### 4. Backtest

```bash
python scripts/rolling_backtest.py --test-year 2024
```

### 5. Run API + Next.js Intelligence Center

```bash
# API (Terminal 1)
uv run uvicorn api.main:app --reload --port 8000

# Frontend Next.js Dashboard (Terminal 2)
cd frontend_v2
npm run dev
```

### Or via Docker

```bash
docker-compose up --build
```

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | Health check |
| `GET /api/v1/predict/{year}/{round}/full-race` | Native LTR predictions + Plackett-Luce upset likelihoods |
| `GET /api/v1/predict/{year}/{round}/live` | LTR prior + Bayesian live updates (Live telemetry) |
| `GET /api/v1/predict/{year}/{round}/simulate` | LTR prior + Counterfactual modifiers |
| `GET /api/v1/races/{year}` | Race calendar |
| `GET /api/v1/evaluation` | Historical Backtest Accuracy |

## Features Engineered (25+)

- **Qualifying:** grid position, gap to pole, Q3 reached, consistency
- **Form:** last 3/5 race avg, podium rate, DNF rate, circuit history
- **Standings:** driver & constructor championship position/points
- **Constructor:** reliability rate, teammate qualifying gap
- **Context:** circuit type, overtake difficulty, home race, season progress, weather
- **Elo System:** head-to-head dynamic rankings

## Model Architecture

- **Auxiliary Heads:** XGBClassifier (DNF Prob) & XGBRegressor (Pace Delta)
- **LTR Ranker:** XGBoost (rank:ndcg) + LightGBM (lambdarank) optimized for NDCG@3
- **Softmax:** Ranking scores mapped to true probabilities summing to 1.0 across the grid
- **Monte Carlo:** 10K simulations for Plackett-Luce upset probabilities

## Tests

```bash
pytest tests/ -v
```

## Automation (Cron Scheduling)

To automatically ingest the latest race data and retrain models in production:

```bash
# Ingest latest race data every Monday at 02:00 AM
0 2 * * 1 cd /path/to/F1PodiumPredictor && .venv/bin/python scripts/ingest_historical.py --latest >> /var/log/f1_ingest.log 2>&1

# Retrain the model on the 1st of every month at 03:00 AM
0 3 1 * * cd /path/to/F1PodiumPredictor && .venv/bin/python -m models_v2.training --no-optimize >> /var/log/f1_train.log 2>&1
```

## Project Layout

```
F1PodiumPredictor/
├── config/           # Settings, circuit metadata
├── data/             # API clients, DB, ingestion
├── features/         # Feature engineering (pre-race + live)
├── models_v2/           # LTR Ensemble, Training, Evaluation
├── api/              # FastAPI application
├── frontend_v2/      # Next.js 14 Dashboard
├── scripts/          # CLI tools (ingest, deep_tune, backtest)
└── tests/            # Test suite
```

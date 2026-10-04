---
title: FormulAI Backend API
emoji: 🏎️
colorFrom: yellow
colorTo: yellow
sdk: docker
pinned: false
---

# 🏎️ F1 Podium Predictor

Predicts Formula 1 podiums with gradient-boosted learning-to-rank models over
leak-free pre-race features, and turns the scores into calibrated
probabilities with an exact Plackett-Luce layer.

## Architecture (v4)

```
Jolpica / Open-Meteo ─▶ SQLite ─▶ v4 features (features/fast_features.py)
                                      │   strictly-before-the-race history, built in ~2 s
                                      ▼
            PodiumPredictor (models_v2/podium_predictor.py)
              post-qualifying blend  ┐  LambdaMART rankers + rank-ordered logit,
              pre-qualifying blend   ┘  members picked by the walk-forward lab
                                      │
                                      ▼
            Plackett-Luce layer ─▶ P(win), P(P2), P(P3), P(podium) (sums to 3)
```

$RESULTS_LINE

**Data Sources:** Jolpica API (results, qualifying, sprints, standings, pit stops) • Open-Meteo (race weather) • FastF1 / OpenF1 (live endpoints)

## Quick Start

### 1. Install

```bash
uv sync --extra dev
cp .env.example .env
```

### 2. Ingest data

```bash
# Full history (first run), then incremental top-ups
uv run python scripts/ingest_historical.py --start-year 2014 --latest --incremental
uv run python scripts/ingest_weather.py --start-year 2014 --end-year 2026
```

### 3. Backtest, train and forecast

```bash
# Walk-forward backtest of a season + forecast of the next race;
# --save-model stores the all-data model used by the API
uv run python scripts/rolling_backtest.py --test-year 2026 --save-model

# Or just train/save the production model
uv run python -m models_v2.podium_predictor
```

### 4. Compare models (optional, slow)

```bash
# One process per season/regime, then aggregate
uv run python scripts/model_lab.py run --season 2025 --regime post
uv run python scripts/model_lab.py aggregate   # -> reports/model_lab/summary.json
```

### 5. Run API + Next.js dashboard

```bash
uv run uvicorn api.main:app --reload --port 8000   # Terminal 1
cd frontend && npm run dev                          # Terminal 2
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

## Features (v4, `features/fast_features.py`)

- **This weekend (post-qualifying only):** grid slot, quali position, gap to pole (%), Q1 gap, teammate grid gap, sprint result
- **Driver form:** exponentially weighted finish / points / podium / win / grid / positions gained / DNF rate, in-season points and averages, circuit history, Elo
- **Team (car) form:** the same for both cars, in-season averages, circuit history, team Elo with regression to the mean after regulation resets
- **Field-relative:** each driver's rank in this field on the key form signals
- **Context:** round, regulation-reset season flag, years into the rules era, street circuit, rain

Every rolling feature is joined with `merge_asof(..., allow_exact_matches=False)`,
so a race can only see races strictly before it (`tests/test_fast_features.py`).

## Model

- **Members:** LightGBM / XGBoost LambdaMART rankers (linear-gain top-10 relevance) and a Plackett-Luce rank-ordered logit; each regime blends z-scored member scores.
- **Probabilities:** exact Plackett-Luce over ordered top-3 triples, temperature fitted on out-of-sample races by podium log-loss.
- **Regimes:** post-qualifying (grid known) and pre-qualifying (no weekend data) are separate models; the forecast picks the one that matches what is known.
- The legacy LTR ensemble (`models_v2/ltr_ranker.py`) stays as the API's fallback.

## Tests

```bash
uv run pytest tests/ -v
```

## Automation (Cron Scheduling)

The GitHub Actions workflow (`.github/workflows/f1_pipeline.yml`) does this every 6 hours. Equivalent cron:

```bash
# Every 6 hours: top up data, backtest the season, retrain, forecast the next race
0 */6 * * * cd /path/to/F1PodiumPredictor && .venv/bin/python scripts/ingest_historical.py --start-year 2014 --latest --incremental && .venv/bin/python scripts/automated_pipeline.py >> /var/log/f1_pipeline.log 2>&1
```

## Project Layout

```
F1PodiumPredictor/
├── config/           # Settings, circuit metadata
├── data/             # API clients, DB, ingestion
├── features/         # Feature engineering (pre-race + live)
├── models_v2/        # PodiumPredictor (v4), legacy LTR ensemble, live/simulation stages
├── api/              # FastAPI application
├── frontend/         # Next.js dashboard
├── scripts/          # CLI tools (ingest, backtest, model lab, pipeline)
├── reports/          # Model lab results and model reports
└── tests/            # Test suite
```

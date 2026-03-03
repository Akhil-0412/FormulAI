# 🏎️ F1 Podium Predictor

Multi-stage ML pipeline for predicting Formula 1 podium finishers using historical and real-time data.

## Architecture

```
Stage 1 (Pre-Race) → Stage 2 (Live) → Stage 3 (Ensemble + Constraints)
  XGBoost + LightGBM    Bayesian Updater    Exactly 3 drivers + Monte Carlo
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
python scripts/ingest_historical.py --start-year 2018 --end-year 2024
```

### 3. Train Model

```bash
# With Optuna hyperparameter optimization (~20 min)
python scripts/train_model.py --train-start 2018 --train-end 2023 --val-year 2024

# Quick training (no optimization, ~2 min)
python scripts/train_model.py --no-optimize
```

### 4. Backtest

```bash
python scripts/backtest.py --test-year 2024
```

### 5. Run API + Dashboard

```bash
# API
uvicorn api.main:app --reload --port 8000

# Dashboard (separate terminal)
streamlit run dashboard/app.py
```

### Or via Docker

```bash
docker-compose up --build
```

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | Health check |
| `GET /api/v1/predict/{year}/{round}` | Pre-race podium prediction |
| `GET /api/v1/predict/{year}/{round}/monte-carlo` | Monte Carlo simulation |
| `GET /api/v1/races/{year}` | Race calendar |
| `GET /api/v1/standings/{year}` | Championship standings |

## Features Engineered (25+)

- **Qualifying:** grid position, gap to pole, Q3 reached, consistency
- **Form:** last 3/5 race avg, podium rate, DNF rate, circuit history
- **Standings:** driver & constructor championship position/points
- **Constructor:** reliability rate, teammate qualifying gap
- **Context:** circuit type, overtake difficulty, home race, season progress, weather

## Model Architecture

- **Head A (Classifier):** XGBoost binary → P(podium | driver, race)
- **Head B (Regressor):** LightGBM → predicted finish position
- **Constraint Enforcement:** Exactly 3 drivers, ranked P1/P2/P3
- **Monte Carlo:** 10K simulations for confidence intervals and combo probabilities

## Tests

```bash
pytest tests/ -v
```

## Automation (Cron Scheduling)

To automatically ingest the latest race data and retrain models in production, you can set up cron jobs. 
Since `scripts/ingest_historical.py` supports the `--latest` flag, it will dynamically fetch the current season's data.

Add the following to your crontab (`crontab -e`):

```bash
# Ingest latest race data every Monday at 02:00 AM
0 2 * * 1 cd /path/to/F1PodiumPredictor && .venv/bin/python scripts/ingest_historical.py --latest >> /var/log/f1_ingest.log 2>&1

# Retrain the model on the 1st of every month at 03:00 AM
0 3 1 * * cd /path/to/F1PodiumPredictor && .venv/bin/python scripts/train_model.py --no-optimize >> /var/log/f1_train.log 2>&1
```

## Project Layout

```
F1PodiumPredictor/
├── config/           # Settings, circuit metadata
├── data/             # API clients, DB, ingestion
├── features/         # Feature engineering (pre-race + live)
├── models/           # Stage 1/2/3, training, evaluation
├── api/              # FastAPI application
├── dashboard/        # Streamlit dashboard
├── scripts/          # CLI tools (ingest, train, backtest)
└── tests/            # Test suite
```

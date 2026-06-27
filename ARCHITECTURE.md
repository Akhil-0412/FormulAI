# FormulAI — Architecture Documentation

> Multi-stage ML pipeline for predicting Formula 1 podium finishers.

## System Overview

```
                    ┌──────────────────────────────────────────────────────────────┐
                    │                    DATA SOURCES                              │
                    │  Jolpica API  ·  FastF1  ·  OpenF1 API  ·  Open-Meteo       │
                    └──────────┬───────────────────────────────┬───────────────────┘
                               │                               │
                    ┌──────────▼──────────┐       ┌────────────▼────────────┐
                    │  Historical Ingest   │       │   Live Race Ingest      │
                    │  (scripts/ingest)    │       │   (OpenF1 streaming)    │
                    └──────────┬──────────┘       └────────────┬────────────┘
                               │                               │
                    ┌──────────▼──────────┐       ┌────────────▼────────────┐
                    │    SQLite DB         │       │   Live Feature Builder   │
                    │  (data/db.py)        │       │  (features/live_race)    │
                    └──────────┬──────────┘       └────────────┬────────────┘
                               │                               │
                    ┌──────────▼──────────┐                    │
                    │  Pre-Race Features   │                    │
                    │  (features/pre_race) │                    │
                    └──────────┬──────────┘                    │
                               │                               │
             ┌─────────────────▼─────────────────┐             │
             │        STAGE 1: PRE-RACE           │             │
             │  Head A: XGBoost  → P(podium)      │             │
             │  Head B: LightGBM → E[position]    │             │
             └─────────────────┬─────────────────┘             │
                               │ (prior probabilities)         │
                               ▼                               ▼
             ┌─────────────────────────────────────────────────────┐
             │           STAGE 2: LIVE BAYESIAN UPDATER            │
             │  Posterior(t) ∝ Likelihood(data_t) × Prior(t-1)     │
             │  Regime: Normal | Safety Car | Pit Phase             │
             └─────────────────┬───────────────────────────────────┘
                               │ (posterior probabilities)
                               ▼
             ┌─────────────────────────────────────────────────────┐
             │      STAGE 3: ENSEMBLE + CONSTRAINT ENFORCEMENT     │
             │  Softmax over -E[position] (Plackett-Luce proxy)    │
             │  → Select exactly 3 drivers: P1, P2, P3             │
             │  → Monte Carlo simulation (10K draws)                │
             └─────────────────┬───────────────────────────────────┘
                               │
                               ▼
             ┌─────────────────────────────────────────────────────┐
             │        STAGE 4: COUNTERFACTUAL SIMULATOR            │
             │  Forward MC simulation from current lap to end      │
             │  Perturbs α (gap penalty) and β (tyre degradation)  │
             │  Scenarios: rain, safety car, forced pit, DNF       │
             └─────────────────────────────────────────────────────┘
```

## Data Layer

### Data Sources

| Source | Type | Used For |
|---|---|---|
| **Jolpica API** | REST (ergast-compatible) | Race results, qualifying, standings, pit stops, schedule |
| **FastF1** | Python library | Telemetry, session data (currently imported but minimally used) |
| **OpenF1 API** | REST | Live race data: laps, intervals, stints, race control messages |
| **Open-Meteo** | REST | Race-day weather forecasts |

### SQLite Schema (9 tables)

| Table | Primary Key | Description |
|---|---|---|
| `races` | `race_id` (`{year}_{round}`) | Race calendar + metadata |
| `drivers` | `driver_id` | Driver registry (42 drivers) |
| `constructors` | `constructor_id` | Team registry |
| `results` | `(race_id, driver_id)` | Race outcomes (position, status, points, is_podium) |
| `qualifying` | `(race_id, driver_id)` | Q1/Q2/Q3 lap times |
| `practice_sessions` | `(race_id, driver_id, session_type)` | FP1/FP2/FP3 data (currently **not** used in features) |
| `pit_stops` | `(race_id, driver_id, stop_number)` | Pit stop timing |
| `weather` | `race_id` | Weather conditions (currently **empty** — fetched on-demand) |
| `standings_snapshot` | `(race_id, driver_id)` | Championship standings before each race |
| `predictions` | `race_id` | Stored predictions for dashboard |

### Current Data Coverage

- **44 races** across 9 seasons (2018–2026), ~5 races per season (partial)
- **866 result entries**, **879 qualifying entries**, **1501 pit stops**
- **Class balance**: 130 podiums (15%) / 736 non-podiums (85%)

## Feature Engineering

### Pre-Race Features (25+)

| Category | Features | Source |
|---|---|---|
| **Qualifying** | `grid_position`, `quali_gap_to_pole`, `quali_q3_reached`, `quali_consistency` | `qualifying` table |
| **Recent Form** | `driver_last3_avg_pos`, `driver_last5_podium_rate`, `driver_last5_avg_pos`, `driver_recent_dnf_rate` | `results` (historical) |
| **Circuit History** | `driver_circuit_avg_pos`, `driver_circuit_best_pos` | `results` × `races` |
| **Standings** | `driver_championship_pos`, `driver_championship_pts`, `constructor_championship_pos`, `constructor_championship_pts` | `standings_snapshot` |
| **Constructor** | `constructor_reliability`, `constructor_season_reliability`, `constructor_circuit_reliability`, `constructor_survival_prob`, `teammate_quali_gap` | `results` (historical) |
| **Context** | `circuit_type`, `circuit_overtake_difficulty`, `home_race`, `season_progress` | `circuits.json` + `drivers` |

### Live Features (Stage 2 input)

| Feature | Source |
|---|---|
| `current_position`, `gap_to_leader`, `gap_to_driver_ahead` | OpenF1 `/intervals` |
| `positions_gained` | Derived from interval history |
| `avg_lap_time_last5`, `lap_time_trend`, `best_lap_time` | OpenF1 `/laps` |
| `pit_stops_made`, `is_pit_phase` | OpenF1 `/pit` |
| `compound_age`, `current_compound` | OpenF1 `/stints` |
| `safety_car_active`, `safety_car_count` | OpenF1 `/race_control` |

## Model Architecture

### Stage 1: Pre-Race Predictor (`models_v2/ltr_ranker.py`)

**Learning-to-Rank Ensemble:**

- **XGBoost LambdaMART**: Trained with `rank:ndcg` to predict a continuous ranking score.
- **LightGBM LambdaRank**: Trained with `lambdarank` and optimized for NDCG@3.
- Both use historical F1 Points allocations as their relevance label array to heavily penalize missing podium spots versus shuffling mid-field positions.
- **Auxiliary Heads**: DNF probability and Pace deltas are predicted via separate sub-models and injected directly as dynamic features into the LTR models_v2.
- **Prediction**: Raw ranking scores are converted via a temperature-calibrated softmax into podium probabilities.

### Stage 2: Live Bayesian Updater (`models_v2/stage2_live.py`)

**Two strategies:**

1. **Bayesian** (default): State-space filter
   ```
   L_i(t) = exp(-α · gap_i(t) - β · tyre_age_i(t))
   Posterior_i = Prior_i × effective_likelihood_i
   ```
   - Regime-switching: α, β conditioned on normal/SC/pit-phase
   - Compound-dependent β (SOFT: 0.015, MEDIUM: 0.01, HARD: 0.005)
   - Burn-in attenuation for early-race stability
   - Position bonus for track leaders

2. **Blended** (fallback): Weighted average
   ```
   weight_live = sigmoid((lap - midpoint) / temperature)
   P_final = (1 - w) × P_stage1 + w × P_live
   ```

### Stage 3: Constraint Enforcement (`models_v2/stage3_ensemble.py`)

**Plackett-Luce proxy:**
```
score_i = softmax(-E[position_i] / τ)    where τ = 3.0
```
- Top 3 by softmax score → P1, P2, P3
- Confidence level: `margin = score_P3 - score_P4`
- Monte Carlo: 10K weighted draws, tracks combo frequencies + per-position probabilities

### Stage 4: Counterfactual Simulator (`models_v2/stage4_simulator.py`)

- Recovers latent Stage 1 priors from Stage 2 posteriors
- Forward-simulates remaining laps with stochastic events:
  - Safety car injection (Bernoulli per lap)
  - Rain onset at specified lap
  - Forced pit stops for specific drivers
  - DNF hazard model (per-lap probability)
- Aggregates over N runs → mean probabilities, deltas, uncertainty

## Training Pipeline

### Temporal Cross-Validation (`models_v2/train.py`)

```
Fold 1: Train 2018–2020 → Calibrate 2021 → Validate 2021
Fold 2: Train 2018–2021 → Calibrate 2022 → Validate 2022
Fold 3: Train 2018–2022 → Calibrate 2023 → Validate 2023
Final:  Train 2018–2022 → Calibrate 2023 → Test 2024
```

Each fold: Train → Isotonic Calibrate → Evaluate

### Evaluation (`models_v2/evaluate.py`)

Race-level metrics:
- Correct podium count (0–3)
- All-3, ≥2, ≥1 correct rates
- AUC-ROC, log loss, Brier score (per-driver binary classification)
- Position MAE (regressor head)
- Confidence level distribution

### Rolling Backtest (`scripts/rolling_backtest.py`)

Online learning: after predicting each race, the race is added to training data and the model is retrained. Produces `data/rolling_backtest_{year}.json` for dashboard consumption.

## API Layer (`api/main.py`)

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check (model loaded, DB connected) |
| `/api/v1/predict/{year}/{round}` | GET | Pre-race podium prediction (Stage 1 → Stage 3) |
| `/api/v1/predict/{year}/{round}/live` | GET | Live prediction (Stage 1 → 2 → 3) |
| `/api/v1/predict/{year}/{round}/simulate` | POST | Counterfactual simulation (Stage 4) |
| `/api/v1/predict/{year}/{round}/monte-carlo` | GET | Monte Carlo simulation |
| `/api/v1/predict/{year}/{round}/full-race` | GET | Full prediction + weather + circuit + grid |
| `/api/v1/race_center/{year}/{round}` | GET | Aggregated race center data |
| `/api/v1/races/{year}` | GET | Race calendar |
| `/api/v1/standings/{year}` | GET | Championship standings |
| `/api/v1/evaluation` | GET | Historical evaluation summary |
| `/api/v1/chat` | POST | ParcFermé AI chatbot (LangGraph) |

## Chatbot: ParcFermé AI (`api/chatbot/`)

LangGraph agent with 7-node graph:
```
START → query_understanding → confidence_gate
  ├─ HIGH   → agent (LLM + tools) → answer_validator → generate_json → END
  ├─ MEDIUM → clarification → generate_json → END
  └─ LOW    → rephrase → generate_json → END
```

- LLM: Groq (Llama-3.1-8B-Instant)
- Tools: driver lineup, regulations, champions, stats, telemetry
- Cross-turn entity memory via MemorySaver checkpointer

## Frontend

- **Next.js** app (`frontend/`) — deployed on Vercel
- **Streamlit** dashboard (`dashboard/`) — local development
- Both consume the FastAPI backend

## Deployment

- **Docker**: Single-stage Python 3.11-slim image
- **Port**: 7860 (HuggingFace Spaces convention)
- **Compose**: API service only

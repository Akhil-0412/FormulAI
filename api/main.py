"""FastAPI application — serves podium predictions."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.schemas import (
    DriverPrediction,
    DriverProbability,
    HealthResponse,
    MonteCarloResponse,
    MonteCarloResult,
    PodiumPredictionResponse,
    RaceInfo,
    SimulationResponse,
    SimulationDriverResult,
    GridPosition,
    RaceCenterMetrics,
    RaceCenterResponse,
    FullRaceWeather,
    CircuitInfo,
    ModelParameter,
    FullGridDriver,
    FullRacePredictionResponse,
)
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    text_response: str
    metadata: Dict[str, Any]
    visualizations: List[Dict[str, Any]] = []
    tables: List[Dict[str, Any]] = []
from config.settings import settings
from data.db import get_connection, init_db, query_df
from features.pre_race import build_pre_race_features
from features.feature_store import get_X_y
from models.stage1_prerace import PreRacePredictor
from models.stage3_ensemble import enforce_podium_constraints, monte_carlo_podium

logger = logging.getLogger(__name__)

# ── Global state ────────────────────────────────────────────────────────
_model: PreRacePredictor | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup."""
    global _model
    init_db()
    model_path = settings.abs_model_dir / "stage1_prerace.joblib"
    if model_path.exists():
        _model = PreRacePredictor.load(model_path)
        logger.info("Model loaded from %s", model_path)
    else:
        logger.warning("No model found at %s — prediction endpoints will fail", model_path)
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="F1 Podium Predictor API",
    description="Multi-stage ML pipeline for predicting Formula 1 podium finishers",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ──────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health_check():
    db_ok = False
    try:
        with get_connection():
            db_ok = True
    except Exception:
        pass

    return HealthResponse(
        status="ok",
        model_loaded=_model is not None and _model.is_fitted,
        db_connected=db_ok,
    )


# ── Pre-race prediction ────────────────────────────────────────────────

@app.get("/api/v1/predict/{year}/{round_number}", response_model=PodiumPredictionResponse)
def predict_podium(year: int, round_number: int):
    """Get pre-race podium prediction for a specific race."""
    if _model is None or not _model.is_fitted:
        raise HTTPException(503, "Model not loaded. Train the model first.")

    # Build features
    race_df = build_pre_race_features(year, round_number)
    if race_df.empty:
        raise HTTPException(404, f"No data available for {year} R{round_number}")

    X, _ = get_X_y(race_df, "is_podium")
    driver_ids = race_df["driver_id"].tolist()

    # Predict
    podium_probs = _model.predict_podium_proba(X)
    position_preds = _model.predict_position(X)

    prob_dict = dict(zip(driver_ids, podium_probs.tolist()))
    pos_dict = dict(zip(driver_ids, position_preds.tolist()))

    # Enforce constraints
    result = enforce_podium_constraints(prob_dict, pos_dict)

    # Get race info
    race_info = _get_race_info(year, round_number)

    return PodiumPredictionResponse(
        race=race_info,
        predictions=[
            DriverPrediction(
                driver_id=str(p.driver_id),
                predicted_position=p.predicted_position,
                probability=round(p.probability, 4),
                confidence=round(p.confidence, 4),
            )
            for p in result.podium
        ],
        full_grid=[
            DriverProbability(driver_id=str(d), podium_probability=round(p, 4))
            for d, p in sorted(result.full_grid.items(), key=lambda x: x[1], reverse=True)
        ],
        prediction_type="pre_race",
        confidence_level=result.confidence_level,
    )


@app.get("/api/v1/race_center/{year}/{round_number}", response_model=RaceCenterResponse)
def get_race_center(year: int, round_number: int):
    """Get aggregated data for the unified Race Center dashboard view."""
    
    # Get basic race info
    race_info = _get_race_info(year, round_number)
    
    # Get grid (qualifying results) and actual race results if any
    grid = []
    actual_podium = []
    is_completed = False
    
    with get_connection() as conn:
        q_df = pd.read_sql_query(
            "SELECT driver_id, position FROM results WHERE race_id = ? ORDER BY grid ASC",
            conn, params=(race_info.race_id,)
        )
        if not q_df.empty:
            for _, row in q_df.iterrows():
                grid.append(GridPosition(
                    driver_id=row["driver_id"], 
                    position=row.get("position"),
                    points=None
                ))
            
            # Check for actual results
            actual_df = pd.read_sql_query(
                "SELECT driver_id, position FROM results WHERE race_id = ? AND position <= 3 ORDER BY position ASC",
                conn, params=(race_info.race_id,)
            )
            if not actual_df.empty and len(actual_df) >= 3:
                is_completed = True
                actual_podium = actual_df["driver_id"].tolist()
        
    predictions_list = []
    full_probs_list = []
    
    # Try to load prediction from Rolling Backtest JSON (faster, uses online learning)
    rolling_file = Path(__file__).resolve().parent.parent / "data" / f"rolling_backtest_{year}.json"
    used_rolling = False
    
    if rolling_file.exists():
        import json
        try:
            with open(rolling_file, "r") as f:
                bt_results = json.load(f)
            # Find this round
            for r in bt_results:
                if r["round"] == round_number:
                    # Construct pseudo-predictions from JSON
                    for i, drv in enumerate(r["predicted"]):
                        predictions_list.append(DriverPrediction(
                            driver_id=drv, predicted_position=i+1, probability=r.get("probabilities", {}).get(drv, 0.5), confidence=1.0
                        ))
                    
                    for drv, prob in r.get("probabilities", {}).items():
                        full_probs_list.append(DriverProbability(driver_id=drv, podium_probability=prob))
                        
                    used_rolling = True
                    break
        except Exception as e:
            logger.warning("Could not read rolling backtest: %s", e)
            
    # Fallback to predicting on the fly using Live Predictor Stage 1
    if not used_rolling:
        if _model is not None and _model.is_fitted:
            try:
                race_df = build_pre_race_features(year, round_number)
                if not race_df.empty:
                    X, _ = get_X_y(race_df, "is_podium")
                    driver_ids = race_df["driver_id"].tolist()
                    
                    podium_probs = _model.predict_podium_proba(X)
                    pos_preds = _model.predict_position(X)
                    
                    prob_dict = dict(zip(driver_ids, podium_probs.tolist()))
                    pos_dict = dict(zip(driver_ids, pos_preds.tolist()))
                    
                    from models.stage3_ensemble import enforce_podium_constraints
                    result = enforce_podium_constraints(prob_dict, pos_dict)
                    
                    predictions_list = [
                        DriverPrediction(
                            driver_id=str(p.driver_id),
                            predicted_position=p.predicted_position,
                            probability=round(p.probability, 4),
                            confidence=round(p.confidence, 4)
                        ) for p in result.podium
                    ]
                    
                    full_probs_list = [
                        DriverProbability(driver_id=str(d), podium_probability=round(p, 4))
                        for d, p in sorted(result.full_grid.items(), key=lambda x: x[1], reverse=True)
                    ]
            except Exception as e:
                logger.error("Failed to build fallback predictions: %s", e)
                
    # Calculate metrics if completed
    correct_count = None
    if is_completed and len(predictions_list) == 3:
        pred_ids = [p.driver_id for p in predictions_list]
        correct_count = len(set(pred_ids).intersection(set(actual_podium)))
        
    return RaceCenterResponse(
        race=race_info,
        grid=grid,
        predictions=predictions_list,
        full_grid_probs=full_probs_list,
        actual_podium=actual_podium,
        metrics=RaceCenterMetrics(correct_podiums=correct_count, is_completed=is_completed)
    )

# ── Live race prediction (Stage 2) ─────────────────────────────────────

@app.get("/api/v1/predict/{year}/{round_number}/live", response_model=PodiumPredictionResponse)
def predict_podium_live(year: int, round_number: int, lap: int | None = None):
    """Get live race prediction via Bayesian State-Space Filter (Stage 2)."""
    if _model is None or not _model.is_fitted:
        raise HTTPException(503, "Model not loaded. Train the model first.")

    # 1. Base Stage 1 Predictions (Our Priors)
    race_df = build_pre_race_features(year, round_number)
    if race_df.empty:
        raise HTTPException(404, f"No pre-race data for {year} R{round_number}")

    X, _ = get_X_y(race_df, "is_podium")
    driver_ids = race_df["driver_id"].tolist()
    
    podium_probs = _model.predict_podium_proba(X)
    pre_race_probs_str = dict(zip(driver_ids, podium_probs.tolist()))

    # 2. Driver mapping (DB text ID -> OpenF1 Number)
    drivers_df = query_df("SELECT * FROM drivers")
    id_to_code = dict(zip(drivers_df["driver_id"], drivers_df["code"]))
    code_to_id = dict(zip(drivers_df["code"], drivers_df["driver_id"]))

    race_info = _get_race_info(year, round_number)

    # 3. Fetch Live Data
    from data.openf1_client import OpenF1Client
    from features.live_race import build_live_features_all_drivers
    from models.stage2_live import LiveRaceUpdater
    
    client = OpenF1Client()
    try:
        # Search OpenF1 session
        search_query = race_info.country if race_info.country else race_info.circuit_name
        session_key = client.get_session_key(year, search_query, session_type="Race")
        if not session_key:
            # Fallback to pure prior if live data isn't found
            logger.warning(f"No OpenF1 session found for {year} R{round_number}. Falling back to Prior.")
            result = enforce_podium_constraints(pre_race_probs_str, position_preds=None)
            return PodiumPredictionResponse(
                race=race_info,
                predictions=[
                    DriverPrediction(
                        driver_id=str(p.driver_id),
                        predicted_position=p.predicted_position,
                        probability=round(p.probability, 4),
                        confidence=round(p.confidence, 4),
                    ) for p in result.podium
                ],
                full_grid=[
                    DriverProbability(driver_id=str(d), podium_probability=round(p, 4))
                    for d, p in sorted(result.full_grid.items(), key=lambda x: x[1], reverse=True)
                ],
                prediction_type="live",
                lap_number=0,
                confidence_level=result.confidence_level,
            )

        openf1_drivers = client.get_drivers(session_key)
        num_to_id = {}
        for d in openf1_drivers:
            num = d.get("driver_number")
            code = d.get("name_acronym")
            if num and code and code in code_to_id:
                num_to_id[num] = code_to_id[code]
                
        # {driver_number: prior_prob}
        prior_probs_num = {num: pre_race_probs_str.get(did, 0.05) for num, did in num_to_id.items()}

        laps_data = client.get_laps(session_key)
        intervals = client.get_intervals(session_key)
        pits = client.get_pit_stops(session_key)
        stints = client.get_stints(session_key)
        race_control = client.get_race_control(session_key)

        if not lap:
            lap = max([l.get("lap_number", 1) for l in laps_data] + [1])

        driver_data = {}
        for num in num_to_id.keys():
            driver_data[num] = {
                "laps": [x for x in laps_data if x.get("driver_number") == num and x.get("lap_number", 0) <= lap],
                "intervals": [x for x in intervals if x.get("driver_number") == num],
                "pit": [x for x in pits if x.get("driver_number") == num and x.get("lap", 0) <= lap],
                "stints": [x for x in stints if x.get("driver_number") == num]
            }

        total_laps_df = query_df("SELECT total_laps FROM races WHERE race_id=?", (race_info.race_id,))
        total_laps = int(total_laps_df.iloc[0]["total_laps"]) if not total_laps_df.empty and pd.notna(total_laps_df.iloc[0]["total_laps"]) else 50

        # Build feature matrix
        live_features_df = build_live_features_all_drivers(
            driver_data, current_lap=lap, total_laps=total_laps, race_control=race_control
        )

        # 4. Bayesian Update
        updater = LiveRaceUpdater(strategy="bayesian")
        updated_probs_num = updater.update(prior_probs_num, live_features_df, current_lap=lap, total_laps=total_laps)

        # Convert back to driver_id
        updated_probs_str = {}
        for num, prob in updated_probs_num.items():
            if num in num_to_id:
                updated_probs_str[num_to_id[num]] = prob

        # Inject missing drivers from prior
        for did, prob in pre_race_probs_str.items():
            if did not in updated_probs_str:
                updated_probs_str[did] = prob

        # 5. Stage 3 Plackett-Luce Constraints Check
        result = enforce_podium_constraints(updated_probs_str, position_preds=None)

        return PodiumPredictionResponse(
            race=race_info,
            predictions=[
                DriverPrediction(
                    driver_id=str(p.driver_id),
                    predicted_position=p.predicted_position,
                    probability=round(p.probability, 4),
                    confidence=round(p.confidence, 4),
                )
                for p in result.podium
            ],
            full_grid=[
                DriverProbability(driver_id=str(d), podium_probability=round(p, 4))
                for d, p in sorted(result.full_grid.items(), key=lambda x: x[1], reverse=True)
            ],
            prediction_type="live",
            lap_number=lap,
            confidence_level=result.confidence_level,
        )

    finally:
        client.close()


# ── Counterfactual Simulation (Stage 4) ───────────────────────────────

@app.post("/api/v1/predict/{year}/{round_number}/simulate", response_model=SimulationResponse)
def predict_podium_simulate(year: int, round_number: int, request: SimulationRequest, lap: int | None = None):
    """Run Stage 4 counterfactual simulation from current posterior."""
    if _model is None or not _model.is_fitted:
        raise HTTPException(503, "Model not loaded.")

    # 1. Base Stage 1 Predictions
    race_df = build_pre_race_features(year, round_number)
    if race_df.empty:
        raise HTTPException(404, f"No pre-race data for {year} R{round_number}")

    X, _ = get_X_y(race_df, "is_podium")
    driver_ids = race_df["driver_id"].tolist()
    
    podium_probs = _model.predict_podium_proba(X)
    pre_race_probs_str = dict(zip(driver_ids, podium_probs.tolist()))

    drivers_df = query_df("SELECT * FROM drivers")
    id_to_code = dict(zip(drivers_df["driver_id"], drivers_df["code"]))
    code_to_id = dict(zip(drivers_df["code"], drivers_df["driver_id"]))

    race_info = _get_race_info(year, round_number)

    # 2. Fetch Live Data
    from data.openf1_client import OpenF1Client
    from features.live_race import build_live_features_all_drivers
    from models.stage2_live import LiveRaceUpdater
    from models.stage4_simulator import simulate_forward
    from api.schemas import SimulationDriverResult
    
    client = OpenF1Client()
    try:
        search_query = race_info.country if race_info.country else race_info.circuit_name
        session_key = client.get_session_key(year, search_query, session_type="Race")
        if not session_key:
            raise HTTPException(404, "No live OpenF1 session found for simulation.")

        openf1_drivers = client.get_drivers(session_key)
        num_to_id = {}
        for d in openf1_drivers:
            num = d.get("driver_number")
            code = d.get("name_acronym")
            if num and code and code in code_to_id:
                num_to_id[num] = code_to_id[code]
                
        prior_probs_num = {num: pre_race_probs_str.get(did, 0.05) for num, did in num_to_id.items()}

        laps_data = client.get_laps(session_key)
        intervals = client.get_intervals(session_key)
        pits = client.get_pit_stops(session_key)
        stints = client.get_stints(session_key)
        race_control = client.get_race_control(session_key)

        if not lap:
            lap = max([l.get("lap_number", 1) for l in laps_data] + [1])

        driver_data = {}
        for num in num_to_id.keys():
            driver_data[num] = {
                "laps": [x for x in laps_data if x.get("driver_number") == num and x.get("lap_number", 0) <= lap],
                "intervals": [x for x in intervals if x.get("driver_number") == num],
                "pit": [x for x in pits if x.get("driver_number") == num and x.get("lap", 0) <= lap],
                "stints": [x for x in stints if x.get("driver_number") == num]
            }

        total_laps_df = query_df("SELECT total_laps FROM races WHERE race_id=?", (race_info.race_id,))
        total_laps = int(total_laps_df.iloc[0]["total_laps"]) if not total_laps_df.empty and pd.notna(total_laps_df.iloc[0]["total_laps"]) else 50

        # Build feature matrix
        live_features_df = build_live_features_all_drivers(
            driver_data, current_lap=lap, total_laps=total_laps, race_control=race_control
        )

        # 3. Get Current Posterior (Stage 2) over driver numbers
        updater = LiveRaceUpdater(strategy="bayesian")
        updated_probs_num = updater.update(prior_probs_num, live_features_df, current_lap=lap, total_laps=total_laps)
        
        scenario_params = request.model_dump()
        
        sim_result = simulate_forward(
            current_state_df=live_features_df,
            current_posterior_probs=updated_probs_num,
            scenario_params=scenario_params,
            total_laps=total_laps,
            current_lap=lap,
            n_runs=request.n_runs,
        )
        
        if not sim_result:
            raise HTTPException(500, "Simulation failed.")
            
        driver_results = []
        for num_str, stats in sim_result["drivers"].items():
            num = int(num_str)
            if num in num_to_id:
                driver_results.append(
                    SimulationDriverResult(
                        driver_id=num_to_id[num],
                        baseline_prob=round(stats["baseline_prob"], 4),
                        simulated_prob=round(stats["simulated_prob"], 4),
                        delta_prob=round(stats["delta_prob"], 4),
                        uncertainty_std=round(stats["uncertainty_std"], 4),
                    )
                )
                
        driver_results.sort(key=lambda x: x.delta_prob, reverse=True)
        
        pos_affected = str(num_to_id.get(sim_result["most_positively_affected"])) if sim_result["most_positively_affected"] in num_to_id else None
        neg_affected = str(num_to_id.get(sim_result["most_negatively_affected"])) if sim_result["most_negatively_affected"] in num_to_id else None

        return SimulationResponse(
            race=race_info,
            lap_number=lap,
            n_runs=request.n_runs,
            sc_prob_multiplier=request.sc_prob_multiplier,
            most_positively_affected=pos_affected,
            most_negatively_affected=neg_affected,
            drivers=driver_results
        )

    finally:
        client.close()


# ── Monte Carlo prediction ─────────────────────────────────────────────

@app.get("/api/v1/predict/{year}/{round_number}/monte-carlo", response_model=MonteCarloResponse)
def predict_monte_carlo(year: int, round_number: int, n_simulations: int = 10000):
    """Run Monte Carlo simulation for podium predictions."""
    if _model is None or not _model.is_fitted:
        raise HTTPException(503, "Model not loaded.")

    race_df = build_pre_race_features(year, round_number)
    if race_df.empty:
        raise HTTPException(404, f"No data for {year} R{round_number}")

    X, _ = get_X_y(race_df, "is_podium")
    driver_ids = race_df["driver_id"].tolist()
    podium_probs = _model.predict_podium_proba(X)
    prob_dict = dict(zip(driver_ids, podium_probs.tolist()))

    mc_result = monte_carlo_podium(prob_dict, n_simulations=n_simulations)

    # Build position probabilities
    results = []
    for driver_id in driver_ids:
        pos_probs = mc_result["position_probability"].get(driver_id, {1: 0, 2: 0, 3: 0})
        results.append(MonteCarloResult(
            driver_id=str(driver_id),
            podium_probability=round(mc_result["podium_probability"].get(driver_id, 0), 4),
            p1_probability=round(pos_probs.get(1, 0), 4),
            p2_probability=round(pos_probs.get(2, 0), 4),
            p3_probability=round(pos_probs.get(3, 0), 4),
        ))
    results.sort(key=lambda r: r.podium_probability, reverse=True)

    race_info = _get_race_info(year, round_number)

    return MonteCarloResponse(
        race=race_info,
        results=results,
        most_likely_combo=[str(d) for d in mc_result["most_likely_combo"]],
        most_likely_combo_probability=round(mc_result["most_likely_combo_probability"], 4),
        n_simulations=n_simulations,
    )


# ── Full Race Prediction ────────────────────────────────────────────────

# Circuit metadata for laps / distance
_CIRCUIT_RACE_INFO = {
    "albert_park": {"laps": 58, "lap_distance_km": 5.278},
    "bahrain": {"laps": 57, "lap_distance_km": 5.412},
    "jeddah": {"laps": 50, "lap_distance_km": 6.174},
    "suzuka": {"laps": 53, "lap_distance_km": 5.807},
    "shanghai": {"laps": 56, "lap_distance_km": 5.451},
    "miami": {"laps": 57, "lap_distance_km": 5.412},
    "imola": {"laps": 63, "lap_distance_km": 4.909},
    "monaco": {"laps": 78, "lap_distance_km": 3.337},
    "montreal": {"laps": 70, "lap_distance_km": 4.361},
    "barcelona": {"laps": 66, "lap_distance_km": 4.675},
    "silverstone": {"laps": 52, "lap_distance_km": 5.891},
    "spa": {"laps": 44, "lap_distance_km": 7.004},
    "monza": {"laps": 53, "lap_distance_km": 5.793},
    "singapore": {"laps": 62, "lap_distance_km": 4.940},
    "yas_marina": {"laps": 58, "lap_distance_km": 5.281},
}

_MODEL_PARAMETERS = [
    ModelParameter(name="Grid Position", description="Qualifying result — strongest single predictor of race outcome", category="qualifying", impact="HIGH"),
    ModelParameter(name="Quali Gap to Pole", description="Time delta to pole-sitter in qualifying (seconds)", category="qualifying", impact="HIGH"),
    ModelParameter(name="Q3 Reached", description="Whether the driver qualified in the top-10 shootout", category="qualifying", impact="MEDIUM"),
    ModelParameter(name="Driver Last 5 Avg Pos", description="Average finishing position over recent 5 races", category="driver_form", impact="HIGH"),
    ModelParameter(name="Driver Last 3 Avg Pos", description="Short-term form over the last 3 races", category="driver_form", impact="HIGH"),
    ModelParameter(name="Podium Rate (Last 5)", description="Percentage of podium finishes in last 5 races", category="driver_form", impact="MEDIUM"),
    ModelParameter(name="Recent DNF Rate", description="Retirement frequency in recent races", category="driver_form", impact="MEDIUM"),
    ModelParameter(name="Circuit Avg Position", description="Historical average finish at this specific circuit", category="track", impact="HIGH"),
    ModelParameter(name="Circuit Best Position", description="Best-ever finish at this circuit", category="track", impact="MEDIUM"),
    ModelParameter(name="Championship Position", description="Current driver standings position", category="constructor", impact="MEDIUM"),
    ModelParameter(name="Championship Points", description="Accumulated season points", category="constructor", impact="LOW"),
    ModelParameter(name="Constructor Reliability", description="Team mechanical finish rate over last 20 races", category="constructor", impact="MEDIUM"),
    ModelParameter(name="Overtake Difficulty", description="Circuit-specific difficulty of overtaking (0=easy, 1=impossible)", category="track", impact="MEDIUM"),
    ModelParameter(name="Circuit Type", description="Street / Technical / High-Speed classification", category="track", impact="LOW"),
    ModelParameter(name="Temperature", description="Race-day maximum air temperature (°C)", category="weather", impact="LOW"),
    ModelParameter(name="Precipitation Probability", description="Chance of rain during the race (%)", category="weather", impact="HIGH"),
    ModelParameter(name="Wind Speed", description="Maximum wind speed at circuit (km/h)", category="weather", impact="LOW"),
    ModelParameter(name="Humidity", description="Relative humidity affecting tire degradation (%)", category="weather", impact="LOW"),
]


@app.get("/api/v1/predict/{year}/{round_number}/full-race", response_model=FullRacePredictionResponse)
def predict_full_race(year: int, round_number: int, n_simulations: int = 10000):
    """Comprehensive full-race prediction with weather, circuit, and all grid positions."""
    if _model is None or not _model.is_fitted:
        raise HTTPException(503, "Model not loaded.")

    # 1. Race features
    race_df = build_pre_race_features(year, round_number)
    if race_df.empty:
        raise HTTPException(404, f"No data for {year} R{round_number}")

    race_info = _get_race_info(year, round_number)

    # 2. Weather
    try:
        from data.weather_client import WeatherClient
        wc = WeatherClient()
        # Determine circuit key from race info
        circuit_id = query_df("SELECT circuit_id FROM races WHERE race_id = ?", (f"{year}_{round_number}",))
        ckey = circuit_id.iloc[0]["circuit_id"] if not circuit_id.empty else "albert_park"
        weather_data = wc.get_forecast(ckey, race_info.race_date or "2026-03-15")
        circuit_meta = wc.get_circuit_info(ckey) or {}
        wc.close()
    except Exception as e:
        logger.warning("Weather fetch failed: %s", e)
        weather_data = {"temperature": 28, "precipitation_prob": 10, "wind_speed": 15, "humidity": 60, "weather_code": 1, "condition": "dry"}
        circuit_meta = {"type": "street", "overtake_difficulty": 0.6}
        ckey = "albert_park"

    weather = FullRaceWeather(**weather_data)

    race_meta = _CIRCUIT_RACE_INFO.get(ckey, {"laps": 58, "lap_distance_km": 5.278})
    circuit = CircuitInfo(
        circuit_id=ckey,
        circuit_type=circuit_meta.get("type", "technical"),
        overtake_difficulty=circuit_meta.get("overtake_difficulty", 0.5),
        laps=race_meta["laps"],
        lap_distance_km=race_meta["lap_distance_km"],
        lat=circuit_meta.get("lat"),
        lon=circuit_meta.get("lon"),
    )

    # 3. Model predictions
    X, _ = get_X_y(race_df, "is_podium")
    driver_ids = race_df["driver_id"].tolist()
    constructor_ids = race_df["constructor_id"].tolist() if "constructor_id" in race_df.columns else [""] * len(driver_ids)

    podium_probs = _model.predict_podium_proba(X)
    position_preds = _model.predict_position(X)
    prob_dict = dict(zip(driver_ids, podium_probs.tolist()))

    # Monte Carlo for position-specific probabilities
    mc_result = monte_carlo_podium(prob_dict, n_simulations=n_simulations)

    # Constructor reliability for DNF risk
    reliability = {}
    for i, did in enumerate(driver_ids):
        cid = constructor_ids[i] if i < len(constructor_ids) else ""
        rel_df = query_df(
            "SELECT status FROM results WHERE constructor_id = ? ORDER BY race_id DESC LIMIT 20",
            (cid,),
        )
        if not rel_df.empty:
            finished = rel_df["status"].apply(lambda s: s == "Finished" or (s and str(s).startswith("+"))).sum()
            reliability[did] = finished / len(rel_df)
        else:
            reliability[did] = 0.9

    # Build sorted full grid
    grid_entries = []
    for i, did in enumerate(driver_ids):
        pos_probs = mc_result["position_probability"].get(did, {1: 0, 2: 0, 3: 0})
        cid = constructor_ids[i] if i < len(constructor_ids) else ""
        rel = reliability.get(did, 0.9)
        dnf_risk = round(1.0 - rel, 3)

        # Estimate lap time from predicted position (rough approximation)
        pred_pos = position_preds[i]
        base_lap = 82.0  # approximate for Albert Park
        estimated_lap = base_lap + (pred_pos - 1) * 0.3

        if rel >= 0.95:
            dnf_note = f"Low — {cid.replace('_', ' ').title()} reliability {rel*100:.0f}%"
        elif rel >= 0.85:
            dnf_note = f"Moderate — {cid.replace('_', ' ').title()} reliability {rel*100:.0f}%"
        else:
            dnf_note = f"Elevated — {cid.replace('_', ' ').title()} reliability {rel*100:.0f}%"

        grid_entries.append(FullGridDriver(
            position=0,  # will be set after sorting
            driver_id=str(did),
            podium_probability=round(mc_result["podium_probability"].get(did, 0), 4),
            p1_probability=round(pos_probs.get(1, 0), 4),
            p2_probability=round(pos_probs.get(2, 0), 4),
            p3_probability=round(pos_probs.get(3, 0), 4),
            expected_lap_time_sec=round(estimated_lap, 3),
            dnf_risk=dnf_risk,
            dnf_note=dnf_note,
            constructor_id=cid,
        ))

    # Sort by predicted position (use position_preds for ordering)
    driver_pos = dict(zip(driver_ids, position_preds.tolist()))
    grid_entries.sort(key=lambda g: driver_pos.get(g.driver_id, 99))
    for idx, entry in enumerate(grid_entries):
        entry.position = idx + 1

    # Top 3 podium
    podium = [str(d) for d in mc_result["most_likely_combo"]]

    return FullRacePredictionResponse(
        race=race_info,
        weather=weather,
        circuit=circuit,
        parameters=_MODEL_PARAMETERS,
        full_grid=grid_entries,
        podium=podium,
        confidence_level="high" if mc_result["most_likely_combo_probability"] > 0.05 else "medium",
        n_simulations=n_simulations,
    )


# ── Data endpoints ──────────────────────────────────────────────────────

@app.get("/api/v1/races/{year}")
def get_races(year: int):
    """Get race calendar for a season."""
    df = query_df("SELECT * FROM races WHERE year = ? ORDER BY round", (year,))
    return df.to_dict("records")


@app.get("/api/v1/standings/{year}")
def get_standings(year: int):
    """Get latest standings snapshot for a season."""
    df = query_df(
        """SELECT ss.*, d.full_name, d.code
           FROM standings_snapshot ss
           JOIN drivers d ON ss.driver_id = d.driver_id
           WHERE ss.race_id LIKE ?
           ORDER BY ss.position""",
        (f"{year}_%",),
    )
    if df.empty:
        return []
    # Return latest round's standings
    latest_race = df["race_id"].max()
    return df[df["race_id"] == latest_race].to_dict("records")


# ── Helpers ─────────────────────────────────────────────────────────────

def _get_race_info(year: int, round_number: int) -> RaceInfo:
    """Fetch race info from DB."""
    race_id = f"{year}_{round_number}"
    df = query_df("SELECT * FROM races WHERE race_id = ?", (race_id,))
    if df.empty:
        return RaceInfo(race_id=race_id, year=year, round=round_number)
    row = df.iloc[0]
    return RaceInfo(
        race_id=race_id,
        year=year,
        round=round_number,
        circuit_name=row.get("circuit_name", ""),
        country=row.get("country", ""),
        race_date=str(row.get("race_date", "")),
    )

# ── ParcFermé AI Chatbot ──────────────────────────────────────────────────

@app.post("/api/v1/chat", response_model=ChatResponse)
def parc_ferme_chat(request: ChatRequest):
    """
    Agentic RAG Endpoint for ParcFermé AI using LangGraph.
    Returns structured JSON according to the F1 Strategic Intelligence Engine spec.
    """
    from api.chatbot.agent import chat_with_agent
    
    res = chat_with_agent(request.message, thread_id="default_thread")
    
    return ChatResponse(
        text_response=res.get("text_response", ""),
        metadata=res.get("metadata", {}),
        visualizations=res.get("visualizations", []),
        tables=res.get("tables", [])
    )

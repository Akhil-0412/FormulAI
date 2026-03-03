"""Pydantic schemas for API request/response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RaceInfo(BaseModel):
    race_id: str
    year: int
    round: int
    circuit_name: str = ""
    country: str = ""
    race_date: str = ""


class DriverPrediction(BaseModel):
    driver_id: str
    predicted_position: int = Field(ge=1, le=3)
    probability: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0)


class GridPosition(BaseModel):
    driver_id: str
    position: int | None
    points: float | None

class RaceCenterMetrics(BaseModel):
    correct_podiums: int | None
    is_completed: bool

class RaceCenterResponse(BaseModel):
    race: RaceInfo
    grid: list[GridPosition]
    predictions: list[DriverPrediction]
    full_grid_probs: list[DriverProbability]
    actual_podium: list[str]
    metrics: RaceCenterMetrics


class DriverProbability(BaseModel):
    driver_id: str
    podium_probability: float = Field(ge=0.0, le=1.0)


class PodiumPredictionResponse(BaseModel):
    race: RaceInfo
    predictions: list[DriverPrediction]
    full_grid: list[DriverProbability]
    model_version: str = "0.1.0"
    prediction_type: Literal["pre_race", "live"] = "pre_race"
    lap_number: int | None = None
    confidence_level: Literal["high", "medium", "low"] = "medium"


class MonteCarloResult(BaseModel):
    driver_id: str
    podium_probability: float
    p1_probability: float
    p2_probability: float
    p3_probability: float


class MonteCarloResponse(BaseModel):
    race: RaceInfo
    results: list[MonteCarloResult]
    most_likely_combo: list[str]
    most_likely_combo_probability: float
    n_simulations: int


class ModelMetrics(BaseModel):
    total_races: int
    all_3_correct_pct: float
    at_least_2_pct: float
    at_least_1_pct: float
    avg_position_mae: float
    avg_brier_score: float
    avg_log_loss: float


class HealthResponse(BaseModel):
    status: str = "ok"
    model_loaded: bool = False
    db_connected: bool = False


class SimulationRequest(BaseModel):
    sc_prob_multiplier: float = 1.0
    rain_onset_lap: int | None = None
    early_pit_driver: int | None = None
    base_dnf_prob: float = 0.002
    n_runs: int = 1000


class SimulationDriverResult(BaseModel):
    driver_id: str
    baseline_prob: float
    simulated_prob: float
    delta_prob: float
    uncertainty_std: float


class SimulationResponse(BaseModel):
    race: RaceInfo
    lap_number: int
    n_runs: int
    sc_prob_multiplier: float
    most_positively_affected: str | None
    most_negatively_affected: str | None
    drivers: list[SimulationDriverResult]


# ── Full Race Prediction ─────────────────────────────────────────────────

class FullRaceWeather(BaseModel):
    temperature: float | None
    precipitation_prob: float | None
    wind_speed: float | None
    humidity: float | None
    weather_code: int | None
    condition: str = "unknown"

class CircuitInfo(BaseModel):
    circuit_id: str
    circuit_type: str = ""
    overtake_difficulty: float = 0.5
    laps: int = 58
    lap_distance_km: float = 5.278
    lat: float | None = None
    lon: float | None = None

class ModelParameter(BaseModel):
    name: str
    description: str
    category: str  # "weather", "driver_form", "track", "constructor", "qualifying"
    impact: str = "MEDIUM"  # HIGH, MEDIUM, LOW

class FullGridDriver(BaseModel):
    position: int
    driver_id: str
    podium_probability: float = 0.0
    p1_probability: float = 0.0
    p2_probability: float = 0.0
    p3_probability: float = 0.0
    expected_lap_time_sec: float | None = None
    dnf_risk: float = 0.05
    dnf_note: str = ""
    constructor_id: str = ""

class FullRacePredictionResponse(BaseModel):
    race: RaceInfo
    weather: FullRaceWeather
    circuit: CircuitInfo
    parameters: list[ModelParameter]
    full_grid: list[FullGridDriver]
    podium: list[str]
    confidence_level: str = "medium"
    n_simulations: int = 10000

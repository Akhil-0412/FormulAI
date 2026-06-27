"""Application settings loaded from environment / .env file."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the F1 Podium Predictor."""

    # ── Paths ───────────────────────────────────────────────────────────
    project_root: Path = Path(__file__).resolve().parent.parent
    db_path: str = "data/db/race_history.db"
    fastf1_cache_dir: str = "data/cache"
    model_dir: str = "models_v2/artifacts"

    # ── API base URLs ───────────────────────────────────────────────────
    openf1_base_url: str = "https://api.openf1.org/v1"
    jolpica_base_url: str = "https://api.jolpi.ca/ergast/f1"
    openmeteo_base_url: str = "https://api.open-meteo.com/v1/forecast"
    odds_api_key: str = ""

    # ── External Services ───────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    mlflow_tracking_uri: str = "./mlruns"

    # ── Feature Flags ───────────────────────────────────────────────────
    enable_odds_feature: bool = False
    enable_experimental_transformer: bool = False
    enable_drqn_agent: bool = False

    # ── Training defaults ───────────────────────────────────────────────
    train_start_year: int = 2018
    train_end_year: int = 2022
    val_year: int = 2023
    test_year: int = 2024

    # ── Model Versioning ────────────────────────────────────────────────
    model_version: str = "2.0.0"
    stage2_model_version: str = "latest"

    # ── Model hyper-param search ────────────────────────────────────────
    optuna_n_trials: int = 100
    random_seed: int = 42

    # ── Logging ─────────────────────────────────────────────────────────
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    # ── Derived helpers ─────────────────────────────────────────────────
    @property
    def abs_db_path(self) -> Path:
        return self.project_root / self.db_path

    @property
    def abs_cache_dir(self) -> Path:
        return self.project_root / self.fastf1_cache_dir

    @property
    def abs_model_dir(self) -> Path:
        return self.project_root / self.model_dir


settings = Settings()

import asyncio
import json
import logging
import sys
import subprocess
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.db import query_df, get_connection
from fastapi import FastAPI

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting Automated F1 Prediction Pipeline...")

    # 1. Ingest Latest Data (Results, Schedules, etc.)
    # Depending on how ingest_data is structured, we run it. 
    # For now, we assume data/ingest.py or similar is the entry point, but 
    # rolling_backtest.py fetches forward schedules anyway. Let's run rolling_backtest.py
    
    # Get the current year to backtest (usually the current calendar year)
    from datetime import datetime
    current_year = datetime.now().year
    
    logger.info(f"Running rolling backtest for {current_year} to update online learning weights...")
    try:
        subprocess.run(
            [sys.executable, "scripts/rolling_backtest.py", "--test-year", str(current_year), "--no-optimize"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Rolling backtest failed: {e}")
        return

    # 2. Determine Next Race
    # The backtest will have inserted the next race into the `races` table temporarily, or we can fetch the latest race.
    races_df = query_df("SELECT year, round FROM races WHERE year = ? ORDER BY round DESC LIMIT 1", (current_year,))
    
    if races_df.empty:
        logger.error(f"No races found for {current_year}.")
        return

    next_round = int(races_df.iloc[0]["round"])
    logger.info(f"Generating full-race prediction payload for {current_year} R{next_round}...")

    # 3. Generate FullRaceResponse using API logic
    from api.main import lifespan, predict_full_race
    app = FastAPI()
    
    async with lifespan(app):
        try:
            # Generate the prediction
            full_race_response = predict_full_race(current_year, next_round, n_simulations=5000)
            
            # Serialize to JSON
            out_dir = Path(__file__).resolve().parent.parent / "frontend" / "public" / "data"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / "latest_prediction.json"
            
            with open(out_file, "w") as f:
                # model_dump_json handles datetime and other types automatically
                f.write(full_race_response.model_dump_json(indent=2))
                
            logger.info(f"Successfully generated static prediction payload at {out_file}")
            
        except Exception as e:
            logger.error(f"Failed to generate full race prediction: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

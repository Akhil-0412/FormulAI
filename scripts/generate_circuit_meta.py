"""Generate circuit metadata by aggregating historical stats."""

import json
import logging
from config.settings import settings
from data.db import get_connection, upsert_circuit_meta

logger = logging.getLogger(__name__)

def generate_circuit_meta():
    """Load circuit metadata from config and upsert into database."""
    meta_file = settings.project_root / "config" / "circuit_meta.json"
    
    if not meta_file.exists():
        logger.error(f"Circuit meta file not found at {meta_file}")
        return

    with open(meta_file, 'r') as f:
        meta_data = json.load(f)
    
    circuits = meta_data.get("circuits", {})
    
    with get_connection() as conn:
        for circuit_id, data in circuits.items():
            record = {
                "circuit_id": circuit_id,
                "tyre_stress_index": data.get("tyre_stress_index", 0.5),
                "sc_probability": data.get("sc_probability", 0.0),
                "vsc_probability": data.get("vsc_probability", 0.0),
                "overtake_difficulty": data.get("overtake_difficulty", 0.5),
                "drs_zones": data.get("drs_zones", 1),
                "avg_pit_delta_s": data.get("avg_pit_delta_s", 22.0),
                "undercut_window_laps": data.get("undercut_window_laps", 2),
                "is_street_circuit": 1 if data.get("is_street_circuit") else 0
            }
            upsert_circuit_meta(conn, record)
            logger.info(f"Upserted meta for {circuit_id}")
    
    logger.info("Circuit metadata generation complete.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generate_circuit_meta()

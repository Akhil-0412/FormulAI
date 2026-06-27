"""Train GRU for live race embedding."""

import argparse
import logging
import torch
from models_v2.stage3_race import RacePredictor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, required=False, help="Path to training sequences")
    args = parser.parse_args()

    logger.info("Initializing Lap GRU model...")
    model = RacePredictor()

    # Dummy sequence data
    batch_size = 4
    seq_len = 10
    input_size = 10
    X_seq = torch.randn(batch_size, seq_len, input_size)
    y_pos = torch.randn(batch_size)

    logger.info("Training GRU...")
    model.fit(X_seq, y_pos, epochs=5)

    logger.info("Training complete.")

if __name__ == "__main__":
    main()

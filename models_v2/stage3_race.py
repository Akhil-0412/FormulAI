"""Stage 3 — Live race model incorporating Lap GRU and telemetry."""

import torch
import pandas as pd
import numpy as np
from typing import Any
from models_v2.heads.lap_gru import LapGRU

class RacePredictor:
    """Stage 3 model: continuous update during the race."""
    
    def __init__(self, gru_input_size: int = 10, gru_hidden_size: int = 64, config: dict | None = None):
        self.config = config
        self.lap_gru = LapGRU(input_size=gru_input_size, hidden_size=gru_hidden_size)
        self.fc_out = torch.nn.Linear(gru_hidden_size, 1) # Simple projection to position
        self.is_fitted = False
        self.optimizer = torch.optim.Adam(
            list(self.lap_gru.parameters()) + list(self.fc_out.parameters()), 
            lr=0.001
        )
        self.criterion = torch.nn.MSELoss()
        
    def fit(self, X_seq: torch.Tensor, y_pos: torch.Tensor, epochs: int = 10):
        """Train the GRU race embedding model."""
        self.lap_gru.train()
        self.fc_out.train()
        
        for epoch in range(epochs):
            self.optimizer.zero_grad()
            embedding, _ = self.lap_gru(X_seq)
            predictions = self.fc_out(embedding).squeeze(-1)
            loss = self.criterion(predictions, y_pos)
            loss.backward()
            self.optimizer.step()
            
        self.is_fitted = True

    def predict_position(self, X_seq: torch.Tensor) -> np.ndarray:
        """Predict race positions given sequential lap data."""
        if not self.is_fitted:
            raise ValueError("Model not fitted")
        
        self.lap_gru.eval()
        self.fc_out.eval()
        with torch.no_grad():
            embedding, _ = self.lap_gru(X_seq)
            predictions = self.fc_out(embedding).squeeze(-1)
            return predictions.numpy()

"""Lap GRU — Recurrent Neural Network for live race embedding."""

import torch
import torch.nn as nn

class LapGRU(nn.Module):
    def __init__(self, input_size: int, hidden_size: int = 64, num_layers: int = 2):
        super(LapGRU, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.gru = nn.GRU(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, hidden_size)

    def forward(self, x, h0=None):
        # x shape: (batch_size, sequence_length, input_size)
        out, hn = self.gru(x, h0)
        # out shape: (batch_size, seq_len, hidden_size)
        
        # take the last time step
        last_out = out[:, -1, :]
        embedding = torch.relu(self.fc(last_out))
        return embedding, hn

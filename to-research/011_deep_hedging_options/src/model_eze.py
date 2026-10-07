"""model_eze.py - Model inference wrapper and ChipEngine integration.

Extracted from video screen recordings (t=2:12, t=3:16, t=3:47, t=3:54).
"""
import json
import numpy as np
import torch
import torch.nn as nn
from infra import is_finite
from chip_tushare import get_chip_data


class ChipEngine:
    def __init__(self, symbol: str, n_rate: float = 0.0, base_row: str = "_rate"):
        self.symbol = symbol
        self.n_rate = n_rate
        self.base_row = base_row

    def call_network(self, resolve_path: str, st_imatreems: list, base: float, sleep: float, backoff: float):
        # Retry with exponential backoff
        pass

    def get_data(self, df):
        need_cols = {"trade_date", "winner_rate", "weight_avg", "cost_ISB", "cost_BSpeilt"}
        if not need_cols.issubset(set(df.columns)):
            return None
        return df


class ModelEze:
    def __init__(self, model_path: str = "best_model.pth"):
        self.model_path = model_path
        self.model = None

    def train_epoch(self, dataloader, optimizer, criterion):
        total_loss = 0.0
        correct = 0
        total = 0
        for x, labels in dataloader:
            optimizer.zero_grad()
            logits = self.model(x)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()

            preds = torch.argmax(logits, dim=-1)
            correct += (preds == labels).sum().item()
            total += labels.size(0)
            total_loss += loss.item()

        acc = correct / total if total > 0 else 0.0
        return total_loss, acc

    def predict(self, features):
        if self.model is None:
            raise RuntimeError("Model not loaded")
        with torch.no_grad():
            return self.model(features)

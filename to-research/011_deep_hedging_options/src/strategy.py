"""strategy.py - Options Strategy State Machine.

Extracted from video screen recordings (t=1:31, t=1:52, t=1:54, t=1:59).
Contains state-machine handling for IronCondor, Straddle, and variants.
"""
from typing import Optional


class Strategy:
    def __init__(self, config, executor):
        self.config = config
        self.executor = executor
        self.active_strategy: Optional[str] = None
        self.entry_portfolio_value: float = 0.0

    def execute_strategy(self, strategy_type: str, action: str, allocation: float) -> dict:
        return self.executor.execute(strategy_type, action, allocation)

    def process_prediction(self, prediction: int, probability: float, portfolio_value: float):
        # State machine derived from OCR (t=1:52-1:59)
        if prediction == 1 and self.active_strategy == "IronCondor":
            self.executor.execute_strategy("IronCondor", "close", 0.81)
            self.active_strategy = None

        if self.active_strategy is None and probability >= 0.6:
            allocation = portfolio_value * self.config.allocation_ratio + self.config.position_size
            self.executor.execute_strategy("Straddle", "buy", allocation)
            self.active_strategy = "Straddle"
            self.entry_portfolio_value = portfolio_value
            return

        if self.active_strategy is None and probability >= 0.51:
            allocation = portfolio_value * self.config.allocation_ratio + self.config.position_size
            self.executor.execute_strategy("IronCondor", "sell", allocation)
            self.active_strategy = "IronCondor"
            self.entry_portfolio_value = portfolio_value

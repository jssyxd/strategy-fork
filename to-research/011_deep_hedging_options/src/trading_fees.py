"""trading_fees.py - Binance and XT fee rate calculations.

Extracted from video screen recordings (t=3:47, t=3:54).
Code reference: Binance WNSTICE PXR
"""


def compute_trading_fee(volume: float, fee_rate: float = 0.001) -> float:
    return volume * fee_rate


def total_transaction_cost(trades: list) -> float:
    """Computes total transaction cost across executed trades."""
    return sum(t.get("cost", 0.0) for t in trades)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Strategy Signal & Math Module for 007 ETH AI Timing (AlphaEvolve GP + Q-State 15m)
Strictly matches ETH_AI_Timing_AlphaEvolve_15m.pine and smc_eth_007_live.py.
"""
from __future__ import annotations

import math
from collections import deque
from typing import Optional, List, Dict, Any

# Parameters matching Pine script
GAMMA: float = 0.88       # Q-State discount factor
ALPHA: float = 0.12       # TD state learning rate
LOOKBACK: int = 20        # SMA & STDEV window
THRESH: float = 1.20      # Signal threshold for entry
TP_PCT: float = 0.0090    # Take profit 0.90%
SL_PCT: float = 0.0250    # Stop loss 2.50%
FIRST_RATIO: float = 0.50 # Initial position ratio (50% of available cash)
ADD_RATIO: float = 0.75   # Add position ratio (75% of remaining cash)
TAKER_FEE: float = 0.0005 # Taker fee 0.05% (5 bps)


class AlphaEvolveSignal:
    """Pine Script Q-State + Price Z-Score Composite Signal.
    Updated once per confirmed 15m bar.
    """

    def __init__(self) -> None:
        self.closes: deque[float] = deque(maxlen=LOOKBACK)
        self.q_val: float = 0.0
        self.value: Optional[float] = None
        self.bars: int = 0

    def update(self, o: float, h: float, l: float, c: float) -> Optional[float]:
        hl_range = h - l
        k_pos = (c - l) / (hl_range + 1e-6)
        hl_spread = hl_range / (c + 1e-6)

        # 1. Q-State value iteration (temporal difference recursion)
        # Pine: reward_step = k_pos * 15.0 + hl_spread * 0.8
        #       q_val := (gamma_decay * nz(q_val[1])) + (alpha_learn * reward_step)
        reward_step = k_pos * 15.0 + hl_spread * 0.8
        self.q_val = GAMMA * self.q_val + ALPHA * reward_step

        # 2. Price Z-Score + Q-State Resonance
        self.closes.append(c)
        self.bars += 1
        if len(self.closes) < LOOKBACK:
            self.value = None
            return None

        n = len(self.closes)
        mean = sum(self.closes) / n
        var = sum((x - mean) ** 2 for x in self.closes) / n  # Population variance (Pine biased=true)
        sd = math.sqrt(var)
        part_a = (c - mean) / sd if sd > 0 else 0.0

        if self.q_val > 0.05:
            part_a += 0.3
        elif self.q_val < -0.05:
            part_a -= 0.3

        self.value = part_a
        return self.value


def compute_all_signals(bars: List[Dict[str, Any]]) -> List[Optional[float]]:
    """Compute signals causally across an ordered sequence of bars."""
    sig_engine = AlphaEvolveSignal()
    signals = []
    for b in bars:
        sig = sig_engine.update(b["open"], b["high"], b["low"], b["close"])
        signals.append(sig)
    return signals

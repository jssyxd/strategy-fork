#!/usr/bin/env python3
"""
Autoresearch Canonical Benchmark Harness
Executes deterministic event-driven backtest on the governed crypto universe.
Outputs standardized METRIC lines for the optimization loop.
"""
from __future__ import annotations

import sys
import os
import math
import time
import re
from decimal import Decimal
import pandas as pd
import numpy as np

sys.path.append("/workspace/demo盘的策略")
from smc_live_trader import SMCLiveConfig, SMCLiveStrategy, PortfolioCoordinator
from nautilus_trader.common import LoggerConfig
from nautilus_trader.backtest import BacktestEngine, BacktestEngineConfig
from nautilus_trader.execution import MakerTakerFeeModel
from nautilus_trader.model import (
    Bar, BarType, BarSpecification, BarAggregation, PriceType, AggregationSource,
    InstrumentId, Price, Quantity, Currency, Money, AccountType, OmsType, Venue,
    CryptoPerpetual, Symbol, StrategyId
)

class SMCBenchmarkStrategy(SMCLiveStrategy):
    def on_start(self) -> None:
        iid = InstrumentId.from_str(self.cfg.instrument_id)
        spec = BarSpecification(15, BarAggregation.MINUTE, PriceType.LAST)
        bar_type = BarType(iid, spec, AggregationSource.EXTERNAL)
        self.subscribe_bars(bar_type)

def run_benchmark():
    PortfolioCoordinator.active_instruments.clear()
    PortfolioCoordinator.pending_candidates.clear()
    PortfolioCoordinator.flush_timer_active = False

    @classmethod
    def backtest_flush_and_execute(cls) -> None:
        if not cls.pending_candidates:
            return
        candidates = list(cls.pending_candidates.values())
        cls.pending_candidates.clear()
        cls.flush_timer_active = False
        x = len(candidates)
        sample_strat = candidates[0]["strategy"]
        account = sample_strat.portfolio.account(venue=Venue("OKX"))
        free_bal = account.balance_free(Currency.from_str("USDT")) if account else None
        equity = float(free_bal.as_double()) if free_bal is not None else 0.0
        if equity < 100.0:
            return
        total_score = sum(c["score"] for c in candidates)
        weights = {c["symbol"]: c["score"] / (total_score + 1e-9) for c in candidates}
        pool_margin = equity * 0.90
        for cand in candidates:
            strat = cand["strategy"]
            sym = cand["symbol"]
            w = weights[sym]
            c_price = cand["c"]
            sl_dist = cand["sl_dist"]
            direction = cand["direction"]
            alloc_margin = pool_margin * w
            margin_per_ct = (c_price * strat.cfg.ct_val) / 3.0
            max_cts_by_margin = math.floor(alloc_margin / (margin_per_ct + 1e-9))
            if max_cts_by_margin < 1:
                continue
            risk_budget = (equity * strat.cfg.risk_pct) * (w * x)
            risk_per_ct = sl_dist * strat.cfg.ct_val
            target_cts_risk = math.floor(risk_budget / (risk_per_ct + 1e-9)) if risk_per_ct > 0 else 1
            contracts = max(1, min(target_cts_risk, max_cts_by_margin, 500))
            if not cls.can_open_position(sym):
                continue
            strat._execute_entry_order(direction, contracts, c_price, cand["atr"], sl_dist, risk_budget)

    @classmethod
    def immediate_reg(cls, strategy, candidate):
        cls.pending_candidates[candidate["symbol"]] = candidate
        cls.flush_and_execute()

    PortfolioCoordinator.flush_and_execute = backtest_flush_and_execute
    PortfolioCoordinator.register_candidate = immediate_reg

    engine = BacktestEngine(BacktestEngineConfig(
        logging=LoggerConfig.from_spec("stdout=Error"),
        bypass_logging=True,
    ))

    fee_model = MakerTakerFeeModel(maker_rate=Decimal("0.0002"), taker_rate=Decimal("0.0005"))
    engine.add_venue(
        venue=Venue("OKX"),
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        starting_balances=[Money.from_str("100000 USDT")],
        base_currency=Currency.from_str("USDT"),
        default_leverage=Decimal("3.0"),
        fee_model=fee_model,
    )

    portfolio_matrix = [
        ("BTC-USDT-SWAP", "BTCUSDT", 0.01, 1, "001", 70.0),
        ("ETH-USDT-SWAP", "ETHUSDT", 0.10, 2, "002", 70.0),
        ("SOL-USDT-SWAP", "SOLUSDT", 1.00, 2, "003", 70.0),
        ("BNB-USDT-SWAP", "BNBUSDT", 0.01, 1, "004", 70.0),
    ]

    all_bars = []
    # Standard evaluation window: 2026 YTD
    eval_start = "2026-06-01"

    for symbol, local_sym, ct_val, prec, tag, score in portfolio_matrix:
        coin = symbol.split("-")[0]
        iid = InstrumentId.from_str(f"{symbol}.OKX")
        inc_str = f"{10**(-prec):.{prec}f}"
        
        inst = CryptoPerpetual(
            instrument_id=iid,
            raw_symbol=Symbol(symbol),
            base_currency=Currency.from_str(local_sym[:3] if local_sym != "SOLUSDT" else "SOL"),
            quote_currency=Currency.from_str("USDT"),
            settlement_currency=Currency.from_str("USDT"),
            is_inverse=False,
            price_precision=prec,
            size_precision=0,
            price_increment=Price.from_str(inc_str),
            size_increment=Quantity.from_int(1),
            multiplier=Quantity.from_str(str(ct_val)),
            lot_size=Quantity.from_int(1),
            margin_init=Decimal("0.1"),
            margin_maint=Decimal("0.05"),
            ts_event=0,
            ts_init=0,
        )
        engine.add_instrument(inst)

        cfg = SMCLiveConfig(
            strategy_id=StrategyId.from_str(f"SMC-{coin}-{tag}"),
            order_id_tag=tag,
        )
        cfg.instrument_id = f"{symbol}.OKX"
        cfg.ct_val = ct_val
        cfg.price_precision = prec
        cfg.risk_pct = 0.001
        cfg.min_score = score
        cfg.u_max = 0.28
        cfg.c_max = 0.28
        cfg.tp1_r = 1.5
        cfg.tp2_r = 3.20
        cfg.max_loss_streak = 3
        cfg.cooldown_bars = 48
        cfg.max_pending_bars = 3
        cfg.use_market_order = False
        cfg.limit_offset_mult = 0.2884

        strat = SMCBenchmarkStrategy(cfg)
        engine.add_strategy(strat)

        p = f"/backENV/dataBaseLake/03_governed_lake/v2_parquet_lake/crypto/futures_um/{local_sym}/15m/{local_sym}_15m_governed.parquet"
        df = pd.read_parquet(p)
        df = df[df["datetime"] >= eval_start]

        bar_spec = BarSpecification(15, BarAggregation.MINUTE, PriceType.LAST)
        bar_type = BarType(iid, bar_spec, AggregationSource.EXTERNAL)

        for row in df.itertuples():
            ts_ns = int(row.timestamp * 1_000_000)
            all_bars.append(Bar(
                bar_type=bar_type,
                open=Price(row.open, prec),
                high=Price(row.high, prec),
                low=Price(row.low, prec),
                close=Price(row.close, prec),
                volume=Quantity.from_int(int(row.volume)),
                ts_event=ts_ns,
                ts_init=ts_ns,
            ))

    all_bars.sort(key=lambda b: b.ts_event)
    engine.add_data(all_bars)
    engine.run()

    account = engine.portfolio.account(venue=Venue("OKX"))
    ccy = Currency.from_str("USDT")
    init_cash = 100_000.0
    end_cash = float(account.balance_total(ccy).as_double())
    net_pnl = end_cash - init_cash
    total_return_pct = (net_pnl / init_cash) * 100.0

    positions_report = engine.generate_positions_report()
    trade_pnls = []
    if not positions_report.empty and "realized_pnl" in positions_report.columns:
        closed = positions_report[positions_report["ts_closed"].notna()]
        for pnl_val in closed["realized_pnl"]:
            m = re.search(r"[-+]?\d*\.?\d+", str(pnl_val))
            if m:
                trade_pnls.append(float(m.group(0)))

    winning = sum(1 for p in trade_pnls if p > 0)
    total_trades = len(trade_pnls)
    win_rate = (winning / total_trades * 100.0) if total_trades > 0 else 0.0
    gross_win = sum(p for p in trade_pnls if p > 0)
    gross_loss = abs(sum(p for p in trade_pnls if p < 0))
    profit_factor = (gross_win / (gross_loss + 1e-9)) if gross_loss > 0 else 1.0

    cum_pnls = np.cumsum(trade_pnls) if trade_pnls else np.array([0.0])
    equity = init_cash + cum_pnls
    peak = np.maximum.accumulate(equity)
    drawdowns = (peak - equity) / peak * 100.0
    max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

    returns = np.diff(equity) / equity[:-1] if len(equity) > 1 else np.array([0.0])
    sharpe = float((np.mean(returns) / (np.std(returns) + 1e-9)) * math.sqrt(252.0)) if len(returns) > 1 else 0.0

    print(f"METRIC sharpe_ratio={sharpe:.4f}")
    print(f"METRIC total_return={total_return_pct:.4f}")
    print(f"METRIC max_drawdown={max_dd:.4f}")
    print(f"METRIC profit_factor={profit_factor:.4f}")
    print(f"METRIC win_rate={win_rate:.4f}")

if __name__ == "__main__":
    run_benchmark()

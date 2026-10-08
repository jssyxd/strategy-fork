import sys, traceback
from decimal import Decimal

from nautilus_trader.model import (InstrumentId, Venue, Currency, Money, Price, Quantity,
    Bar, BarType, BarSpecification, BarAggregation, PriceType, AggregationSource,
    OmsType, AccountType, TraderId, CryptoPerpetual)
from nautilus_trader.backtest import BacktestEngine, BacktestEngineConfig
from nautilus_trader.trading import Strategy, StrategyConfig
from nautilus_trader.execution import MakerTakerFeeModel

USDT = Currency.from_str("USDT")
BTC = Currency.from_str("BTC")
IID = InstrumentId.from_str("BTC-USDT-SWAP.OKX")
VENUE = Venue("OKX")

def section(t):
    print("")
    print("=== " + t + " ===")

def make_instrument():
    return CryptoPerpetual(
        instrument_id=IID, raw_symbol="BTC-USDT-SWAP", base_currency=BTC, quote_currency=USDT,
        settlement_currency=USDT, is_inverse=False,
        price_precision=1, size_precision=2,
        price_increment=Price.from_str("0.1"), size_increment=Quantity.from_str("0.01"),
        multiplier=Quantity.from_str("0.01"),
        margin_init=Decimal("0.05"), margin_maint=Decimal("0.005"),
        maker_fee=Decimal("0.0002"), taker_fee=Decimal("0.0005"),
        ts_event=0, ts_init=0)

def make_bars(n, bar_type, start_ns, step_ns, base=100.0):
    bars = []
    for i in range(n):
        o = base + i
        h = o + 1.5
        l = o - 1.5
        c = o + 0.5
        ts = start_ns + i * step_ns
        bars.append(Bar(bar_type, Price.from_str("%.1f" % o), Price.from_str("%.1f" % h),
                        Price.from_str("%.1f" % l), Price.from_str("%.1f" % c),
                        Quantity.from_str("10"), ts, ts))
    return bars

class Probe(Strategy):
    def __init__(self, config):
        super().__init__(config)
        self.seen = []
        self.fills = []
    def on_start(self):
        instr = self.cache.instrument(IID)
        self.bar_type = BarType(IID, BarSpecification(15, BarAggregation.MINUTE, PriceType.LAST), AggregationSource.EXTERNAL)
        self.subscribe_bars(self.bar_type)
    def on_bar(self, bar):
        self.seen.append((bar.ts_event, str(bar.open), str(bar.high), str(bar.low), str(bar.close)))
        if len(self.seen) == 3:
            order = self.order_factory.market(
                instrument_id=IID, order_side=__import__("nautilus_trader.model", fromlist=["OrderSide"]).OrderSide.BUY,
                quantity=Quantity.from_str("1"))
            self.submit_order(order)
    def on_order_filled(self, event):
        self.fills.append((event.ts_event, str(event.last_px), str(event.last_qty)))

MIN = 60 * 1_000_000_000
section("BarType 展开")
for label, spec in [("15m", BarSpecification(15, BarAggregation.MINUTE, PriceType.LAST)),
                    ("1h", BarSpecification(1, BarAggregation.HOUR, PriceType.LAST)),
                    ("4h", BarSpecification(4, BarAggregation.HOUR, PriceType.LAST)),
                    ("1d", BarSpecification(1, BarAggregation.DAY, PriceType.LAST))]:
    print(label, "->", BarType(IID, spec, AggregationSource.EXTERNAL))

section("回测骨架 + 成交时点")
try:
    engine = BacktestEngine(config=BacktestEngineConfig(trader_id=TraderId("BT-013"), logging=None))
    engine.add_venue(
        venue=VENUE, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN,
        starting_balances=[Money(10000, USDT)], base_currency=USDT,
        default_leverage=Decimal(20),
        fee_model=MakerTakerFeeModel(maker_fee=Decimal("0.0002"), taker_fee=Decimal("0.0005")),
        bar_execution=True, trade_execution=True, bar_adaptive_high_low_ordering=False)
    instr = make_instrument()
    engine.add_instrument(instr)
    bt = BarType(IID, BarSpecification(15, BarAggregation.MINUTE, PriceType.LAST), AggregationSource.EXTERNAL)
    start = 1_700_000_000 * 1_000_000_000
    bars = make_bars(6, bt, start, 15 * MIN)
    engine.add_data(bars)
    strat = Probe(StrategyConfig(strategy_id="P-001", order_id_tag="001"))
    engine.add_strategy(strat)
    engine.run()
    print("bars seen:", len(strat.seen))
    for i, s in enumerate(strat.seen):
        print("  bar", i, s)
    print("fills:", strat.fills)
    res = engine.get_result()
    print("total_orders:", res.total_orders, "positions:", res.total_positions)
except Exception as e:
    traceback.print_exc()
section("SimulationModule 结构")
try:
    from nautilus_trader.backtest import SimulationModule
    import inspect
    for m in ["pre_process", "process", "acknowledge", "reset", "log_diagnostics"]:
        f = getattr(SimulationModule, m, None)
        print(m, "->", (getattr(f, "__doc__", None) or "no doc")[:160].replace(chr(10), " "))
except Exception as e:
    traceback.print_exc()

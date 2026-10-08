import traceback
from decimal import Decimal

from nautilus_trader.model import (InstrumentId, Venue, Currency, Money, Price, Quantity,
    Bar, BarType, BarSpecification, BarAggregation, PriceType, AggregationSource,
    OmsType, AccountType, TraderId, CryptoPerpetual, OrderSide, TimeInForce, TriggerType, Symbol, StrategyId)
from nautilus_trader.backtest import BacktestEngine, BacktestEngineConfig, SimulationModule
from nautilus_trader.trading import Strategy, StrategyConfig
from nautilus_trader.execution import MakerTakerFeeModel

USDT = Currency.from_str("USDT")
BTC = Currency.from_str("BTC")
IID = InstrumentId.from_str("BTC-USDT-SWAP.OKX")
VENUE = Venue("OKX")
MIN = 60 * 1_000_000_000
BT15 = BarType(IID, BarSpecification(15, BarAggregation.MINUTE, PriceType.LAST), AggregationSource.EXTERNAL)
START = 1_700_000_000 * 1_000_000_000

def log(*a):
    print("PROBE|", *a, flush=True)

class SpyModule(SimulationModule):
    def __init__(self):
        try:
            super().__init__()
        except Exception as ex:
            log("SpyModule super init err:", str(ex)[:80])
        self.calls = []
    def pre_process(self, *a, **kw):
        self.calls.append(("pre_process", len(a), list(kw)))
    def process(self, *a, **kw):
        self.calls.append(("process", len(a), list(kw)))
    def acknowledge(self, *a, **kw):
        self.calls.append(("acknowledge", len(a), list(kw)))
    def reset(self, *a, **kw):
        self.calls.append(("reset", len(a), list(kw)))

def make_instrument():
    return CryptoPerpetual(
        instrument_id=IID, raw_symbol=Symbol.from_str("BTC-USDT-SWAP"), base_currency=BTC, quote_currency=USDT,
        settlement_currency=USDT, is_inverse=False,
        price_precision=1, size_precision=2,
        price_increment=Price.from_str("0.1"), size_increment=Quantity.from_str("0.01"),
        ts_event=0, ts_init=0, multiplier=Quantity.from_str("0.01"),
        margin_init=Decimal("0.05"), margin_maint=Decimal("0.005"))

def bar(i, o, h, l, c):
    ts = START + i * 15 * MIN
    return Bar(BT15, Price.from_str("%.1f" % o), Price.from_str("%.1f" % h),
               Price.from_str("%.1f" % l), Price.from_str("%.1f" % c),
               Quantity.from_str("10"), ts, ts)

class ProbeConfig(StrategyConfig):
    adaptive: bool = False

class Probe2(Strategy):
    def __init__(self, config: ProbeConfig):
        super().__init__(config)
        self.adaptive = config.adaptive
        self.bars = []
        self.fills = []
        self.orders = []
    def on_start(self):
        self.subscribe_bars(BT15)
    def on_bar(self, b):
        self.bars.append((b.ts_event, float(b.open), float(b.high), float(b.low), float(b.close)))
        n = len(self.bars)
        if n == 3:
            o = self.order_factory.market(instrument_id=IID, order_side=OrderSide.BUY, quantity=Quantity.from_str("1"))
            log("submit MARKET buy on bar#2 (close=%.1f)" % float(b.close))
            self.submit_order(o)
        if n == 4 and self.fills:
            q = self.fills[-1][2]
            log("after first fill qty=%s -> rest SL(95.0) / TP(110.0)" % q)
            sl = self.order_factory.stop_market(instrument_id=IID, order_side=OrderSide.SELL,
                    quantity=Quantity.from_str(q), trigger_price=Price.from_str("95.0"))
            tp = self.order_factory.limit(instrument_id=IID, order_side=OrderSide.SELL,
                    quantity=Quantity.from_str(q), price=Price.from_str("110.0"), time_in_force=TimeInForce.GTC)
            self.submit_order(sl)
            self.submit_order(tp)
    def on_order_filled(self, e):
        self.fills.append((e.ts_event, float(e.last_px), str(e.last_qty)))
        log("FILL px=%.1f qty=%s ts=%d" % (float(e.last_px), e.last_qty, e.ts_event))
    def on_order_submitted(self, e):
        log("ORDER SUBMITTED", str(e))

def run_once(adaptive, bars):
    log("---- run with bar_adaptive_high_low_ordering=%s ----" % adaptive)
    engine = BacktestEngine(config=BacktestEngineConfig(trader_id=TraderId("BT-013"), logging=None))
    spy = SpyModule()
    engine.add_venue(venue=VENUE, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN,
        starting_balances=[Money(10000, USDT)], base_currency=USDT, default_leverage=Decimal(20),
        fee_model=MakerTakerFeeModel(Decimal("0.0002"), Decimal("0.0005")),
        modules=[spy], bar_execution=True, trade_execution=True, bar_adaptive_high_low_ordering=adaptive)
    engine.add_instrument(make_instrument())
    engine.add_data(bars)
    s = Probe2(ProbeConfig(strategy_id=StrategyId.from_str("P2-001"), order_id_tag="001", adaptive=adaptive))
    engine.add_strategy(s)
    engine.run()
    for i, b in enumerate(s.bars):
        log("  bar#%d open=%.1f high=%.1f low=%.1f close=%.1f ts=%d" % (i, b[1], b[2], b[3], b[4], b[0]))
    log("  fills:", [(f[0], round(f[1], 1), f[2]) for f in s.fills])
    log("  module calls:", spy.calls[:4], "total", len(spy.calls))
    try:
        res = engine.get_result()
        log("  result: orders=%s positions=%s" % (res.total_orders, res.total_positions))
    except Exception as ex:
        log("  get_result err:", str(ex)[:100])
    engine.dispose()

try:
    t1 = [bar(i, o, h, l, c) for i, (o, h, l, c) in enumerate([
        (100.0, 101.0, 99.5, 100.5), (100.5, 101.5, 100.0, 101.0), (101.0, 102.0, 100.5, 101.5),
        (101.5, 102.5, 101.0, 102.0), (102.0, 103.0, 101.5, 102.5), (102.5, 103.5, 102.0, 103.0)])]
    run_once(False, t1)
except Exception:
    traceback.print_exc()

try:
    t2 = [bar(i, o, h, l, c) for i, (o, h, l, c) in enumerate([
        (100.0, 101.0, 99.5, 100.5), (100.5, 101.5, 100.0, 101.0), (101.0, 102.0, 100.5, 101.5),
        (101.5, 102.5, 101.0, 102.0), (102.0, 112.0, 94.0, 105.0), (105.0, 106.0, 104.0, 105.5)])]
    run_once(False, t2)
    run_once(True, t2)
except Exception:
    traceback.print_exc()
log("DONE")

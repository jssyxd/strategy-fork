import traceback, datetime
from decimal import Decimal
from nautilus_trader.model import (InstrumentId, Venue, Currency, Money, Price, Quantity, Bar, BarType,
    BarSpecification, BarAggregation, PriceType, AggregationSource, OmsType, AccountType, TraderId,
    CryptoPerpetual, Symbol, StrategyId, OrderSide, TimeInForce)
from nautilus_trader.backtest import BacktestEngine, BacktestEngineConfig
from nautilus_trader.trading import Strategy, StrategyConfig
from nautilus_trader.execution import MakerTakerFeeModel

USDT = Currency.from_str("USDT"); BTC = Currency.from_str("BTC")
IID = InstrumentId.from_str("BTC-USDT-SWAP.OKX"); VENUE = Venue("OKX")
MIN = 60 * 1_000_000_000
START = 1_700_000_000 * 1_000_000_000
BT = BarType(IID, BarSpecification(15, BarAggregation.MINUTE, PriceType.LAST), AggregationSource.EXTERNAL)

def log(*a): print("SB|", *a, flush=True)

# bar#4 spans BOTH the stop (98) and the target (105): low=96.0, high=106.0
OHLC = [(100.0, 101.0, 99.5, 100.5), (100.5, 101.5, 100.0, 101.0), (101.0, 102.0, 100.5, 101.5),
        (101.5, 102.5, 101.0, 102.0), (102.0, 106.0, 96.0, 103.0), (103.0, 104.0, 102.5, 103.5)]

def mk_bars():
    out = []
    for i, (o, h, l, c) in enumerate(OHLC):
        ts = START + i * 15 * MIN
        out.append(Bar(BT, Price.from_str("%.1f" % o), Price.from_str("%.1f" % h),
                       Price.from_str("%.1f" % l), Price.from_str("%.1f" % c),
                       Quantity.from_str("10.00"), ts, ts))
    return out

def perp():
    return CryptoPerpetual(instrument_id=IID, raw_symbol=Symbol.from_str("BTC-USDT-SWAP"),
        base_currency=BTC, quote_currency=USDT, settlement_currency=USDT, is_inverse=False,
        price_precision=1, size_precision=2, price_increment=Price.from_str("0.1"),
        size_increment=Quantity.from_str("0.01"), ts_event=0, ts_init=0,
        min_quantity=Quantity.from_str("0.01"), margin_init=Decimal("0.05"), margin_maint=Decimal("0.005"))

class C(StrategyConfig):
    adaptive: bool = False

class S(Strategy):
    def __init__(self, config: C):
        super().__init__(config)
        self.n = 0
        self.entry = None
        self.orders_placed = False
    def on_start(self):
        self.subscribe_bars(BT)
    def on_bar(self, b):
        self.n += 1
        if self.n == 3:
            o = self.order_factory.market(instrument_id=IID, order_side=OrderSide.BUY, quantity=Quantity.from_str("1"))
            self.submit_order(o)
        if self.n == 4 and self.entry is not None and not self.orders_placed:
            self.orders_placed = True
            sl = self.order_factory.stop_market(instrument_id=IID, order_side=OrderSide.SELL,
                quantity=Quantity.from_str("1"), trigger_price=Price.from_str("98.0"))
            tp = self.order_factory.limit(instrument_id=IID, order_side=OrderSide.SELL,
                quantity=Quantity.from_str("1"), price=Price.from_str("105.0"), time_in_force=TimeInForce.GTC)
            log("bar#4 rests SL=98.0 and TP=105.0")
            self.submit_order(sl)
            self.submit_order(tp)
    def on_bar_after(self, b):
        pass
    def on_order_filled(self, e):
        log("  FILL type=%s px=%.1f ts=%s" % (e.order_type, float(e.last_px),
            datetime.datetime.utcfromtimestamp(e.ts_event / 1e9).strftime("%H:%M")))
        if self.entry is None:
            self.entry = float(e.last_px)
    def on_order_rejected(self, e):
        log("  REJECTED:", e.reason)

def run(adaptive):
    log("==== adaptive=%s ====" % adaptive)
    try:
        eng = BacktestEngine(config=BacktestEngineConfig(trader_id=TraderId("BT-013"), logging=None))
        eng.add_venue(venue=VENUE, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN,
            starting_balances=[Money(10000, USDT)], base_currency=USDT, default_leverage=Decimal(20),
            fee_model=MakerTakerFeeModel(Decimal("0.0002"), Decimal("0.0005")),
            bar_execution=True, trade_execution=True, bar_adaptive_high_low_ordering=adaptive)
        eng.add_instrument(perp())
        eng.add_data(mk_bars())
        cfg = C(strategy_id=StrategyId.from_str("SB-001"), order_id_tag="001")
        cfg.adaptive = adaptive
        eng.add_strategy(S(cfg))
        eng.run()
        log("  total_orders=%s" % eng.get_result().total_orders)
        eng.dispose()
    except Exception:
        traceback.print_exc()

try:
    run(False)
    run(True)
except Exception:
    traceback.print_exc()

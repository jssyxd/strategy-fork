import traceback
from decimal import Decimal
from nautilus_trader.model import (InstrumentId, Venue, Currency, Money, Price, Quantity, Bar, BarType,
    BarSpecification, BarAggregation, PriceType, AggregationSource, OmsType, AccountType, TraderId,
    CryptoPerpetual, Symbol, StrategyId, OrderSide, QuoteTick)
from nautilus_trader.backtest import BacktestEngine, BacktestEngineConfig
from nautilus_trader.trading import Strategy, StrategyConfig
from nautilus_trader.execution import MakerTakerFeeModel
from nautilus_trader.testkit.providers import TestInstrumentProvider

USDT = Currency.from_str("USDT"); BTC = Currency.from_str("BTC")
MIN = 60 * 1_000_000_000
START = 1_700_000_000 * 1_000_000_000

def log(*a): print("M2|", *a, flush=True)

def my_perp():
    return CryptoPerpetual(instrument_id=InstrumentId.from_str("BTC-USDT-SWAP.OKX"),
        raw_symbol=Symbol.from_str("BTC-USDT-SWAP"), base_currency=BTC, quote_currency=USDT,
        settlement_currency=USDT, is_inverse=False, price_precision=1, size_precision=2,
        price_increment=Price.from_str("0.1"), size_increment=Quantity.from_str("0.01"),
        ts_event=0, ts_init=0, multiplier=Quantity.from_str("0.01"),
        margin_init=Decimal("0.05"), margin_maint=Decimal("0.005"))

class C(StrategyConfig):
    use_bars: bool = False

class S(Strategy):
    def __init__(self, config: C):
        super().__init__(config)
        self.iid = None
        self.done = False
        self.use_bars = config.use_bars
    def on_start(self):
        instr = list(self.cache.instruments())[0]
        self.iid = instr.id
        if self.use_bars:
            self.subscribe_bars(BarType(self.iid, BarSpecification(15, BarAggregation.MINUTE, PriceType.LAST), AggregationSource.EXTERNAL))
        else:
            self.subscribe_quotes(self.iid)
    def _go(self):
        if not self.done:
            self.done = True
            o = self.order_factory.market(instrument_id=self.iid, order_side=OrderSide.BUY, quantity=Quantity.from_str("1"))
            self.submit_order(o)
    def on_quote(self, q):
        self._go()
    def on_bar(self, b):
        self._go()
    def on_order_filled(self, e):
        log("  FILL px=%.2f" % float(e.last_px))
    def on_order_rejected(self, e):
        log("  REJECTED:", e.reason)

def mk_bars(iid):
    bt = BarType(iid, BarSpecification(15, BarAggregation.MINUTE, PriceType.LAST), AggregationSource.EXTERNAL)
    out = []
    for i in range(6):
        o = 100.0 + i; ts = START + i * 15 * MIN
        out.append(Bar(bt, Price.from_str("%.1f" % o), Price.from_str("%.1f" % (o + 1.5)),
                       Price.from_str("%.1f" % (o - 1.5)), Price.from_str("%.1f" % (o + 0.5)),
                       Quantity.from_str("10.0000"), ts, ts))
    return out

def mk_quotes(iid):
    out = []
    for i in range(6):
        ts = START + i * 15 * MIN
        out.append(QuoteTick(iid, Price.from_str("100.0"), Price.from_str("100.2"),
                             Quantity.from_str("1.000"), Quantity.from_str("1.000"), ts, ts))
    return out

def run(name, instr, use_bars):
    log("---- %s (data=%s) ----" % (name, "bars" if use_bars else "quotes"))
    try:
        iid = instr.id
        eng = BacktestEngine(config=BacktestEngineConfig(trader_id=TraderId("BT-013"), logging=None))
        eng.add_venue(venue=iid.venue, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN,
            starting_balances=[Money(10000, USDT)], base_currency=USDT, default_leverage=Decimal(20),
            fee_model=MakerTakerFeeModel(Decimal("0.0002"), Decimal("0.0005")),
            bar_execution=True, trade_execution=True)
        eng.add_instrument(instr)
        eng.add_data(mk_bars(iid) if use_bars else mk_quotes(iid))
        eng.add_strategy(S(C(strategy_id=StrategyId.from_str("M2-001"), order_id_tag="001", use_bars=use_bars)))
        eng.run()
        log("  orders=%s" % eng.get_result().total_orders)
        eng.dispose()
    except Exception as e:
        log("  EXC", type(e).__name__, str(e)[:100])

try:
    run("A my OKX perp", my_perp(), False)
    run("B my OKX perp", my_perp(), True)
    run("C testkit BINANCE perp", TestInstrumentProvider.btcusdt_perp_binance(), True)
except Exception:
    traceback.print_exc()

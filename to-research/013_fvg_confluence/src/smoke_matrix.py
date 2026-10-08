import traceback
from decimal import Decimal
from nautilus_trader.model import (InstrumentId, Venue, Currency, Money, Price, Quantity, Bar, BarType,
    BarSpecification, BarAggregation, PriceType, AggregationSource, OmsType, AccountType, TraderId,
    CryptoPerpetual, Symbol, StrategyId, OrderSide, CurrencyPair)
from nautilus_trader.backtest import BacktestEngine, BacktestEngineConfig
from nautilus_trader.trading import Strategy, StrategyConfig
from nautilus_trader.execution import MakerTakerFeeModel

USDT = Currency.from_str("USDT"); BTC = Currency.from_str("BTC")
MIN = 60 * 1_000_000_000
START = 1_700_000_000 * 1_000_000_000

def log(*a): print("MX|", *a, flush=True)

def bars_for(iid, venue_str):
    bt = BarType(iid, BarSpecification(15, BarAggregation.MINUTE, PriceType.LAST), AggregationSource.EXTERNAL)
    out = []
    for i in range(6):
        o = 100.0 + i; ts = START + i * 15 * MIN
        out.append(Bar(bt, Price.from_str("%.1f" % o), Price.from_str("%.1f" % (o + 1.5)),
                       Price.from_str("%.1f" % (o - 1.5)), Price.from_str("%.1f" % (o + 0.5)),
                       Quantity.from_str("10.0000"), ts, ts))
    return bt, out

class C(StrategyConfig):
    iid: str = ""

class S(Strategy):
    def __init__(self, config: C):
        super().__init__(config)
        self.iid = InstrumentId.from_str(config.iid)
    def on_start(self):
        self.subscribe_bars(BarType(self.iid, BarSpecification(15, BarAggregation.MINUTE, PriceType.LAST), AggregationSource.EXTERNAL))
    def on_bar(self, b):
        if not hasattr(self, "done"):
            self.done = True
            o = self.order_factory.market(instrument_id=self.iid, order_side=OrderSide.BUY, quantity=Quantity.from_str("1"))
            self.submit_order(o)
    def on_order_filled(self, e):
        log("  FILL", float(e.last_px), e.ts_event)
    def on_order_rejected(self, e):
        log("  REJECTED:", e.reason)

def case(name, venue_str, iid_str, make_instr):
    log("---- " + name + " ----")
    try:
        iid = InstrumentId.from_str(iid_str)
        venue = Venue(venue_str)
        eng = BacktestEngine(config=BacktestEngineConfig(trader_id=TraderId("BT-013"), logging=None))
        eng.add_venue(venue=venue, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN,
            starting_balances=[Money(10000, USDT)], base_currency=USDT, default_leverage=Decimal(20),
            fee_model=MakerTakerFeeModel(Decimal("0.0002"), Decimal("0.0005")))
        eng.add_instrument(make_instr(iid))
        bt, bars = bars_for(iid, venue_str)
        eng.add_data(bars)
        cfg = C(strategy_id=StrategyId.from_str("S-001"), order_id_tag="001")
        cfg.iid = iid_str
        eng.add_strategy(S(cfg))
        eng.run()
        log("  orders=%s" % eng.get_result().total_orders)
        eng.dispose()
    except Exception as e:
        log("  EXC", type(e).__name__, str(e)[:120])

def perp(iid):
    return CryptoPerpetual(instrument_id=iid, raw_symbol=Symbol.from_str("BTC-USDT-SWAP"),
        base_currency=BTC, quote_currency=USDT, settlement_currency=USDT, is_inverse=False,
        price_precision=1, size_precision=2, price_increment=Price.from_str("0.1"),
        size_increment=Quantity.from_str("0.01"), ts_event=0, ts_init=0,
        multiplier=Quantity.from_str("0.01"), margin_init=Decimal("0.05"), margin_maint=Decimal("0.005"))

try:
    case("A: OKX venue + perp", "OKX", "BTC-USDT-SWAP.OKX", perp)
    case("B: SIM venue + perp", "SIM", "BTC-USDT-SWAP.SIM", perp)
    case("C: OKX venue + perp, CASH account", "OKX", "BTC-USDT-SWAP.OKX", perp)
except Exception:
    traceback.print_exc()

import traceback
from decimal import Decimal
from nautilus_trader.model import (InstrumentId, Venue, Currency, Money, Price, Quantity, Bar, BarType,
    BarSpecification, BarAggregation, PriceType, AggregationSource, OmsType, AccountType, TraderId,
    CryptoPerpetual, CurrencyPair, OrderSide, Symbol, StrategyId)
from nautilus_trader.backtest import BacktestEngine, BacktestEngineConfig
from nautilus_trader.trading import Strategy, StrategyConfig
from nautilus_trader.execution import MakerTakerFeeModel

USDT = Currency.from_str("USDT"); BTC = Currency.from_str("BTC")
IID = InstrumentId.from_str("BTC-USDT-SWAP.OKX"); VENUE = Venue("OKX")
MIN = 60 * 1_000_000_000
BT15 = BarType(IID, BarSpecification(15, BarAggregation.MINUTE, PriceType.LAST), AggregationSource.EXTERNAL)
START = 1_700_000_000 * 1_000_000_000

def log(*a): print("P3|", *a, flush=True)

def perp():
    return CryptoPerpetual(instrument_id=IID, raw_symbol=Symbol.from_str("BTC-USDT-SWAP"),
        base_currency=BTC, quote_currency=USDT, settlement_currency=USDT, is_inverse=False,
        price_precision=1, size_precision=2, price_increment=Price.from_str("0.1"),
        size_increment=Quantity.from_str("0.01"), ts_event=0, ts_init=0,
        multiplier=Quantity.from_str("0.01"), margin_init=Decimal("0.05"), margin_maint=Decimal("0.005"))

def bars(n=6):
    out = []
    for i in range(n):
        o = 100.0 + i; ts = START + i * 15 * MIN
        out.append(Bar(BT15, Price.from_str("%.1f" % o), Price.from_str("%.1f" % (o+1.5)),
                       Price.from_str("%.1f" % (o-1.5)), Price.from_str("%.1f" % (o+0.5)),
                       Quantity.from_str("10"), ts, ts))
    return out

class Cfg(StrategyConfig):
    pass

class S(Strategy):
    def on_start(self):
        instr = self.cache.instrument(IID)
        log("cache instrument:", instr)
        self.subscribe_bars(BT15)
    def on_bar(self, b):
        if not hasattr(self, "sent"):
            self.sent = True
            o = self.order_factory.market(instrument_id=IID, order_side=OrderSide.BUY, quantity=Quantity.from_str("1"))
            self.submit_order(o)
    def on_order_filled(self, e):
        log("FILL", float(e.last_px), e.last_qty, e.ts_event)
    def on_order_rejected(self, e):
        log("REJECTED", e.reason)

def variant(name, add_instrument_first, make_instr):
    log("==== " + name + " ====")
    try:
        eng = BacktestEngine(config=BacktestEngineConfig(trader_id=TraderId("BT-013"), logging=None))
        if add_instrument_first:
            eng.add_instrument(make_instr())
        eng.add_venue(venue=VENUE, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN,
            starting_balances=[Money(10000, USDT)], base_currency=USDT, default_leverage=Decimal(20),
            fee_model=MakerTakerFeeModel(Decimal("0.0002"), Decimal("0.0005")))
        if not add_instrument_first:
            eng.add_instrument(make_instr())
        eng.add_data(bars())
        eng.add_strategy(S(Cfg(strategy_id=StrategyId.from_str("P3-001"), order_id_tag="001")))
        eng.run()
        log("total_orders:", eng.get_result().total_orders)
        eng.dispose()
    except Exception:
        traceback.print_exc()

variant("A: venue then instrument (perp)", False, perp)
variant("B: instrument then venue (perp)", True, perp)

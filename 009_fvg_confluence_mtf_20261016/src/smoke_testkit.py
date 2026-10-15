import traceback
from decimal import Decimal
from nautilus_trader.model import (Venue, Currency, Money, Price, Quantity, OmsType, AccountType, TraderId, StrategyId, OrderSide, QuoteTick)
from nautilus_trader.backtest import BacktestEngine, BacktestEngineConfig
from nautilus_trader.trading import Strategy, StrategyConfig
from nautilus_trader.execution import MakerTakerFeeModel
from nautilus_trader.testkit.providers import TestInstrumentProvider, TestDataProvider

def log(*a): print("TP|", *a, flush=True)
log("providers:", [m for m in dir(TestInstrumentProvider) if not m.startswith("_")][:25])
log("data providers:", [m for m in dir(TestDataProvider) if not m.startswith("_")][:25])

class C(StrategyConfig):
    pass

class S(Strategy):
    def __init__(self, config: C):
        super().__init__(config)
        self.done = False
    def on_start(self):
        self.subscribe_quotes(self.iid)
    def on_quote(self, q):
        if not self.done:
            self.done = True
            o = self.order_factory.market(instrument_id=self.iid, order_side=OrderSide.BUY, quantity=Quantity.from_str("1"))
            self.submit_order(o)
    def on_order_filled(self, e):
        log("FILL", float(e.last_px), e.last_qty)
    def on_order_rejected(self, e):
        log("REJECTED:", e.reason)

try:
    instr = None
    for name in ("btcusdt_perp_binance", "btcusdt_perp", "crypto_perpetual_btcusdt"):
        fn = getattr(TestInstrumentProvider, name, None)
        if fn:
            instr = fn()
            log("using TestInstrumentProvider.%s -> %s" % (name, instr.id))
            break
    if instr is None:
        log("no crypto perp provider; listing first few:")
    if instr is not None:
        SIM = Venue("BINANCE")
        eng = BacktestEngine(config=BacktestEngineConfig(trader_id=TraderId("BT-013"), logging=None))
        eng.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN,
            starting_balances=[Money(10000, Currency.from_str("USDT"))], base_currency=Currency.from_str("USDT"),
            default_leverage=Decimal(20), fee_model=MakerTakerFeeModel(Decimal("0.0002"), Decimal("0.0005")))
        eng.add_instrument(instr)
        log("instrument added, price_prec=%s size_prec=%s" % (instr.price_precision, instr.size_precision))
        eng.run()
        log("run ok, orders=%s" % eng.get_result().total_orders)
        eng.dispose()
except Exception:
    traceback.print_exc()

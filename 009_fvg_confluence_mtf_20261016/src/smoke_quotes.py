import traceback
from decimal import Decimal
from nautilus_trader.model import (Venue, Currency, Money, Price, Quantity, OmsType, AccountType, TraderId, StrategyId, OrderSide, QuoteTick)
from nautilus_trader.backtest import BacktestEngine, BacktestEngineConfig
from nautilus_trader.trading import Strategy, StrategyConfig
from nautilus_trader.execution import MakerTakerFeeModel
from nautilus_trader.testkit.providers import TestInstrumentProvider

def log(*a): print("TQ|", *a, flush=True)

class C(StrategyConfig):
    pass

class S(Strategy):
    def __init__(self, config: C):
        super().__init__(config)
        self.done = False
        self.iid = None
    def on_start(self):
        self.iid = list(self.cache.instruments())[0].id
        log("strategy sees instruments:", [str(i) for i in self.cache.instruments()])
        self.subscribe_quotes(self.iid)
    def on_quote(self, q):
        if not self.done:
            self.done = True
            o = self.order_factory.market(instrument_id=self.iid, order_side=OrderSide.BUY, quantity=Quantity.from_str("1"))
            log(">>> submit MARKET BUY on first quote")
            self.submit_order(o)
    def on_order_filled(self, e):
        log("FILL", float(e.last_px), e.last_qty)
    def on_order_rejected(self, e):
        log("REJECTED:", e.reason)

try:
    instr = TestInstrumentProvider.btcusdt_perp_binance()
    iid = instr.id
    log("instrument:", iid, "venue:", iid.venue)
    eng = BacktestEngine(config=BacktestEngineConfig(trader_id=TraderId("BT-013"), logging=None))
    eng.add_venue(venue=iid.venue, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN,
        starting_balances=[Money(10000, Currency.from_str("USDT"))], base_currency=Currency.from_str("USDT"),
        default_leverage=Decimal(20), fee_model=MakerTakerFeeModel(Decimal("0.0002"), Decimal("0.0005")),
        bar_execution=True, trade_execution=True)
    eng.add_instrument(instr)
    base = 1_700_000_000 * 1_000_000_000
    quotes = []
    for i in range(5):
        ts = base + i * 60 * 1_000_000_000
        quotes.append(QuoteTick(iid, Price.from_str("100.0"), Price.from_str("100.2"),
                                Quantity.from_str("1.000"), Quantity.from_str("1.000"), ts, ts))
    eng.add_data(quotes)
    eng.add_strategy(S(C(strategy_id=StrategyId.from_str("Q-001"), order_id_tag="001")))
    eng.run()
    log("orders:", eng.get_result().total_orders)
    eng.dispose()
except Exception:
    traceback.print_exc()

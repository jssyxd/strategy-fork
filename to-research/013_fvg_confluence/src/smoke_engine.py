import traceback, datetime
from decimal import Decimal
from nautilus_trader.model import (InstrumentId, BarType, BarSpecification, BarAggregation, PriceType,
    AggregationSource, OrderSide, Quantity, Price, StrategyId, TraderId, NautilusDataType, TimeInForce, Currency)
from nautilus_trader.config import BacktestEngineConfig, BacktestVenueConfig, BacktestDataConfig, BacktestRunConfig
from nautilus_trader.backtest import BacktestNode
from nautilus_trader.trading import Strategy, StrategyConfig
from nautilus_trader.execution import MakerTakerFeeModel

CAT = "/root/bt013/catalog"
IID = InstrumentId.from_str("BTC-USDT-SWAP.OKX")
BT15 = BarType(IID, BarSpecification(15, BarAggregation.MINUTE, PriceType.LAST), AggregationSource.EXTERNAL)

def log(*a):
    print("ENG|", *a, flush=True)

def ns(y, m, d, hh=0):
    return int(datetime.datetime(y, m, d, hh, tzinfo=datetime.timezone.utc).timestamp() * 1e9)

class Cfg(StrategyConfig):
    mode: str = "timing"

class S(Strategy):
    def __init__(self, config: Cfg):
        super().__init__(config)
        self.mode = config.mode
        self.n = 0
        self.sent_fill = None
        self.entry_px = None
        self.stops_done = False
    def on_start(self):
        self.subscribe_bars(BT15)
    def on_bar(self, b):
        self.n += 1
        if self.n <= 4 or self.n % 20 == 0:
            log("bar#%d ts=%s O=%.1f H=%.1f L=%.1f C=%.1f" % (
                self.n, datetime.datetime.utcfromtimestamp(b.ts_event / 1e9).strftime("%m-%d %H:%M"),
                float(b.open), float(b.high), float(b.low), float(b.close)))
        if self.mode == "timing" and self.n == 3:
            o = self.order_factory.market(instrument_id=IID, order_side=OrderSide.BUY, quantity=Quantity.from_str("1"))
            log(">>> submit MARKET BUY at bar#3 close=%.1f" % float(b.close))
            self.submit_order(o)
        if self.mode == "sltp" and self.entry_px is not None and not self.stops_done and self.n == 5:
            self.stops_done = True
            entry = self.entry_px
            sl = self.order_factory.stop_market(instrument_id=IID, order_side=OrderSide.SELL,
                quantity=Quantity.from_str("1"), trigger_price=Price.from_str("%.1f" % (entry - 100)))
            tp = self.order_factory.limit(instrument_id=IID, order_side=OrderSide.SELL,
                quantity=Quantity.from_str("1"), price=Price.from_str("%.1f" % (entry + 100)),
                time_in_force=TimeInForce.GTC)
            log(">>> resting SL=%.1f TP=%.1f (entry=%.1f)" % (entry - 100, entry + 100, entry))
            self.submit_order(sl)
            self.submit_order(tp)
    def on_order_filled(self, e):
        log("FILL side=%s px=%.1f qty=%s ts=%s" % (e.order_side, float(e.last_px), e.last_qty,
            datetime.datetime.utcfromtimestamp(e.ts_event / 1e9).strftime("%m-%d %H:%M")))
        if self.entry_px is None:
            self.entry_px = float(e.last_px)
    def on_order_rejected(self, e):
        log("REJECTED:", e.reason)

def run(mode, adaptive):
    log("==== mode=%s adaptive=%s ====" % (mode, adaptive))
    start, end = ns(2026, 10, 5), ns(2026, 10, 8)
    venue = BacktestVenueConfig(name="OKX", oms_type="NETTING", account_type="MARGIN",
        starting_balances=["10000 USDT"], base_currency=Currency.from_str("USDT"), default_leverage=Decimal(20),
        fee_model=MakerTakerFeeModel(Decimal("0.0002"), Decimal("0.0005")),
        bar_execution=True, trade_execution=True, bar_adaptive_high_low_ordering=adaptive)
    data = BacktestDataConfig(data_type=NautilusDataType.Bar, catalog_path=CAT,
        instrument_id=IID, bar_spec=BarSpecification(15, BarAggregation.MINUTE, PriceType.LAST),
        start_time=start, end_time=end)
    cfg = BacktestRunConfig(venues=[venue], data=[data],
        engine=BacktestEngineConfig(trader_id=TraderId("BT-013"), logging=None), start=start, end=end)
    node = BacktestNode(configs=[cfg])
    node.build()
    node.add_strategy(cfg.id, S(Cfg(strategy_id=StrategyId.from_str("S-001"), order_id_tag="001", mode=mode)))
    node.run()
    try:
        rep = node.generate_order_fills_report(cfg.id)
        log("fills report rows=%d" % len(rep))
        log(rep.to_string()[:900])
    except Exception as ex:
        log("fills report err:", str(ex)[:150])
    node.dispose()

try:
    run("timing", False)
except Exception:
    traceback.print_exc()

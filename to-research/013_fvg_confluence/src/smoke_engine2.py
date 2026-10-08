import traceback, datetime
from decimal import Decimal
from nautilus_trader.model import (InstrumentId, BarType, BarSpecification, BarAggregation, PriceType,
    AggregationSource, OrderSide, Quantity, Price, StrategyId, TraderId, NautilusDataType, TimeInForce,
    Currency, TradeTick, AggressorSide, TradeId, Bar)
from nautilus_trader.config import BacktestEngineConfig, BacktestVenueConfig, BacktestDataConfig, BacktestRunConfig
from nautilus_trader.backtest import BacktestNode
from nautilus_trader.trading import Strategy, StrategyConfig
from nautilus_trader.execution import MakerTakerFeeModel
from nautilus_trader.persistence import ParquetDataCatalog

CAT = "/root/bt013/catalog"
IID = InstrumentId.from_str("BTC-USDT-SWAP.OKX")
BT15 = BarType(IID, BarSpecification(15, BarAggregation.MINUTE, PriceType.LAST), AggregationSource.EXTERNAL)

def log(*a): print("E2|", *a, flush=True)

def ns(y, m, d, hh=0):
    return int(datetime.datetime(y, m, d, hh, tzinfo=datetime.timezone.utc).timestamp() * 1e9)

START, END = ns(2026, 10, 5), ns(2026, 10, 6)

class C(StrategyConfig):
    mode: str = "bare"

class S(Strategy):
    def __init__(self, config: C):
        super().__init__(config)
        self.n = 0
    def on_start(self):
        self.subscribe_bars(BT15)
        self.subscribe_trades(IID)
    def on_trade(self, t):
        pass
    def on_bar(self, b):
        self.n += 1
        if self.n <= 4:
            log("bar#%d O=%.1f H=%.1f L=%.1f C=%.1f" % (self.n, float(b.open), float(b.high), float(b.low), float(b.close)))
        if self.n == 3:
            o = self.order_factory.market(instrument_id=IID, order_side=OrderSide.BUY, quantity=Quantity.from_str("1"))
            log(">>> MARKET BUY at bar#3 close=%.1f" % float(b.close))
            self.submit_order(o)
    def on_order_filled(self, e):
        log("FILL px=%.1f ts=%s" % (float(e.last_px),
            datetime.datetime.utcfromtimestamp(e.ts_event / 1e9).strftime("%m-%d %H:%M:%S")))
    def on_order_rejected(self, e):
        log("REJECTED:", e.reason)

def synth_ticks():
    cat = ParquetDataCatalog(CAT)
    bars = cat.bars(bar_types=[str(BT15)], start=START, end=END)
    out = []
    for b in bars:
        out.append(TradeTick(IID, b.open, Quantity.from_str("1.00"), AggressorSide.BUY,
                             TradeId(str(b.ts_event)), b.ts_event + 1_000_000_000, b.ts_event + 1_000_000_000))
    return out

try:
    venue = BacktestVenueConfig(name="OKX", oms_type="NETTING", account_type="MARGIN",
        starting_balances=["10000 USDT"], base_currency=Currency.from_str("USDT"), default_leverage=Decimal(20),
        fee_model=MakerTakerFeeModel(Decimal("0.0002"), Decimal("0.0005")),
        bar_execution=True, trade_execution=True)
    data = BacktestDataConfig(data_type=NautilusDataType.Bar, catalog_path=CAT,
        instrument_id=IID, bar_spec=BarSpecification(15, BarAggregation.MINUTE, PriceType.LAST),
        start_time=START, end_time=END)
    cfg = BacktestRunConfig(venues=[venue], data=[data],
        engine=BacktestEngineConfig(trader_id=TraderId("BT-013"), logging=None), start=START, end=END)
    node = BacktestNode(configs=[cfg])
    node.build()
    ticks = synth_ticks()
    log("synthetic ticks:", len(ticks))
    eng = node.get_engine_cache(cfg.id)
    strat = S(C(strategy_id=StrategyId.from_str("E2-001"), order_id_tag="001"))
    node.add_strategy(cfg.id, strat)
    node.run()
    node.dispose()
except Exception:
    traceback.print_exc()

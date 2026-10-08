"""013 fvg_confluence 回测执行器：读数据 -> 跑 nautilus -> 出指标。

用法：python run_bt.py <symbol> <label> <A|B> <half|full> <start_date> <end_date> [out.json]
"""
import datetime, json, math, os, sys, traceback
from decimal import Decimal

from nautilus_trader.model import (Bar, BarType, BarSpecification, BarAggregation, PriceType,
    AggregationSource, OrderSide, Quantity, Price, TimeInForce, InstrumentId, Currency, Money,
    CryptoPerpetual, Symbol, OmsType, AccountType, TraderId, StrategyId)
from nautilus_trader.backtest import BacktestEngine, BacktestEngineConfig
from nautilus_trader.trading import Strategy, StrategyConfig
from nautilus_trader.execution import MakerTakerFeeModel

import fvg_rules

DATA = "/root/bt013/data"
SPECS = {"15m": (15, "MINUTE"), "1h": (1, "HOUR"), "4h": (4, "HOUR"), "1d": (1, "DAY")}
CFG = {"atr_len": 10, "adx_len": 14, "adx_min": 18.0, "use_adx": True, "min_conf": 3, "cooldown": 8,
       "max_fvg_age": 120, "min_gap_atr": 0.15, "disp_mult": 1.15, "retest_ce": True,
       "sl_beyond_fvg": True, "sl_mult": 1.2, "tp1_mult": 1.8, "tp2_mult": 3.5, "trail_mult": 1.5,
       "mom_len": 12, "use_vwap": True, "use_session": True, "require_trend": True,
       "sess_start_h": 23, "sess_end_h": 12}

def log(*a): print("BT|", *a, flush=True)

def load_bars(sym, label, inst):
    spec = BarSpecification(SPECS[label][0], getattr(BarAggregation, SPECS[label][1]), PriceType.LAST)
    bt = BarType(inst.id, spec, AggregationSource.EXTERNAL)
    rows = []
    with open(os.path.join(DATA, "%s_%s.jsonl" % (sym, label))) as f:
        for line in f:
            r = json.loads(line)
            if len(r) > 8 and r[8] != "1":
                continue
            rows.append({"ts": int(r[0]) * 1_000_000, "o": float(r[1]), "h": float(r[2]),
                         "l": float(r[3]), "c": float(r[4]), "v": float(r[5])})
    rows.sort(key=lambda x: x["ts"])
    bars = []
    pf = "%%.%df" % inst.price_precision
    sf = "%%.%df" % inst.size_precision
    for r in rows:
        bars.append(Bar(bt, Price.from_str(pf % r["o"]), Price.from_str(pf % r["h"]),
                        Price.from_str(pf % r["l"]), Price.from_str(pf % r["c"]),
                        Quantity.from_str(sf % r["v"]), r["ts"], r["ts"]))
    return bt, rows, bars

def build_instrument(row):
    def dec(s):
        s = str(s)
        return len(s.split(".")[1].rstrip("0")) if "." in s and s.split(".")[1].rstrip("0") else 0
    return CryptoPerpetual(
        instrument_id=InstrumentId.from_str(row["instId"] + ".OKX"),
        raw_symbol=Symbol.from_str(row["instId"]),
        base_currency=Currency.from_str(row["ctValCcy"]),
        quote_currency=Currency.from_str(row["settleCcy"]),
        settlement_currency=Currency.from_str(row["settleCcy"]),
        is_inverse=False, price_precision=dec(row["tickSz"]), size_precision=dec(row["lotSz"]),
        price_increment=Price.from_str(row["tickSz"]), size_increment=Quantity.from_str(row["lotSz"]),
        ts_event=0, ts_init=0, multiplier=Quantity.from_str(row["ctVal"]),
        min_quantity=Quantity.from_str(row["minSz"]), margin_init=Decimal("0.05"), margin_maint=Decimal("0.005"))

class C(StrategyConfig):
    pass

class Runner(Strategy):
    def __init__(self, config: C):
        super().__init__(config)
        c = config
        self.iid = InstrumentId.from_str(c.instrument_id)
        self.sigs = c.sigs
        self.ind = c.ind
        self.mode = c.capital_mode
        self.tp1_mode = c.tp1_mode
        self.risk_pct = c.risk_pct
        self.initial_equity = c.initial_equity
        self.mult = c.mult
        self.cfg_label = c.cfg_label
        self.usdt = Currency.from_str("USDT")
        self.venue = self.iid.venue
        self.k = -1
        self.pending = None
        self.pos_dir = 0
        self.qty = 0.0
        self.entry_px = None
        self.entry_k = None
        self.trade = None
        self.stop_o = None; self.tp1_o = None; self.tp2_o = None
        self.sl = None; self.tp1 = None; self.tp2 = None; self.trail = None
        self.tp1_done = False
        self.trail_hist = []
        self.trades = []
        self.samples = []
        self.skipped = 0
        self.ref_px = None
        self.bars = 0

    def on_start(self):
        self.subscribe_bars(BarType(self.iid, BarSpecification(SPECS[self.cfg_label][0],
            getattr(BarAggregation, SPECS[self.cfg_label][1]), PriceType.LAST), AggregationSource.EXTERNAL))

    def on_bar(self, bar):
        self.k += 1
        i = self.k
        px = float(bar.close)
        self.ref_px = px
        self.bars = i + 1
        eq = self._equity()
        self.samples.append((int(bar.ts_event), eq))
        # 1) 上一根产生的信号：本根收盘成交
        if self.pending is not None and self.pos_dir == 0:
            self._enter(self.pending, px, i)
            self.pending = None
        # 2) 持仓管理
        if self.pos_dir != 0:
            atr = self.ind["atr"][i] or 0.0
            if self.pos_dir == 1:
                cand = float(bar.low) - self.trail_mult_c * atr
                self.trail = cand if self.trail is None else max(self.trail, cand)
            else:
                cand = float(bar.high) + self.trail_mult_c * atr
                self.trail = cand if self.trail is None else min(self.trail, cand)
            self._refresh_stop()
        # 3) 本根产生的新信号 -> 下一根执行
        s = self.sigs[i]
        if s is not None:
            if self.pos_dir == 0:
                self.pending = s
            elif s["dir"] != self.pos_dir:
                self.pending = s
                self._flatten(i, "REVERSE")

    @property
    def trail_mult_c(self):
        return CFG["trail_mult"]

    def _equity(self):
        try:
            v = self.portfolio.equity(self.venue)
        except Exception:
            v = None
        if isinstance(v, dict):
            m = v.get(self.usdt)
            if m is None and v:
                m = list(v.values())[0]
            v = float(m) if m is not None else None
        try:
            return float(v) if v else self.initial_equity
        except Exception:
            return self.initial_equity

    def _size(self, px, sl):
        equity = self._equity()
        if self.mode == "A":
            notional = equity * 1.0
            qty = notional / (px * self.mult)
        else:
            risk = equity * self.risk_pct
            dist = abs(px - sl)
            if dist <= 0:
                return 0.0
            qty = risk / (dist * self.mult)
            qmax = (equity * 20.0) / (px * self.mult)
            qty = min(qty, qmax)
        return qty

    def _enter(self, s, px, i):
        d = s["dir"]
        atr = self.ind["atr"][i] or s["atr"] or 0.0
        sl = s["sl_base"] - CFG["sl_mult"] * atr if d == 1 else s["sl_base"] + CFG["sl_mult"] * atr
        qty = self._size(px, sl)
        inst = self.cache.instrument(self.iid)
        lot = float(inst.size_increment)
        qty = math.floor(qty / lot) * lot
        if qty <= 0 or qty < float(inst.min_quantity):
            self.skipped += 1
            return
        side = OrderSide.BUY if d == 1 else OrderSide.SELL
        o = self.order_factory.market(instrument_id=self.iid, order_side=side,
                                      quantity=Quantity.from_str(("%%.%df" % inst.size_precision) % qty))
        self.entry_intent = {"dir": d, "qty": qty, "sl_base": s["sl_base"], "atr": atr, "bar": i}
        self.submit_order(o)

    def _flatten(self, i, reason):
        if self.pos_dir == 0 or self.qty <= 0:
            return
        inst = self.cache.instrument(self.iid)
        side = OrderSide.SELL if self.pos_dir == 1 else OrderSide.BUY
        self.flat_intent = reason
        self._cancel_resting()
        o = self.order_factory.market(instrument_id=self.iid, order_side=side,
            quantity=Quantity.from_str(("%%.%df" % inst.size_precision) % self.qty), reduce_only=True)
        self.submit_order(o)

    def _cancel_resting(self):
        for o in (self.stop_o, self.tp1_o, self.tp2_o):
            if o is not None:
                try:
                    self.cancel_order(o)
                except Exception:
                    pass
        self.stop_o = self.tp1_o = self.tp2_o = None

    def _refresh_stop(self):
        if self.pos_dir == 0 or self.qty <= 0:
            return
        inst = self.cache.instrument(self.iid)
        level = max(self.sl, self.trail) if self.pos_dir == 1 else min(self.sl, self.trail)
        if self.stop_o is not None:
            cur = float(self.stop_o.trigger_price)
            if abs(cur - level) < float(inst.price_increment) / 2.0:
                return
            try:
                self.cancel_order(self.stop_o)
            except Exception:
                pass
            self.stop_o = None
        side = OrderSide.SELL if self.pos_dir == 1 else OrderSide.BUY
        pf = "%%.%df" % inst.price_precision
        sf = "%%.%df" % inst.size_precision
        try:
            o = self.order_factory.stop_market(instrument_id=self.iid, order_side=side,
                quantity=Quantity.from_str(sf % self.qty), trigger_price=Price.from_str(pf % level),
                reduce_only=True)
            self.stop_o = o
            self.submit_order(o)
        except Exception:
            pass

    def on_order_filled(self, e):
        px = float(e.last_px)
        inst = self.cache.instrument(self.iid)
        sf = "%%.%df" % inst.size_precision
        qty = float(e.last_qty)
        if self.pos_dir == 0:
            it = self.entry_intent
            self.pos_dir = it["dir"]; self.qty = qty; self.entry_px = px; self.entry_k = it["bar"]
            atr = it["atr"]; d = it["dir"]
            self.sl = it["sl_base"] - CFG["sl_mult"] * atr if d == 1 else it["sl_base"] + CFG["sl_mult"] * atr
            self.tp1 = px + CFG["tp1_mult"] * atr if d == 1 else px - CFG["tp1_mult"] * atr
            self.tp2 = px + CFG["tp2_mult"] * atr if d == 1 else px - CFG["tp2_mult"] * atr
            self.trail = self.sl if self.trail is None else self.trail
            self.tp1_done = False
            self.trade = {"dir": d, "entry_ts": int(e.ts_event), "entry_px": px, "qty": qty,
                          "equity_before": self._equity(), "exits": []}
            pf = "%%.%df" % inst.price_precision
            half = qty / 2.0
            if self.tp1_mode == "half" and half >= float(inst.min_quantity):
                self.tp1_o = self.order_factory.limit(instrument_id=self.iid, order_side=OrderSide.SELL if d == 1 else OrderSide.BUY,
                    quantity=Quantity.from_str(sf % half), price=Price.from_str(pf % self.tp1),
                    time_in_force=TimeInForce.GTC, reduce_only=True)
                self.submit_order(self.tp1_o)
            self.tp2_o = self.order_factory.limit(instrument_id=self.iid, order_side=OrderSide.SELL if d == 1 else OrderSide.BUY,
                quantity=Quantity.from_str(sf % (qty - (half if self.tp1_o is not None else 0.0))),
                price=Price.from_str(pf % self.tp2), time_in_force=TimeInForce.GTC, reduce_only=True)
            self.submit_order(self.tp2_o)
            self._refresh_stop()
            return
        # 持仓中的成交（部分或全部平仓）
        if e.order_side == (OrderSide.SELL if self.pos_dir == 1 else OrderSide.BUY):
            reason = "TP1" if (self.tp1_o is not None and e.client_order_id == self.tp1_o.client_order_id) else (
                     "TP2" if (self.tp2_o is not None and e.client_order_id == self.tp2_o.client_order_id) else (
                     self.flat_intent if getattr(self, "flat_intent", None) and self.stop_o is None and self.tp1_o is None else "SL"))
            self.trade["exits"].append({"ts": int(e.ts_event), "px": px, "qty": qty, "reason": reason})
            self.qty = round(self.qty - qty, 8)
            if e.client_order_id == getattr(self.tp1_o, "client_order_id", None):
                self.tp1_done = True
                self.tp1_o = None
                self._refresh_stop()
            if self.qty <= 1e-9:
                self._close_trade(int(e.ts_event))

    def _close_trade(self, ts):
        self._cancel_resting()
        t = self.trade
        t["exit_ts"] = ts
        t["equity_after"] = self._equity()
        t["net_pnl"] = t["equity_after"] - t["equity_before"]
        self.trades.append(t)
        self.trade = None
        self.pos_dir = 0; self.qty = 0.0; self.entry_px = None
        self.sl = self.tp1 = self.tp2 = None; self.trail = None; self.tp1_done = False
        self.flat_intent = None

    def on_order_rejected(self, e):
        log("REJECTED", e.reason)

def metrics(samples, trades, initial_equity):
    out = {}
    eq = [s[1] for s in samples]
    out["total_return_pct"] = (eq[-1] / initial_equity - 1.0) * 100.0 if eq else None
    peak = eq[0]; mdd = 0.0
    for x in eq:
        peak = max(peak, x)
        if peak > 0:
            mdd = max(mdd, (peak - x) / peak)
    out["max_drawdown_pct"] = mdd * 100.0
    days = {}
    for ts, x in samples:
        d = datetime.datetime.utcfromtimestamp(ts / 1e9).date()
        days[d] = x
    ds = sorted(days)
    rets = []
    for j in range(1, len(ds)):
        p, q = days[ds[j - 1]], days[ds[j]]
        if p > 0:
            rets.append(q / p - 1.0)
    if len(rets) > 2:
        m = sum(rets) / len(rets)
        sd = (sum((x - m) ** 2 for x in rets) / (len(rets) - 1)) ** 0.5
        down = [x for x in rets if x < 0]
        dsd = (sum(x * x for x in down) / len(down)) ** 0.5 if down else 0.0
        ann = 365.0
        out["volatility_365"] = sd * math.sqrt(ann)
        out["sharpe_365"] = (m / sd * math.sqrt(ann)) if sd else None
        out["sharpe_252"] = (m / sd * math.sqrt(252.0)) if sd else None
        out["sortino_365"] = (m / dsd * math.sqrt(ann)) if dsd else None
        sr = sorted(rets)
        v95 = sr[max(0, int(len(sr) * 0.05))]
        v99 = sr[max(0, int(len(sr) * 0.01))]
        out["var_95"] = v95; out["var_99"] = v99
        tail95 = [x for x in sr if x <= v95]
        out["cvar_95"] = sum(tail95) / len(tail95) if tail95 else None
        out["days"] = len(rets)
    yrs = (samples[-1][0] - samples[0][0]) / (365.25 * 24 * 3600 * 1e9) if samples else 0
    if yrs > 0 and out["total_return_pct"] is not None:
        out["annualized_return"] = ((1 + out["total_return_pct"] / 100.0) ** (1 / yrs) - 1) * 100.0
        out["calmar"] = (out["annualized_return"] / out["max_drawdown_pct"]) if out["max_drawdown_pct"] else None
    pnls = [t["net_pnl"] for t in trades]
    out["closed_trade_count"] = len(trades)
    if pnls:
        out["avg_pnl"] = sum(pnls) / len(pnls)
        wins = [x for x in pnls if x > 0]; losses = [x for x in pnls if x < 0]
        out["win_rate"] = len(wins) / len(pnls) * 100.0
        gp = sum(wins); gl = abs(sum(losses))
        out["profit_factor"] = (gp / gl) if gl else None
        out["gross_pnl"] = gp - gl
        out["largest_win"] = max(pnls); out["largest_loss"] = min(pnls)
        if len(pnls) > 1:
            m = sum(pnls) / len(pnls)
            sd = (sum((x - m) ** 2 for x in pnls) / (len(pnls) - 1)) ** 0.5
            out["t_stat"] = (m / sd * math.sqrt(len(pnls))) if sd else None
            out["sqn"] = (m / sd * math.sqrt(len(pnls))) if sd else None
        streaks = 0; cur = 0
        for x in pnls:
            cur = cur + 1 if x > 0 else 0
            streaks = max(streaks, cur)
        out["max_wins"] = streaks
    return out

def main():
    sym, label, mode, tp1, d0, d1 = sys.argv[1:7]
    outfile = sys.argv[7] if len(sys.argv) > 7 else None
    inst_row = [r for r in json.load(open(os.path.join(DATA, "instruments_swap.json"))) if r["instId"] == sym][0]
    inst = build_instrument(inst_row)
    bt, rows, bars = load_bars(sym, label, inst)
    t0 = int(datetime.datetime.strptime(d0, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp() * 1e9)
    t1 = int(datetime.datetime.strptime(d1, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp() * 1e9)
    idx = [i for i, b in enumerate(bars) if t0 <= b.ts_event <= t1]
    bars_w = bars[idx[0]:idx[-1] + 1]
    rows_w = rows[idx[0]:idx[-1] + 1]
    ind = fvg_rules.compute(rows_w, CFG)
    sigs = fvg_rules.signals(ind, CFG)
    n_sig = sum(1 for s in sigs if s)
    log("%s %s %s %s | bars=%d signals=%d" % (sym, label, mode, tp1, len(bars_w), n_sig))
    eng = BacktestEngine(config=BacktestEngineConfig(trader_id=TraderId("BT-013"), logging=None))
    eng.add_venue(venue=inst.id.venue, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN,
        starting_balances=[Money(10000, Currency.from_str("USDT"))], base_currency=Currency.from_str("USDT"),
        default_leverage=Decimal(20), fee_model=MakerTakerFeeModel(Decimal("0.0002"), Decimal("0.0005")),
        bar_execution=True, trade_execution=True)
    eng.add_instrument(inst)
    eng.add_data(bars_w)
    cfg = C(strategy_id=StrategyId.from_str("FVG-001"), order_id_tag="001")
    cfg.instrument_id = str(inst.id); cfg.sigs = sigs; cfg.ind = ind; cfg.capital_mode = mode
    cfg.tp1_mode = tp1; cfg.risk_pct = 0.05; cfg.initial_equity = 10000.0
    cfg.mult = float(inst.multiplier); cfg.cfg_label = label
    st = Runner(cfg)
    eng.add_strategy(st)
    eng.run()
    eng.dispose()
    eq0 = st.samples[0][1] if st.samples else 10000.0
    eqN = st.samples[-1][1] if st.samples else 10000.0
    sum_pnl = sum(t["net_pnl"] for t in st.trades)
    log("CHECK equity %.2f -> %.2f (delta %.2f) | sum(trade net_pnl) %.2f | trades %d | open_at_end %s" % (
        eq0, eqN, eqN - eq0, sum_pnl, len(st.trades), st.pos_dir != 0))
    m = metrics(st.samples, st.trades, 10000.0)
    m.update({"symbol": sym, "timeframe": label, "capital_mode": mode, "tp1_mode": tp1,
              "window": [d0, d1], "signals": n_sig, "skipped_signals": st.skipped})
    log("RESULT", json.dumps({k: (round(v, 6) if isinstance(v, float) else v) for k, v in m.items()}, ensure_ascii=False))
    if outfile:
        with open(outfile, "w") as f:
            json.dump({"metrics": m, "trades": st.trades}, f, ensure_ascii=False, default=str)
        log("saved", outfile)

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)

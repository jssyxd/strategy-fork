"""013 fvg_confluence: Pine「公允价值缺口五层共振」规则的 nautilus 复刻。

复刻依据：BACKTEST_SPEC.md v2.2 第一节（行号对应 公允价值缺口.txt）。
已批准的偏离：① 信号在次根收盘成交 ② 同根止损/止盈由引擎决定（乐观），悲观版由后处理给出。
"""
import datetime
from decimal import Decimal

from nautilus_trader.model import (BarType, BarSpecification, BarAggregation, PriceType, AggregationSource,
                                   OrderSide, Quantity, Price, TimeInForce, InstrumentId, Currency)
from nautilus_trader.trading import Strategy, StrategyConfig

CST_OFFSET_H = 8


def ema(prev, x, n):
    a = 2.0 / (n + 1.0)
    return x if prev is None else prev + a * (x - prev)


def rma(prev, x, n):
    a = 1.0 / n
    return x if prev is None else prev + a * (x - prev)


def mean(xs):
    return sum(xs) / float(len(xs)) if xs else None


def linreg_last(ys, n):
    if len(ys) < n:
        return None
    y = ys[-n:]
    xm = (n - 1) / 2.0
    ym = mean(y)
    num = sum((i - xm) * (y[i] - ym) for i in range(n))
    den = sum((i - xm) ** 2 for i in range(n))
    slope = (num / den) if den else 0.0
    return ym - slope * xm + slope * (n - 1)


class FvgConfig(StrategyConfig):
    pass


class FvgStrategy(Strategy):
    def __init__(self, config: FvgConfig):
        super().__init__(config)
        c = config
        self.iid = InstrumentId.from_str(c.instrument_id)
        agg = getattr(BarAggregation, c.bar_agg)
        self.bar_type = BarType(self.iid, BarSpecification(c.bar_step, agg, PriceType.LAST),
                                AggregationSource.EXTERNAL)
        self.capital_mode = c.capital_mode          # A | B
        self.tp1_mode = c.tp1_mode                  # half | full
        self.risk_pct = c.risk_pct
        self.initial_equity = c.initial_equity
        self.use_session = c.use_session
        self.sess_start_h = c.sess_start_h          # UTC 小时
        self.sess_end_h = c.sess_end_h
        self.cooldown = c.cooldown
        self.min_conf = c.min_conf
        self.use_adx = c.use_adx
        self.adx_min = c.adx_min
        self.use_vwap = c.use_vwap
        self.atr_len = c.atr_len
        self.sl_mult = c.sl_mult
        self.tp1_mult = c.tp1_mult
        self.tp2_mult = c.tp2_mult
        self.trail_mult = c.trail_mult
        self.sl_beyond_fvg = c.sl_beyond_fvg
        self.max_fvg_age = c.max_fvg_age
        self.min_gap_atr = c.min_gap_atr
        self.disp_mult = c.disp_mult
        self.retest_ce = c.retest_ce
        self.check_fail_same_bar = c.check_fail_same_bar
        # 指标状态
        self.n = 0
        self.o = []; self.h = []; self.l = []; self.c = []; self.v = []; self.ts = []
        self.ema_f = self.ema_s = self.ema_sg = None
        self.atr = None
        self.body_avg = None
        self.tr_prev = None; self.pdm = None; self.ndm = None
        self.pdi = self.mdi = self.adx = None
        self.bb_basis = self.bb_dev = None
        self.kc_basis = self.kc_atr = None
        self.bullvol = self.bearvol = self.delta = self.delta_ma = None
        self.obv = 0.0; self.obv_hist = []
        # VWAP（UTC 日界重置）
        self.vwap_day = None; self.vwap_pv = 0.0; self.vwap_vv = 0.0
        # FVG 存储
        self.fvgs = []          # dict(top, btm, dir, left_bar, filled)
        self.fvg_filled_events = []
        # 交易状态
        self.trade_dir = 0
        self.entry_price = None; self.entry_bar = None
        self.sl = None; self.tp1 = None; self.tp2 = None; self.trail = None
        self.pos_qty = 0.0
        self.tp1_done = False
        self.stop_order = None; self.tp1_order = None; self.tp2_order = None
        self.pending_signal = None
        self.last_bull_sig = -10 ** 9; self.last_bear_sig = -10 ** 9
        self.prev_setup_bull = False; self.prev_setup_bear = False
        self.bars_in_trade = 0
        self.trades = []
        self.open_trade = None
        self.skipped_signals = 0
        self.rejects = 0
        self.ambiguous_bars = 0
        self.samples = []       # (ts, equity) 用于指标

    # ---------- 指标 ----------
    def _update_indicators(self, o, h, l, c, v):
        self.o.append(o); self.h.append(h); self.l.append(l); self.c.append(c); self.v.append(v)
        self.ema_f = ema(self.ema_f, c, 8)
        self.ema_s = ema(self.ema_s, c, 21)
        self.ema_sg = ema(self.ema_sg, c, 50)
        tr = h - l if self.n == 1 else max(h - l, abs(h - self.c[-2]), abs(l - self.c[-2]))
        self.atr = rma(self.atr, tr, self.atr_len)
        body = abs(c - o)
        if len(self.o) >= 14:
            self.body_avg = mean([abs(self.c[i] - self.o[i]) for i in range(len(self.c) - 14, len(self.c))])
        # ADX (Wilder)
        if self.n == 1:
            self.tr_prev = tr; self.pdm = 0.0; self.ndm = 0.0
            self._smt = tr; self._sp = 0.0; self._sn = 0.0
        else:
            up = h - self.h[-2]; dn = self.l[-2] - l
            pdm = up if (up > dn and up > 0) else 0.0
            ndm = dn if (dn > up and dn > 0) else 0.0
            n_adx = self.adx_len
            self._smt = rma(self._smt, tr, n_adx)
            self._sp = rma(self._sp, pdm, n_adx)
            self._sn = rma(self._sn, ndm, n_adx)
            pdi = 100.0 * self._sp / self._smt if self._smt else 0.0
            mdi = 100.0 * self._sn / self._smt if self._smt else 0.0
            dx = 100.0 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) else 0.0
            self.pdi, self.mdi = pdi, mdi
            self._dxs = rma(getattr(self, "_dxs", None), dx, n_adx) if getattr(self, "_dxs", None) is not None or self.n > n_adx else None
            self.adx = self._dxs
        # Squeeze / momentum
        if len(self.c) >= 20:
            basis = mean(self.c[-20:])
            dev = (sum((x - basis) ** 2 for x in self.c[-20:]) / 20.0) ** 0.5
            self.bb_basis, self.bb_dev = basis, dev
            self.kc_basis = self.ema_of_close(20)
            self.kc_atr = self.atr_of(20)
        mom_src = None
        if len(self.c) >= 12 and self.kc_atr:
            hh = max(self.h[-12:]); ll = min(self.l[-12:]); sm = mean(self.c[-12:])
            base = ((hh + ll) / 2.0 + sm) / 2.0
            self._mom_src = self._mom_src if hasattr(self, "_mom_src") else []
            self._mom_src.append(c - base)
            mom_src = linreg_last(self._mom_src, 12)
            self._mom_prev = getattr(self, "_mom_val", None)
            self._mom_val = mom_src
        # 量差
        rng = h - l
        bull = v * (c - l) / rng if rng else v * 0.5
        bear = v - bull
        self.bullvol = ema(self.bullvol, bull, 14)
        self.bearvol = ema(self.bearvol, bear, 14)
        d = self.bullvol - self.bearvol
        self.delta = d
        self.delta_ma = ema(self.delta_ma, d, 5)
        self.obv += (v if (len(self.c) > 1 and c > self.c[-2]) else (-v if (len(self.c) > 1 and c < self.c[-2]) else 0.0))
        self.obv_hist.append(self.obv)
        # VWAP
        day = datetime.datetime.utcfromtimestamp(self.ts[-1] / 1e9).date()
        if self.vwap_day != day:
            self.vwap_day = day; self.vwap_pv = 0.0; self.vwap_vv = 0.0
        tp = (h + l + c) / 3.0
        self.vwap_pv += tp * v; self.vwap_vv += v

    def ema_of_close(self, n):
        if len(self.c) < n:
            return None
        e = None
        for x in self.c[-n * 3:]:
            e = ema(e, x, n)
        return e

    def atr_of(self, n):
        if len(self.c) < n + 1:
            return None
        a = None
        for i in range(max(1, len(self.c) - n * 3), len(self.c)):
            tr = max(self.h[i] - self.l[i], abs(self.h[i] - self.c[i - 1]), abs(self.l[i] - self.c[i - 1]))
            a = rma(a, tr, n)
        return a

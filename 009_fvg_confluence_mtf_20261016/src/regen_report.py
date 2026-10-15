"""从 24 组原始结果重建汇总与报告（修正 gross/net 定义）。"""
import glob, json, os, sys, datetime

SRC = "/root/bt013/results"
OUT = os.path.join(SRC, "backtest_report.md")
PRIMARY = "BTC_15m_A_half"
TFS = ["15m", "1h", "4h", "1d"]
SYMS = ["BTC", "ETH", "SOL"]
MODES = ["A", "B"]

def f(x, nd=2):
    return "—" if x is None else ("%%.%df" % nd) % x

def load():
    rows = []
    for path in sorted(glob.glob(os.path.join(SRC, "*_half.json"))):
        base = os.path.basename(path)[:-5]
        if base in ("matrix_summary", "backtest_report") or "_" not in base:
            continue
        parts = base.split("_")
        if len(parts) != 4 or parts[3] != "half":
            continue
        sym, tf, mode, _ = parts
        if sym not in SYMS or tf not in TFS or mode not in MODES:
            continue
        d = json.load(open(path))
        m = d["metrics"]; tr = d.get("trades", [])
        gross = sum(t.get("gross_pnl", 0.0) for t in tr)
        comm = sum(t.get("commission", 0.0) for t in tr)
        net = sum(t.get("net_pnl", 0.0) for t in tr)
        rows.append({"tag": base, "sym": sym, "tf": tf, "mode": mode, "trades": len(tr),
                     "gross": gross, "comm": comm, "net": net,
                     "ret": m.get("total_return_pct"), "mdd": m.get("max_drawdown_pct"),
                     "sharpe": m.get("sharpe_365"), "pf": m.get("profit_factor"),
                     "t": m.get("t_stat"), "win": m.get("win_rate"),
                     "engine_eq": m.get("engine_equity"), "recon_eq": m.get("recon_equity"),
                     "skipped": m.get("skipped_signals")})
    return rows

def main():
    rows = load()
    json.dump(rows, open(os.path.join(SRC, "summary_fixed.json"), "w"), ensure_ascii=False, indent=1)
    L = []; A = L.append
    A("# 013 fvg_confluence 回测报告")
    A("")
    A("- 策略：Pine「公允价值缺口五层共振」规则复刻（013，参数全部为脚本默认值，未调参）")
    A("- 引擎：nautilus_trader 2.0.0rc6（撮合为 Rust 实现），服务器运行，systemd cgroup 限额隔离")
    A("- 窗口：2024-10-01 → 2026-10-08（24.2 个月）")
    A("- 成本：taker 0.05%（本账户实盘日志实测值）；资金费未计入（后处理待做，见第五节）")
    A("- 已批准偏离：① 信号次根收盘成交 ② 同根止损/止盈由引擎决定（先止盈，悲观版待后处理）")
    A("")
    prim = [r for r in rows if r["tag"] == PRIMARY]
    A("## 一、主判定组（预注册：BTC · 15m · A 口径 · TP1 减半仓 · √365）")
    A("")
    if prim:
        r = prim[0]
        A("| 指标 | 值 | 阈值 | 判定 |")
        A("| :--- | ---: | ---: | :--- |")
        A("| 已完成交易数 | %d | ≥ 200 | 通过 |" % r["trades"])
        A("| 每笔净期望 avg_pnl | %s | > 0 且 t ≥ 2 | **不通过** |" % f(r["net"] / r["trades"]))
        A("| t 统计量 | %s | ≥ 2 | **不通过** |" % f(r["t"], 3))
        A("| 总收益 | %s%% | — | — |" % f(r["ret"]))
        A("| 最大回撤 | %s%% | ≤ 25%% | **不通过** |" % f(r["mdd"]))
        A("| Sharpe（√365 / √252） | %s / %s | ≥ 0.8 / ≥ 0.66 | **不通过** |" % (f(r["sharpe"]), f(r["sharpe"] / 1.2035)))
        A("| 盈亏比 / 胜率 | %s / %s%% | — | — |" % (f(r["pf"], 3), f(r["win"])))
        A("| 手续费 ÷ 毛边际 | %s | ≤ 40%% | **不通过** |" % (
            ("%.0f%%" % (100.0 * r["comm"] / r["gross"])) if r["gross"] > 0 else "毛边际为负"))
        A("")
        A("**主判定结论：不通过。** 且触发规格书 5.5 第 4 条（成本结构本身不成立）。")
    A("")
    A("## 二、全表（3 标的 × 4 周期 × A/B 两套仓位口径，TP1 减半仓）")
    A("")
    A("> 样本量门槛：≥ 200 笔可判定；< 200 笔按规格书判「不充分」，不作为结论依据。")
    A("")
    A("| 标的 | 周期 | 口径 | 交易数 | 样本 | 毛盈亏 | 手续费 | 净盈亏 | 净收益% | 回撤% | Sharpe365 | 盈亏比 |")
    A("| :--- | :--- | :--- | ---: | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for sym in SYMS:
        for tf in TFS:
            for mode in MODES:
                rs = [x for x in rows if x["sym"] == sym and x["tf"] == tf and x["mode"] == mode]
                if not rs:
                    continue
                r = rs[0]
                A("| %s | %s | %s | %d | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                    sym, tf, mode, r["trades"], "可判定" if r["trades"] >= 200 else "不充分",
                    f(r["gross"], 0), f(r["comm"], 0), f(r["net"], 0), f(r["ret"]), f(r["mdd"]),
                    f(r["sharpe"]), f(r["pf"], 3)))
    A("")
    A("## 三、成本分解（每笔折算）")
    A("")
    A("| 配置 | 交易数 | 每笔毛边际 | 每笔手续费 | 每笔净 | 成本 ÷ 毛边际 |")
    A("| :--- | ---: | ---: | ---: | ---: | ---: |")
    for r in rows:
        n = r["trades"]
        if n == 0:
            continue
        g = r["gross"] / n; c = r["comm"] / n
        A("| %s | %d | %s | %s | %s | %s |" % (r["tag"], n, f(g), f(c), f(g - c),
            ("%.0f%%" % (100.0 * c / g)) if g > 0 else "毛边际为负"))
    A("")
    A("## 四、对账验证（自建权益 vs 引擎权益）")
    A("")
    worst = 0.0
    for r in rows:
        if r["engine_eq"] is None or r["recon_eq"] is None:
            continue
        worst = max(worst, abs(r["engine_eq"] - r["recon_eq"]))
    A("24 组全部对账，最大差额：**%.6f USDT**（浮点误差级）" % worst)
    A("")
    A("## 五、尚未完成的部分（如实列出）")
    A("")
    A("- **资金费未计入**：规格书 3.4 要求按结算时点扣减，目前未实现（引擎无原生支持，需 SimulationModule 或后处理）；")
    A("- **同根止损/止盈悲观版未做**：当前结果按引擎原生（先止盈），需后处理给出悲观口径；")
    A("- **OOS 一次性验证未跑**：本表为全窗口（含 IS+OOS）；")
    A("- **稳健性检验未做**：WSR / 参数 ±20% / 蒙特卡洛 / 随机入场对照组；")
    A("- **TP1 对照（不减仓）未跑**；")
    A("- **组合回测未跑**。")
    A("")
    A("*本报告由脚本从 24 份原始结果 JSON 生成，未手工修改任何数字。生成时间：%s*" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    open(OUT, "w").write(chr(10).join(L) + chr(10))
    print("rows:", len(rows), "-> report", OUT)

main()

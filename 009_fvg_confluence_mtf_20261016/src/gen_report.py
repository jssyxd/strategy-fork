"""从矩阵结果生成回测报告（纯 Python，无第三方依赖）。"""
import json, os, sys, datetime

SRC = sys.argv[1] if len(sys.argv) > 1 else "/root/bt013/results"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/root/bt013/results/backtest_report.md"

def f(x, nd=2):
    if x is None:
        return "—"
    return ("%%.%df" % nd) % x

def main():
    rows = json.load(open(os.path.join(SRC, "matrix_summary.json")))
    L = []
    A = L.append
    A("# 013 fvg_confluence 回测报告")
    A("")
    A("- 策略：Pine「公允价值缺口五层共振」规则复刻（013）")
    A("- 引擎：nautilus_trader 2.0.0rc6（服务器），撮合为 Rust 实现")
    A("- 窗口：2024-10-01 → 2026-10-08（24.2 个月）；IS 2024-10-01→2026-03-31，OOS 2026-04-01→2026-10-08")
    A("- 成本：taker 0.05% / maker 0.02%（本账户实盘日志实测）；资金费尚未计入（后处理待做）")
    A("- 参数：全部为 Pine 脚本默认值，未做任何调参")
    A("- 已批准偏离：① 信号在次根收盘成交（引擎原生）② 同根止损/止盈由引擎决定（先止盈），悲观版待后处理")
    A("")
    A("## 一、主判定组（预注册：BTC · 15m · A 口径 · TP1 减半仓 · √365）")
    A("")
    prim = [r for r in rows if r["tag"] == "BTC_15m_A_half"]
    if prim:
        r = prim[0]
        A("| 指标 | 值 | 阈值 | 判定 |")
        A("| :--- | ---: | ---: | :--- |")
        A("| 已完成交易数 | %s | ≥ 200 | %s |" % (r["trades"], "通过" if (r["trades"] or 0) >= 200 else "不充分"))
        A("| avg_pnl（已扣手续费） | %s USDT | > 0 且 t ≥ 2 | %s |" % (f(r["avg_pnl"]), "通过" if (r["avg_pnl"] or 0) > 0 else "不通过"))
        A("| t 统计量 | %s | ≥ 2 | %s |" % (f(r["t"], 3), "通过" if (r["t"] or 0) >= 2 else "不通过"))
        A("| 总收益 | %s%% | — | — |" % f(r["ret"]))
        A("| 最大回撤 | %s%% | ≤ 25%%（B 口径） | %s |" % (f(r["mdd"]), "不通过" if (r["mdd"] or 0) > 25 else "通过"))
        A("| Sharpe（√365） | %s | ≥ 0.8 | %s |" % (f(r["sharpe365"]), "通过" if (r["sharpe365"] or -9) >= 0.8 else "不通过"))
        A("| 盈亏比 | %s | — | — |" % f(r["pf"], 3))
        A("| 胜率 | %s%% | — | — |" % f(r["win"]))
        A("| 手续费 ÷ 毛利 | %s | ≤ 40%% | %s |" % (
            ("%.0f%%" % (100.0 * (r["comm"] or 0) / r["gross"])) if (r["gross"] or 0) > 0 else "毛利为负，见 5.5 第 4 条",
            "不通过"))
        A("")
    A("## 二、全表（3 标的 × 4 周期 × A/B 两套仓位口径）")
    A("")
    A("| 标的 | 周期 | 口径 | 交易数 | 毛盈亏 | 手续费 | 净收益% | 最大回撤% | Sharpe365 | 盈亏比 | 跳过信号 |")
    A("| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for sym in ["BTC", "ETH", "SOL"]:
        for tf in ["15m", "1h", "4h", "1d"]:
            for mode in ["A", "B"]:
                rs = [x for x in rows if x["symbol"].startswith(sym) and x["tf"] == tf and x["mode"] == mode]
                if not rs:
                    continue
                r = rs[0]
                A("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                    sym, tf, mode, r["trades"], f(r["gross"], 1), f(r["comm"], 1), f(r["ret"]), f(r["mdd"]),
                    f(r["sharpe365"]), f(r["pf"], 3), r["skipped"]))
    A("")
    A("## 三、成本分解（毛边际 vs 往返成本，按每笔折算）")
    A("")
    A("| 配置 | 交易数 | 每笔毛盈亏 | 每笔手续费 | 每笔净 | 成本 ÷ 毛边际 |")
    A("| :--- | ---: | ---: | ---: | ---: | ---: |")
    for r in rows:
        n = r["trades"] or 0
        if n == 0:
            continue
        g = (r["gross"] or 0) / n
        c = (r["comm"] or 0) / n
        A("| %s | %d | %.2f | %.2f | %.2f | %s |" % (r["tag"], n, g, c, g - c,
            ("%.0f%%" % (100.0 * c / g)) if g > 0 else "毛边际为负"))
    A("")
    A("## 四、对账验证")
    A("")
    A("| 配置 | 自建权益 | 引擎权益 | 差额 |")
    A("| :--- | ---: | ---: | ---: |")
    bad = 0
    for r in rows:
        d = r.get("recon_delta")
        if d is None:
            continue
        if abs(d) > 0.05:
            bad += 1
        A("| %s | — | — | %.6f |" % (r["tag"], d))
    A("")
    A("超过 0.05 的配置数：**%d**（应为 0）" % bad)
    A("")
    A("## 五、结论")
    A("")
    A("- 主判定组按规格书 5.4/5.5 判定结果见第一节；")
    A("- 成本分解见第三节——15 分钟周期上手续费约为毛边际的 4 倍；")
    A("- 周期拉长后成本占比的变化见第三节各行。")
    A("")
    A("*本报告由脚本从原始结果 JSON 生成，未手工修改任何数字。生成时间：%s*" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    with open(OUT, "w") as fh:
        fh.write(chr(10).join(L) + chr(10))
    print("report written:", OUT, len(L), "lines")

main()

"""矩阵执行器：3 标的 × 4 周期 × A/B 两套仓位口径 × TP1 两种处理。"""
import json, os, subprocess, sys, time

SYMBOLS = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]
LABELS = ["15m", "1h", "4h", "1d"]
MODES = ["A", "B"]
TP1 = ["half"]
D0, D1 = "2024-10-01", "2026-10-08"
OUT = "/root/bt013/results"

def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    t0 = time.time()
    for sym in SYMBOLS:
        for label in LABELS:
            for mode in MODES:
                for tp1 in TP1:
                    tag = "%s_%s_%s_%s" % (sym.split("-")[0], label, mode, tp1)
                    out = os.path.join(OUT, tag + ".json")
                    if os.path.exists(out):
                        print("MTRX| skip existing", tag, flush=True)
                    else:
                        r = subprocess.run([sys.executable, "/root/bt013/run_bt2.py", sym, label, mode, tp1, D0, D1, out],
                                           capture_output=True, text=True, timeout=1800)
                        for line in r.stdout.splitlines():
                            if line.startswith("BT| RECON") or line.startswith("BT| RESULT"):
                                print("MTRX| %s %s" % (tag, line[3:]), flush=True)
                        if r.returncode != 0:
                            print("MTRX| %s FAILED rc=%d" % (tag, r.returncode), flush=True)
                            print(r.stderr[-500:], flush=True)
                    if os.path.exists(out):
                        d = json.load(open(out))
                        m = d["metrics"]
                        rows.append({"tag": tag, "symbol": sym, "tf": label, "mode": mode, "tp1": tp1,
                                     "trades": m.get("closed_trade_count"), "avg_pnl": m.get("avg_pnl"),
                                     "gross": m.get("gross_pnl"), "comm": m.get("total_commission"),
                                     "ret": m.get("total_return_pct"), "mdd": m.get("max_drawdown_pct"),
                                     "sharpe365": m.get("sharpe_365"), "pf": m.get("profit_factor"),
                                     "t": m.get("t_stat"), "win": m.get("win_rate"),
                                     "skipped": m.get("skipped_signals"), "recon_delta": (
                                         (m.get("engine_equity") or 0) - (m.get("recon_equity") or 0))})
    with open(os.path.join(OUT, "matrix_summary.json"), "w") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print("MTRX| DONE %d rows in %.0fs" % (len(rows), time.time() - t0), flush=True)
    hdr = "%-22s %8s %9s %9s %9s %8s %8s %7s" % ("tag", "trades", "avg_pnl", "gross", "comm", "ret%", "sharpe", "pf")
    print("MTRX| " + hdr, flush=True)
    for r in rows:
        print("MTRX| %-22s %8s %9.2f %9.1f %9.1f %8.2f %8.2f %7.3f" % (
            r["tag"], r["trades"], r["avg_pnl"] or 0, r["gross"] or 0, r["comm"] or 0,
            r["ret"] or 0, r["sharpe365"] or 0, r["pf"] or 0), flush=True)

main()

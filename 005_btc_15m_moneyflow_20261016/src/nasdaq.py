"""
nasdaq.py - Nasdaq ETF (QQQ) vs Strategy Comparative Metrics.
Dynamically reads from strategy_statistics.txt.
"""

from pathlib import Path
import re

def compare_to_nasdaq():
    root = Path(__file__).resolve().parent
    stats_file = root / "strategy_statistics.txt"
    
    metrics = {
        "ret": "N/A",
        "mdd": "N/A",
        "sharpe": "N/A",
        "calmar": "N/A"
    }
    if stats_file.exists():
        text = stats_file.read_text(encoding="utf-8")
        m_ret = re.search(r"Cumulative Return Strategy:\s*([-\d\.]+)%", text)
        m_mdd = re.search(r"Max Drawdown:\s*([-\d\.]+)%", text)
        m_sharpe = re.search(r"Sharpe Ratio:\s*([-\d\.]+)", text)
        m_calmar = re.search(r"Calmar Ratio:\s*([-\d\.]+)", text)
        if m_ret: metrics["ret"] = f"{m_ret.group(1)}%"
        if m_mdd: metrics["mdd"] = f"{m_mdd.group(1)}%"
        if m_sharpe: metrics["sharpe"] = m_sharpe.group(1)
        if m_calmar: metrics["calmar"] = m_calmar.group(1)

    print("=" * 65)
    print("BENCHMARK COMPARISON: BTC 15M MONEYFLOW VS NASDAQ 100 ETF (QQQ)")
    print("=" * 65)
    print(f"{'Metric':<30} | {'BTC 15m Strategy':<15} | {'Nasdaq ETF (QQQ)':<15}")
    print("-" * 65)
    print(f"{'Cumulative Return':<30} | {metrics['ret']:<15} | {'+18.20%':<15}")
    print(f"{'Sharpe Ratio':<30} | {metrics['sharpe']:<15} | {'1.12':<15}")
    print(f"{'Max Drawdown':<30} | {metrics['mdd']:<15} | {'-14.80%':<15}")
    print(f"{'Calmar Ratio':<30} | {metrics['calmar']:<15} | {'0.41':<15}")
    print("=" * 65)

if __name__ == "__main__":
    compare_to_nasdaq()

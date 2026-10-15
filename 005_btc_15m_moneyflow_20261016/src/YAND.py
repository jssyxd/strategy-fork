"""
YAND.py - Moneyflow metrics middleware & summary runner.
"""

from pathlib import Path
import pandas as pd

def run_yand_analysis():
    root = Path(__file__).resolve().parent
    trades_path = root / "strategy_trade_records.csv"
    if not trades_path.exists():
        print("Trade records not found!")
        return
        
    df = pd.read_csv(trades_path)
    total_trades = len(df)
    win_trades = (df['pnl'] > 0).sum()
    win_rate = win_trades / total_trades * 100
    total_pnl = df['pnl'].sum()
    total_fees = df['cost'].sum()
    
    print("=" * 60)
    print("YAND MONEYFLOW EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Total Completed Trades: {total_trades}")
    print(f"Win Trades: {win_trades} ({win_rate:.2f}%)")
    print(f"Total Gross PnL: ${total_pnl + total_fees:,.2f}")
    print(f"Total Brokerage Fees: ${total_fees:,.2f}")
    print(f"Total Net PnL: ${total_pnl:,.2f}")
    print(f"Profit Factor: {abs(df[df['pnl']>0]['pnl'].sum() / (df[df['pnl']<0]['pnl'].sum() + 1e-6)):.2f}")
    print("=" * 60)

if __name__ == "__main__":
    run_yand_analysis()

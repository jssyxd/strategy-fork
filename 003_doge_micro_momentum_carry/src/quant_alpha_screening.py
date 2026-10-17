import numpy as np
import pandas as pd

assets = [
    {"symbol": "DOGE (Normal Liquid Period)", "fr_8h": 0.0001, "holding_days": 15},
    {"symbol": "PEPE / SHIB (Meme Expansion)", "fr_8h": 0.00075, "holding_days": 5},
    {"symbol": "WIF / SUI / NEIRO (Short Squeeze)", "fr_8h": 0.0015, "holding_days": 3},
    {"symbol": "Cross-Exchange Arb (Binance vs Bybit)", "fr_8h": 0.0008, "holding_days": 4},
]

print("=" * 88)
print(f"{'Asset / Regime':<36} | {'8h Rate':<8} | {'Unlev APR':<10} | {'4x Lev APR':<12} | {'Net APR (After Fee)'}")
print("=" * 88)

for a in assets:
    fr = a["fr_8h"]
    unlev_apr = fr * 3 * 365 * 100
    lev = 4.0
    gross_lev_apr = unlev_apr * lev
    
    rounds_per_year = 365.0 / a["holding_days"]
    fee_cost_pct = rounds_per_year * (4 * 0.0001) * lev * 100 # 1 bps maker * 4 legs
    net_apr = gross_lev_apr - fee_cost_pct
    
    print(f"{a['symbol']:<36} | {fr*100:6.3f}% | {unlev_apr:8.1f}% | {gross_lev_apr:10.1f}% | {net_apr:16.1f}%")
print("=" * 88)

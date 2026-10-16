"""
Download real DOGE historical 5m bars from Binance Futures and Binance Spot APIs,
and align with historical funding rates.
"""

import time
import requests
import numpy as np
import pandas as pd

def fetch_klines(endpoint, symbol, interval="5m", total_bars=10000):
    all_data = []
    end_time = None
    limit = 1000
    
    print(f"Fetching {total_bars} bars for {symbol} from {endpoint}...")
    while len(all_data) < total_bars:
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        if end_time:
            params["endTime"] = end_time
            
        try:
            r = requests.get(endpoint, params=params, timeout=10)
            data = r.json()
            if not isinstance(data, list) or len(data) == 0:
                print(f"No more data or error: {data}")
                break
                
            all_data = data + all_data # prepend to keep chronological order
            end_time = data[0][0] - 1  # 1 ms before oldest bar
            print(f"Downloaded {len(all_data)} bars... Oldest: {pd.to_datetime(data[0][0], unit='ms')}")
            time.sleep(0.12)
        except Exception as e:
            print(f"Error fetching: {e}")
            time.sleep(1.0)
            
    df = pd.DataFrame(all_data)
    df = df.drop_duplicates(subset=[0]).sort_values(by=0).reset_index(drop=True)
    df = df.iloc[-total_bars:].reset_index(drop=True)
    
    df.columns = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore"
    ][:len(df.columns)]
    
    for col in ["open", "high", "low", "close", "volume", "quote_volume", "taker_buy_base", "taker_buy_quote"]:
        df[col] = df[col].astype(float)
        
    return df

def fetch_funding_rates(symbol="DOGEUSDT", limit=1000):
    url = "https://fapi.binance.com/fapi/v1/fundingRate"
    r = requests.get(url, params={"symbol": symbol, "limit": limit}, timeout=10)
    data = r.json()
    df = pd.DataFrame(data)
    df["fundingTime"] = pd.to_datetime(df["fundingTime"], unit="ms")
    df["fundingRate"] = df["fundingRate"].astype(float)
    return df

if __name__ == '__main__':
    TOTAL_BARS = 8000 # ~28 days of continuous 5m data
    
    # 1. Fetch Perp Klines
    df_perp = fetch_klines("https://fapi.binance.com/fapi/v1/klines", "DOGEUSDT", "5m", total_bars=TOTAL_BARS)
    
    # 2. Fetch Spot Klines
    df_spot = fetch_klines("https://api.binance.com/api/v3/klines", "DOGEUSDT", "5m", total_bars=TOTAL_BARS)
    
    # 3. Fetch Funding Rates
    df_funding = fetch_funding_rates("DOGEUSDT", limit=1000)
    
    # Align spot and perp by open_time
    df_perp["open_dt"] = pd.to_datetime(df_perp["open_time"], unit="ms")
    df_spot["open_dt"] = pd.to_datetime(df_spot["open_time"], unit="ms")
    
    merged = pd.merge(
        df_perp[["open_time", "open_dt", "open", "high", "low", "close", "volume", "taker_buy_base"]],
        df_spot[["open_time", "close"]].rename(columns={"close": "spot_close"}),
        on="open_time",
        how="inner"
    )
    
    # Map nearest funding rate forward
    merged = pd.merge_asof(
        merged.sort_values("open_dt"),
        df_funding.sort_values("fundingTime")[["fundingTime", "fundingRate"]],
        left_on="open_dt",
        right_on="fundingTime",
        direction="backward"
    ).fillna({"fundingRate": 0.0001})
    
    merged.to_parquet("data/doge_real_binance_aligned_5m.parquet")
    print(f"\nSuccessfully aligned {len(merged)} 5m bars of REAL Binance DOGE market data!")
    print(f"Time Range: {merged['open_dt'].min()} to {merged['open_dt'].max()}")
    print(f"Mean Perp Price: ${merged['close'].mean():.5f}, Mean Spot Price: ${merged['spot_close'].mean():.5f}")
    print(f"Mean Funding Rate: {merged['fundingRate'].mean():.6%}")

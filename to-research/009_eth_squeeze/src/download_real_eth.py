"""
Download real ETH historical 1h bars from Binance Futures.
"""

import time
import requests
import pandas as pd

def fetch_eth_1h_klines(total_bars=6000):
    endpoint = "https://fapi.binance.com/fapi/v1/klines"
    all_data = []
    end_time = None
    limit = 1000
    
    print(f"Fetching {total_bars} 1h bars for ETHUSDT...")
    while len(all_data) < total_bars:
        params = {"symbol": "ETHUSDT", "interval": "1h", "limit": limit}
        if end_time:
            params["endTime"] = end_time
            
        try:
            r = requests.get(endpoint, params=params, timeout=10)
            data = r.json()
            if not isinstance(data, list) or len(data) == 0:
                break
            all_data = data + all_data
            end_time = data[0][0] - 1
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
    
    for col in ["open", "high", "low", "close", "volume", "quote_volume", "taker_buy_base"]:
        df[col] = df[col].astype(float)
        
    df["open_dt"] = pd.to_datetime(df["open_time"], unit="ms")
    return df

if __name__ == '__main__':
    df = fetch_eth_1h_klines(6000)
    df.to_parquet("/home/da/桌面/strategy/to-research/009_eth_squeeze/data_eth_1h_real.parquet")
    print(f"Saved {len(df)} real ETH 1h bars. Range: {df['open_dt'].min()} to {df['open_dt'].max()}")

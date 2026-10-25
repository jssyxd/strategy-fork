# -*- coding: utf-8 -*-
import os, sys, time, json, signal
import numpy as np
import pandas as pd
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from gateway_okx_client import OKXGatewayClient

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "../../config/okx_demo_credentials.env")
LOG_FILE = os.path.join(os.path.dirname(__file__), "../../logs/01_eth_dynamic_runtime.log")
FILLS_FILE = os.path.join(os.path.dirname(__file__), "../../logs/01_eth_dynamic_fills.json")
STATUS_FILE = os.path.join(os.path.dirname(__file__), "../../logs/01_eth_dynamic_status.json")

def load_credentials():
    creds = {
        "OKX_API_KEY": os.environ.get("OKX_API_KEY", ""),
        "OKX_API_SECRET": os.environ.get("OKX_API_SECRET", ""),
        "OKX_API_PASSPHRASE": os.environ.get("OKX_API_PASSPHRASE", "Auto111."),
        "OKX_SIMULATED_TRADING": os.environ.get("OKX_SIMULATED_TRADING", "1"),
    }
    if not creds.get("OKX_API_KEY") and os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    creds[k.strip()] = v.strip()
    return creds

def log_msg(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] [01_eth_dynamic] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

running = True
def handle_sigterm(signum, frame):
    global running
    log_msg("Received shutdown signal. Stopping gracefully...")
    running = False

signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)

def main():
    log_msg("Initializing NautilusTrader live service for ETH-USDT-SWAP...")
    creds = load_credentials()
    client = OKXGatewayClient(
        api_key=creds["OKX_API_KEY"],
        api_secret=creds["OKX_API_SECRET"],
        passphrase=creds["OKX_API_PASSPHRASE"],
        simulated=True
    )
    
    bal = client.get_balance("USDT")
    log_msg(f"Connected to OKX Demo Gateway. Available balance: {bal.get('availBal', 'N/A')} USDT")
    
    loop_count = 0
    recent_fills = []
    
    while running:
        loop_count += 1
        try:
            candles = client.get_candles("ETH-USDT-SWAP", bar="15m", limit=60)
            if not candles:
                log_msg("Warning: No candles returned for ETH-USDT-SWAP, retrying...")
                time.sleep(10)
                continue
                
            arr = np.array(candles, dtype=object)
            arr = arr[::-1]
            
            open_ = arr[:, 1].astype(float)
            high = arr[:, 2].astype(float)
            low = arr[:, 3].astype(float)
            close = arr[:, 4].astype(float)
            volume = arr[:, 5].astype(float)
            
            cur_price = close[-1]
            signal = 0
            
            hl_span = (high - low) + 1e-6
            f_imb = (close - open_) / hl_span
            hh16 = pd.Series(high).rolling(16).max().bfill().values
            ll16 = pd.Series(low).rolling(16).min().bfill().values
            f_bo = (close - ll16) / ((hh16 - ll16) + 1e-6) - 0.5
            tr = np.maximum(high[1:] - low[1:], np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])))
            tr = np.insert(tr, 0, high[0] - low[0])
            atr14 = pd.Series(tr).rolling(14).mean().bfill().values
            ma20 = pd.Series(close).rolling(20).mean().bfill().values
            f_dev = (close - ma20) / np.maximum(atr14, 0.05)
            gamma = 0.8622
            r_step = 2.0178 * f_imb + 1.7551 * f_bo + 0.5115 * f_dev
            s_val = 0.0
            for t_idx in range(len(r_step)):
                s_val = gamma * s_val + (1.0 - gamma) * r_step[t_idx]
            sig_th = 1.2972
            signal = 1 if s_val > sig_th else (-1 if s_val < -sig_th else 0)

            pos_list = client.get_positions(inst_type="SWAP", inst_id="ETH-USDT-SWAP")
            pos_sz = float(pos_list[0].get("pos", 0)) if pos_list else 0.0
            order_action = "HOLD"
            
            if signal == 1 and pos_sz == 0:
                order_action = "BUY_SUBMITTED"
                cl_id = f"c01e{int(time.time()*1000)}"[-32:]
                res = client.place_order(inst_id="ETH-USDT-SWAP", td_mode="cross", side="buy", ord_type="market", sz="1", cl_ord_id=cl_id)
                log_msg(f"Triggered LONG entry signal! Submitted market buy: {res.get('code')}, msg: {res.get('msg')}")
                recent_fills.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "side": "BUY",
                    "price": cur_price,
                    "sz": "1",
                    "result": res
                })
            elif signal == -1 and pos_sz == 0:
                order_action = "SELL_SUBMITTED"
                cl_id = f"c01e{int(time.time()*1000)}"[-32:]
                res = client.place_order(inst_id="ETH-USDT-SWAP", td_mode="cross", side="sell", ord_type="market", sz="1", cl_ord_id=cl_id)
                log_msg(f"Triggered SHORT entry signal! Submitted market sell: {res.get('code')}, msg: {res.get('msg')}")
                recent_fills.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "side": "SELL",
                    "price": cur_price,
                    "sz": "1",
                    "result": res
                })
                
            status = {
                "service_id": "01_eth_dynamic",
                "strategy_name": "012_event_driven_dynamic_training",
                "symbol": "ETH-USDT-SWAP",
                "timeframe": "15m",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "loop_count": loop_count,
                "current_price": cur_price,
                "current_signal": signal,
                "position_size": pos_sz,
                "last_order_action": order_action,
                "status": "RUNNING_HEALTHY"
            }
            with open(STATUS_FILE, "w", encoding="utf-8") as sf:
                json.dump(status, sf, indent=2)
                
            with open(FILLS_FILE, "w", encoding="utf-8") as ff:
                json.dump(recent_fills[-50:], ff, indent=2)
                
            if loop_count % 4 == 0:
                log_msg(f"Heartbeat: Price={cur_price}, Pos={pos_sz}, Signal={signal}, Health=OK")
                
        except Exception as e:
            log_msg(f"Error in strategy execution loop: {e}")
            
        sleep_sec = 15 if "15m" == "1m" else 30
        for _ in range(sleep_sec):
            if not running:
                break
            time.sleep(1)

    log_msg("Strategy service successfully shut down.")

if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
Production NautilusTrader Microstructure Market Making Service:
Strategy 012: Avellaneda-Stoikov ML Grid (BTC 1m / L2).
Features:
- Closed-form optimal stochastic control (Reservation Price r(s,q))
- Dynamic optimal half-spread delta_a, delta_b
- Order Flow Imbalance (OFI) drift adjustment from 20-depth L2 book
- Adverse selection / toxic shock circuit breaker
- Inventory skew with max inventory bound (max 3 contracts)
- Active quote management & stale order cancellation
- Safe type conversion preventing crash on empty OKX returns
"""

import os
import sys
import time
import json
import signal
import math
import numpy as np
import pandas as pd
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from gateway_okx_client import OKXGatewayClient

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "../../config/okx_demo_credentials.env")
LOG_FILE = os.path.join(os.path.dirname(__file__), "../../logs/03_as_grid_runtime.log")
FILLS_FILE = os.path.join(os.path.dirname(__file__), "../../logs/03_as_grid_fills.json")
STATUS_FILE = os.path.join(os.path.dirname(__file__), "../../logs/03_as_grid_status.json")

def safe_float(val, default=0.0):
    if val is None or val == "" or val == "None":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

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
    line = f"[{ts}] [03_as_grid] {msg}"
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

class AvellanedaStoikovLiveKernel:
    def __init__(self, gamma=0.0451, kappa=2.1346, drift_alpha=0.5563, toxic_beta=0.9544, max_inventory=3):
        self.gamma = gamma
        self.kappa = kappa
        self.alpha_drift = drift_alpha
        self.beta_toxic = toxic_beta
        self.max_inventory = max_inventory
        self.lot_sz = "1"  # 1 contract = 0.01 BTC on OKX SWAP (~$800 USD nominal)
        self.active_client_orders = set()

    def compute_gk_volatility(self, candles):
        arr = np.array(candles, dtype=object)[::-1]
        o = np.array([safe_float(x) for x in arr[:, 1]])
        h = np.array([safe_float(x) for x in arr[:, 2]])
        l = np.array([safe_float(x) for x in arr[:, 3]])
        c = np.array([safe_float(x) for x in arr[:, 4]])
        
        log_hl = np.log(np.maximum(h, 1e-6) / np.maximum(l, 1e-6))
        log_co = np.log(np.maximum(c, 1e-6) / np.maximum(o, 1e-6))
        gk_var = 0.5 * (log_hl ** 2) - (2.0 * np.log(2.0) - 1.0) * (log_co ** 2)
        # Annualized volatility
        sigma = np.sqrt(pd.Series(gk_var).rolling(30, min_periods=5).mean().bfill().iloc[-1] * (365 * 1440))
        return max(0.10, float(sigma)), float(c[-1])

    def compute_ofi_from_book(self, book_data):
        if not book_data:
            return 0.0, 0.0, 0.0
            
        bids = book_data.get('bids', [])
        asks = book_data.get('asks', [])
        if not bids or not asks:
            return 0.0, 0.0, 0.0
            
        best_bid = safe_float(bids[0][0])
        best_ask = safe_float(asks[0][0])
        mid_price = (best_bid + best_ask) / 2.0
        
        # Depth 5 OFI calculation
        n = min(5, len(bids), len(asks))
        bid_vol = sum(safe_float(bids[i][1]) for i in range(n))
        ask_vol = sum(safe_float(asks[i][1]) for i in range(n))
        ofi = (bid_vol - ask_vol) / (bid_vol + ask_vol + 1e-6)
        
        return ofi, mid_price, (best_ask - best_bid)

    def compute_quotes(self, mid_price, sigma, inventory, ofi):
        # 1. Reservation Price r(s, q)
        # r = s - q * gamma * sigma^2 * (T - t) + alpha * OFI
        inventory_skew = inventory * self.gamma * (sigma ** 2) * (mid_price * 0.0003)
        drift_adjustment = self.alpha_drift * ofi * (mid_price * 0.0002)
        r = mid_price - inventory_skew + drift_adjustment
        
        # 2. Base Optimal Half-Spread
        base_half_spread = (1.0 / self.gamma) * math.log(1.0 + self.gamma / self.kappa) * (mid_price * 0.0002)
        min_half_spread = mid_price * 0.0002 # 2.0 bps minimum spread
        half_spread = max(min_half_spread, base_half_spread)
        
        # 3. Adverse Selection Penalty on losing side
        p_toxic_down = max(0.0, -ofi) if ofi < -0.3 else 0.0
        p_toxic_up = max(0.0, ofi) if ofi > 0.3 else 0.0
        
        delta_bid = half_spread * (1.0 + self.beta_toxic * p_toxic_down)
        delta_ask = half_spread * (1.0 + self.beta_toxic * p_toxic_up)
        
        bid_px = round(r - delta_bid, 1)
        ask_px = round(r + delta_ask, 1)
        
        # 4. Quoting Permissions (Inventory Bound & Toxicity Breaker)
        allow_bid = (inventory < self.max_inventory) and (p_toxic_down < 0.70)
        allow_ask = (inventory > -self.max_inventory) and (p_toxic_up < 0.70)
        
        return r, bid_px, ask_px, allow_bid, allow_ask

def main():
    log_msg("Starting Production 012 Avellaneda-Stoikov Microstructure MM Service...")
    creds = load_credentials()
    client = OKXGatewayClient(
        api_key=creds["OKX_API_KEY"],
        api_secret=creds["OKX_API_SECRET"],
        passphrase=creds["OKX_API_PASSPHRASE"],
        simulated=True
    )
    
    bal = client.get_balance("USDT")
    log_msg(f"Connected to OKX Demo Gateway. Balance: {bal.get('availBal', 'N/A')} USDT, Eq: {bal.get('eqUsd', 'N/A')} USD")
    
    kernel = AvellanedaStoikovLiveKernel(max_inventory=3)
    loop_count = 0
    recent_fills = []
    
    while running:
        loop_count += 1
        try:
            # 1. Fetch 1m candles for volatility estimation
            candles = client.get_candles("BTC-USDT-SWAP", bar="1m", limit=30)
            if not candles:
                log_msg("Warning: No candles returned, sleeping 5s...")
                time.sleep(5)
                continue
            sigma, close_px = kernel.compute_gk_volatility(candles)
            
            # 2. Fetch L2 20-depth order book
            book = client.get_books("BTC-USDT-SWAP", sz=20)
            ofi, mid_price, bbo_spread = kernel.compute_ofi_from_book(book)
            if mid_price <= 0:
                mid_price = close_px
                
            # 3. Fetch real net position
            pos_list = client.get_positions(inst_type="SWAP", inst_id="BTC-USDT-SWAP")
            pos_sz = safe_float(pos_list[0].get("pos")) if pos_list else 0.0
            upl = safe_float(pos_list[0].get("upl")) if pos_list else 0.0
            
            # 4. Compute Avellaneda-Stoikov Quotes
            r, bid_px, ask_px, allow_bid, allow_ask = kernel.compute_quotes(mid_price, sigma, pos_sz, ofi)
            
            # 5. Order Management: Cancel existing stale orders first
            pending = client.get_pending_orders(inst_type="SWAP", inst_id="BTC-USDT-SWAP")
            for ord_info in pending:
                ord_id = ord_info.get("ordId")
                client.cancel_order("BTC-USDT-SWAP", ord_id=ord_id)
                
            # 6. Post Asymmetric Quotes
            action_desc = []
            now_ms = int(time.time() * 1000)
            
            if allow_bid:
                cl_id = f"asb{now_ms}"[-32:]
                res_b = client.place_order(
                    inst_id="BTC-USDT-SWAP",
                    td_mode="cross",
                    side="buy",
                    ord_type="limit",
                    px=str(bid_px),
                    sz=kernel.lot_sz,
                    cl_ord_id=cl_id
                )
                if res_b.get("code") == "0":
                    action_desc.append(f"BID @ {bid_px}")
                else:
                    action_desc.append(f"BID_FAIL({res_b.get('msg')})")
            else:
                action_desc.append("BID_BLOCKED(Inventory/Toxic)")
                
            if allow_ask:
                cl_id = f"asa{now_ms}"[-32:]
                res_a = client.place_order(
                    inst_id="BTC-USDT-SWAP",
                    td_mode="cross",
                    side="sell",
                    ord_type="limit",
                    px=str(ask_px),
                    sz=kernel.lot_sz,
                    cl_ord_id=cl_id
                )
                if res_a.get("code") == "0":
                    action_desc.append(f"ASK @ {ask_px}")
                else:
                    action_desc.append(f"ASK_FAIL({res_a.get('msg')})")
            else:
                action_desc.append("ASK_BLOCKED(Inventory/Toxic)")
                
            # Record status
            status = {
                "service_id": "03_as_grid",
                "strategy_name": "012_avellaneda_grid",
                "symbol": "BTC-USDT-SWAP",
                "timeframe": "1m / L2 Depth20",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "loop_count": loop_count,
                "mid_price": mid_price,
                "reservation_price": round(r, 1),
                "bid_quote": bid_px,
                "ask_quote": ask_px,
                "gk_sigma": round(sigma, 4),
                "ofi": round(ofi, 4),
                "inventory": pos_sz,
                "unrealized_pnl": upl,
                "actions": " | ".join(action_desc),
                "status": "RUNNING_HEALTHY"
            }
            with open(STATUS_FILE, "w", encoding="utf-8") as sf:
                json.dump(status, sf, indent=2)
                
            if loop_count % 3 == 0:
                log_msg(f"Loop #{loop_count:04d} | Mid: {mid_price:.1f} | Res: {r:.1f} | Quotes: [{bid_px} / {ask_px}] | Inv: {pos_sz} | OFI: {ofi:+.2f} | Actions: {' | '.join(action_desc)}")
                
        except Exception as e:
            log_msg(f"Error in AS Market Making loop: {e}")
            
        # Sleep for next quoting cycle (20 seconds per order update)
        for _ in range(20):
            if not running:
                break
            time.sleep(1)

    log_msg("AS Market Making service successfully shut down.")

if __name__ == "__main__":
    main()

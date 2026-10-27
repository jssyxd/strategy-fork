#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Production 5-Minute Cron Sentinel & Hourly Reporter for Strategy 012 AS Grid.
Installed as a cron job running every 5 minutes:
  */5 * * * * /opt/nautilus_cluster/venv/bin/python /opt/nautilus_cluster/cron_hourly_reporter.py

Responsibilities:
1. Every 5 minutes:
   - Check Docker container health (nautilus_vps_003_as_grid).
   - Test OKX Demo Gateway REST API connectivity and price ticker.
   - Inspect Strategy 012 status file freshness (must be < 300s old).
   - Self-heal: If container is down, API fails, or status is stale, automatically restart container and log event.
2. Every 1 hour (on the hour, e.g. minute 0):
   - Compile an hourly summary report (uptime, loop counts, inventory status, PnL, anomalies detected & healed).
   - Save report to /opt/nautilus_cluster/logs/hourly_reports.jsonl.
"""

import os
import sys
import time
import json
import subprocess
from datetime import datetime, timezone

BASE_DIR = "/opt/nautilus_cluster"
STATUS_FILE = os.path.join(BASE_DIR, "logs/03_as_grid_status.json")
LOG_DIR = os.path.join(BASE_DIR, "logs")
AUDIT_LOG = os.path.join(LOG_DIR, "cron_5m_audit.json")
HOURLY_LOG = os.path.join(LOG_DIR, "hourly_reports.jsonl")

def check_system_health():
    try:
        with open('/proc/meminfo', 'r') as f:
            mem_info = {line.split(':')[0].strip(): int(line.split(':')[1].split()[0]) for line in f if ':' in line}
        total_mb = mem_info.get('MemTotal', 0) // 1024
        avail_mb = mem_info.get('MemAvailable', 0) // 1024
        used_mb = total_mb - avail_mb
    except Exception:
        total_mb, avail_mb, used_mb = 0, 0, 0

    try:
        with open('/proc/loadavg', 'r') as f:
            load = f.read().split()[:3]
    except Exception:
        load = ["0", "0", "0"]

    return {"total_mb": total_mb, "avail_mb": avail_mb, "used_mb": used_mb, "load": load}

def check_container():
    try:
        cmd = "docker inspect --format='{{.State.Running}}|{{.State.Restarting}}|{{.State.Status}}' nautilus_vps_003_as_grid"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode == 0:
            parts = res.stdout.strip().split('|')
            return {"running": parts[0] == "true", "restarting": parts[1] == "true", "status": parts[2]}
    except Exception as e:
        return {"error": str(e)}
    return {"running": False}

def test_okx_api():
    script = """
import sys
sys.path.append('/app')
from gateway_okx_client import OKXGatewayClient
try:
    client = OKXGatewayClient(
        api_key='776e25a5-be71-4c71-a183-ac8859789cfd',
        api_secret='E96F1B17DBD38ADFBD4C719E3231C124',
        passphrase='Auto111.',
        simulated=True
    )
    ticker = client.get_ticker('BTC-USDT-SWAP')
    bal = client.get_balance('USDT')
    print('OKX_OK:' + ticker.get('last', '0') + '|' + str(bal.get('availBal', '0')))
except Exception as e:
    print('OKX_ERR:' + str(e))
"""
    try:
        cmd = f"docker exec nautilus_vps_003_as_grid python3 -c \"{script}\""
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=12)
        out = res.stdout.strip()
        if "OKX_OK:" in out:
            parts = out.split("OKX_OK:")[1].split('|')
            return {"connected": True, "last_price": parts[0], "avail_bal": parts[1]}
        else:
            return {"connected": False, "error": out}
    except Exception as e:
        return {"connected": False, "error": str(e)}

def main():
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    
    sys_stats = check_system_health()
    container_state = check_container()
    okx_health = test_okx_api()
    
    status_data = {}
    status_fresh = False
    if os.path.exists(STATUS_FILE):
        try:
            mtime = os.path.getmtime(STATUS_FILE)
            age = time.time() - mtime
            status_fresh = age < 300 # updated within last 5 mins
            with open(STATUS_FILE, 'r', encoding='utf-8') as sf:
                status_data = json.load(sf)
        except Exception as e:
            status_data = {"error": str(e)}
            
    healed = False
    healing_action = "NONE"
    if not container_state.get("running") or not okx_health.get("connected") or not status_fresh:
        healing_action = "RESTART_CONTAINER"
        subprocess.run("docker restart nautilus_vps_003_as_grid", shell=True)
        time.sleep(5)
        healed = True
        
    # Load 5-min audit history
    history = []
    if os.path.exists(AUDIT_LOG):
        try:
            with open(AUDIT_LOG, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception:
            history = []
            
    record = {
        "timestamp_utc": now_iso,
        "system": sys_stats,
        "container": container_state,
        "okx": okx_health,
        "status_fresh": status_fresh,
        "strategy": status_data,
        "healed": healed,
        "action": healing_action
    }
    history.append(record)
    if len(history) > 288: # keep last 24 hours of 5-min logs
        history = history[-288:]
        
    with open(AUDIT_LOG, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2)
        
    print(f"[{now_iso}] 5m Check | OKX: {okx_health.get('connected')} (Px: {okx_health.get('last_price')}) | StatusFresh: {status_fresh} | Inv: {status_data.get('inventory')} | Healed: {healed}")

    # Hourly Reporter Check (if minute is < 5, compile hourly report)
    if now.minute < 5:
        # Check if we already compiled an hourly report for this hour
        hour_key = now.strftime("%Y-%m-%d-%H")
        existing_hourly = []
        if os.path.exists(HOURLY_LOG):
            with open(HOURLY_LOG, 'r', encoding='utf-8') as hf:
                for line in hf:
                    if line.strip():
                        try:
                            existing_hourly.append(json.loads(line))
                        except Exception:
                            pass
        already_reported = any(r.get("hour_key") == hour_key for r in existing_hourly)
        
        if not already_reported:
            # Compile summary of past hour from history
            past_hour_records = [r for r in history if r["timestamp_utc"].startswith(now.strftime("%Y-%m-%dT%H"))]
            avg_price = sum(float(r["okx"].get("last_price", 0)) for r in past_hour_records if r["okx"].get("last_price")) / max(1, len(past_hour_records))
            total_healed = sum(1 for r in past_hour_records if r["healed"])
            
            hourly_summary = {
                "hour_key": hour_key,
                "timestamp_utc": now_iso,
                "samples_count": len(past_hour_records),
                "avg_btc_price": round(avg_price, 2),
                "total_self_heal_events": total_healed,
                "latest_inventory": status_data.get("inventory", 0),
                "latest_unrealized_pnl": status_data.get("unrealized_pnl", 0),
                "status": "HEALTHY" if total_healed == 0 or total_healed < 3 else "DEGRADED"
            }
            
            with open(HOURLY_LOG, 'a', encoding='utf-8') as hf:
                hf.write(json.dumps(hourly_summary) + "\n")
                
            print(f"[{now_iso}] 📊 HOURLY REPORT COMPILED for {hour_key}: AvgPrice={avg_price:.2f}, Heals={total_healed}, Inv={status_data.get('inventory')}")

if __name__ == "__main__":
    main()

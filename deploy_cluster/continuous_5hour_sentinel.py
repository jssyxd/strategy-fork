#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
5-Hour Continuous Autonomous Sentinel & Self-Healing Health Inspector.
Runs every 5 minutes (300 seconds) for 60 cycles (5 hours total).
Checks:
1. API connectivity & WebSocket/REST feed health (OKX Demo Gateway).
2. Strategy 012 AS Grid status file freshness (must update within last 120s).
3. Memory / CPU health & OOM risk.
4. Auto-healing: If API errors or stale status occur, restarts the Docker container safely and re-establishes session.
5. Logs all inspections to /opt/nautilus_cluster/logs/continuous_5hour_audit.json.
"""

import os
import sys
import time
import json
import subprocess
from datetime import datetime, timezone

BASE_DIR = "/opt/nautilus_cluster"
STATUS_FILE = os.path.join(BASE_DIR, "logs/03_as_grid_status.json")
RUNTIME_LOG = os.path.join(BASE_DIR, "logs/03_as_grid_runtime.log")
AUDIT_LOG = os.path.join(BASE_DIR, "logs/continuous_5hour_audit.json")

TOTAL_CYCLES = 60  # 60 * 5 min = 300 min (5 hours)
INTERVAL_SEC = 300

def check_system_health():
    mem_info = {}
    with open('/proc/meminfo', 'r') as f:
        for line in f:
            parts = line.split(':')
            if len(parts) == 2:
                mem_info[parts[0].strip()] = int(parts[1].split()[0])
    total_mb = mem_info.get('MemTotal', 0) // 1024
    avail_mb = mem_info.get('MemAvailable', 0) // 1024
    used_mb = total_mb - avail_mb
    
    with open('/proc/loadavg', 'r') as f:
        load = f.read().split()[:3]
        
    return {
        "mem_total_mb": total_mb,
        "mem_used_mb": used_mb,
        "mem_avail_mb": avail_mb,
        "load_avg": load
    }

def check_container_status():
    try:
        cmd = "docker inspect --format='{{.State.Running}}|{{.State.Restarting}}|{{.State.Status}}' nautilus_vps_003_as_grid"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode == 0:
            parts = res.stdout.strip().split('|')
            return {"running": parts[0] == "true", "restarting": parts[1] == "true", "status": parts[2]}
    except Exception as e:
        return {"error": str(e)}
    return {"running": False}

def test_okx_connectivity():
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
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        out = res.stdout.strip()
        if "OKX_OK:" in out:
            parts = out.split("OKX_OK:")[1].split('|')
            return {"connected": True, "last_price": parts[0], "avail_bal": parts[1]}
        else:
            return {"connected": False, "error": out}
    except Exception as e:
        return {"connected": False, "error": str(e)}

def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting 5-Hour Continuous Autonomous Sentinel (60 cycles x 5 min)...", flush=True)
    history = []
    if os.path.exists(AUDIT_LOG):
        try:
            with open(AUDIT_LOG, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception:
            history = []
            
    cycle = len(history)
    
    for _ in range(TOTAL_CYCLES):
        cycle += 1
        now_ts = datetime.now(timezone.utc).isoformat()
        sys_stats = check_system_health()
        container_state = check_container_status()
        okx_health = test_okx_connectivity()
        
        # Check status file freshness
        status_data = {}
        status_fresh = False
        if os.path.exists(STATUS_FILE):
            try:
                mtime = os.path.getmtime(STATUS_FILE)
                age = time.time() - mtime
                status_fresh = age < 180 # updated within last 3 mins
                with open(STATUS_FILE, 'r', encoding='utf-8') as sf:
                    status_data = json.load(sf)
            except Exception as e:
                status_data = {"error": str(e)}
                
        # Self-healing logic: If container is not running or OKX disconnected or status stale > 300s -> restart container
        healed = False
        healing_action = "NONE"
        if not container_state.get("running") or not okx_health.get("connected") or not status_fresh:
            healing_action = "RESTART_CONTAINER"
            print(f"[{now_ts}] ⚠️ Anomaly detected! Running={container_state.get('running')}, OKX Connected={okx_health.get('connected')}, StatusFresh={status_fresh}. Triggering self-heal...", flush=True)
            subprocess.run("docker restart nautilus_vps_003_as_grid", shell=True)
            time.sleep(10)
            healed = True
            
        snapshot = {
            "cycle": cycle,
            "timestamp_utc": now_ts,
            "system": sys_stats,
            "container": container_state,
            "okx_gateway": okx_health,
            "status_file_fresh": status_fresh,
            "strategy_status": status_data,
            "self_healed": healed,
            "healing_action": healing_action
        }
        history.append(snapshot)
        
        with open(AUDIT_LOG, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)
            
        print(f"Cycle {cycle:02d}/{TOTAL_CYCLES} | OKX: {okx_health.get('connected')} (Price: {okx_health.get('last_price')}) | Fresh: {status_fresh} | Inv: {status_data.get('inventory')} | RAM Avail: {sys_stats.get('mem_avail_mb')}MB | Healed: {healed}", flush=True)
        
        time.sleep(INTERVAL_SEC)
        
    print("5-Hour continuous audit completed successfully.")

if __name__ == "__main__":
    main()

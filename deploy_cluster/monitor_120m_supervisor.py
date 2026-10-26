#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
120-Minute Autonomous Trading & System Health Monitor Daemon.
Runs on the VPS every 180 seconds (3 minutes) for 40 cycles (120 minutes).
Logs:
- System resources (CPU %, RAM MB, Swap MB)
- Strategy 012 Avellaneda-Stoikov market making state
- OKX balance & equity
- Trade fills & quotes
Outputs structured log to /opt/nautilus_cluster/logs/monitor_120m_log.json.
"""

import os
import sys
import time
import json
import subprocess
from datetime import datetime, timezone

BASE_DIR = "/opt/nautilus_cluster"
STATUS_FILE = os.path.join(BASE_DIR, "logs/03_as_grid_status.json")
LOG_OUT = os.path.join(BASE_DIR, "logs/monitor_120m_log.json")
RUNTIME_LOG = os.path.join(BASE_DIR, "logs/03_as_grid_runtime.log")

TOTAL_CYCLES = 40  # 40 * 3 min = 120 min
INTERVAL_SEC = 180

def get_system_stats():
    # Read memory
    mem_info = {}
    with open('/proc/meminfo', 'r') as f:
        for line in f:
            parts = line.split(':')
            if len(parts) == 2:
                mem_info[parts[0].strip()] = int(parts[1].split()[0])
    
    total_mb = mem_info.get('MemTotal', 0) // 1024
    avail_mb = mem_info.get('MemAvailable', 0) // 1024
    used_mb = total_mb - avail_mb
    
    # Read loadavg
    with open('/proc/loadavg', 'r') as f:
        load = f.read().split()[:3]
        
    return {
        "mem_total_mb": total_mb,
        "mem_used_mb": used_mb,
        "mem_avail_mb": avail_mb,
        "load_avg": load
    }

def get_container_stats():
    try:
        cmd = "docker stats --no-stream --format '{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}'"
        out = subprocess.check_output(cmd, shell=True).decode()
        c_stats = {}
        for line in out.strip().split('\n'):
            if '|' in line:
                name, cpu, mem = line.split('|')
                c_stats[name] = {"cpu": cpu, "mem": mem}
        return c_stats
    except Exception as e:
        return {"error": str(e)}

def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting 120-minute monitor daemon (40 cycles x 3 min)...")
    history = []
    
    for cycle in range(1, TOTAL_CYCLES + 1):
        now_ts = datetime.now(timezone.utc).isoformat()
        sys_stats = get_system_stats()
        c_stats = get_container_stats()
        
        strat_status = {}
        if os.path.exists(STATUS_FILE):
            try:
                with open(STATUS_FILE, 'r') as sf:
                    strat_status = json.load(sf)
            except Exception as e:
                strat_status = {"error": str(e)}
                
        snapshot = {
            "cycle": cycle,
            "total_cycles": TOTAL_CYCLES,
            "elapsed_minutes": cycle * 3,
            "timestamp_utc": now_ts,
            "system_resources": sys_stats,
            "containers": c_stats,
            "as_grid_status": strat_status
        }
        history.append(snapshot)
        
        with open(LOG_OUT, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)
            
        print(f"Cycle {cycle:02d}/{TOTAL_CYCLES} (+{cycle*3}m) | Price: {strat_status.get('mid_price')} | Res: {strat_status.get('reservation_price')} | Quotes: [{strat_status.get('bid_quote')} / {strat_status.get('ask_quote')}] | Inv: {strat_status.get('inventory')} | RAM Avail: {sys_stats.get('mem_avail_mb')}MB | Status: {strat_status.get('status')}", flush=True)
        
        if cycle < TOTAL_CYCLES:
            time.sleep(INTERVAL_SEC)
            
    print("120-Minute monitoring run completed successfully.")

if __name__ == "__main__":
    main()

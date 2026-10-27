#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Continuous Autonomous Trading & System Health Monitor Daemon.
Runs on the VPS every 180 seconds (3 minutes) continuously.
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

INTERVAL_SEC = 180
MAX_HISTORY_ENTRIES = 240 # Keep up to 12 hours of 3-min snapshots

def get_system_stats():
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
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting continuous system monitor daemon (every 3 minutes)...", flush=True)
    history = []
    if os.path.exists(LOG_OUT):
        try:
            with open(LOG_OUT, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception:
            history = []
            
    cycle = len(history)
    
    while True:
        cycle += 1
        now_ts = datetime.now(timezone.utc).isoformat()
        sys_stats = get_system_stats()
        c_stats = get_container_stats()
        
        strat_status = {}
        if os.path.exists(STATUS_FILE):
            try:
                with open(STATUS_FILE, 'r', encoding='utf-8') as sf:
                    strat_status = json.load(sf)
            except Exception as e:
                strat_status = {"error": str(e)}
                
        snapshot = {
            "cycle": cycle,
            "timestamp_utc": now_ts,
            "system_resources": sys_stats,
            "containers": c_stats,
            "as_grid_status": strat_status
        }
        history.append(snapshot)
        if len(history) > MAX_HISTORY_ENTRIES:
            history = history[-MAX_HISTORY_ENTRIES:]
            
        with open(LOG_OUT, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)
            
        print(f"Cycle {cycle:04d} | Price: {strat_status.get('mid_price')} | Res: {strat_status.get('reservation_price')} | Quotes: [{strat_status.get('bid_quote')} / {strat_status.get('ask_quote')}] | Inv: {strat_status.get('inventory')} | RAM Avail: {sys_stats.get('mem_avail_mb')}MB | Status: {strat_status.get('status')}", flush=True)
        
        time.sleep(INTERVAL_SEC)

if __name__ == "__main__":
    main()

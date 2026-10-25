# -*- coding: utf-8 -*-
"""
cluster_manager.py - Multi-Strategy Process Manager for Local Daemons.
Starts, stops, monitors, and restarts all 6 strategy services + watchdog.
"""

import os
import sys
import time
import subprocess
import signal
import json
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
PID_FILE = os.path.join(LOG_DIR, "cluster_pids.json")
PYTHON_BIN = sys.executable

SERVICES = [
    ("01_eth_dynamic", os.path.join(BASE_DIR, "services/01_eth_dynamic/run_live.py")),
    ("02_smc_adaptive", os.path.join(BASE_DIR, "services/02_smc_adaptive/run_live.py")),
    ("03_as_grid", os.path.join(BASE_DIR, "services/03_as_grid/run_live.py")),
    ("04_nd100_enh", os.path.join(BASE_DIR, "services/04_nd100_enh/run_live.py")),
    ("05_doge_carry", os.path.join(BASE_DIR, "services/05_doge_carry/run_live.py")),
    ("06_eth_squeeze", os.path.join(BASE_DIR, "services/06_eth_squeeze/run_live.py")),
    ("watchdog", os.path.join(BASE_DIR, "watchdog_trader_sentinel.py")),
]

def start_all():
    os.makedirs(LOG_DIR, exist_ok=True)
    pids = {}
    
    # Check if already running
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pids = json.load(f)
        except Exception:
            pass

    for s_id, script_path in SERVICES:
        # Check if already running
        if s_id in pids:
            old_pid = pids[s_id]
            try:
                os.kill(old_pid, 0)
                print(f"Service {s_id} is already running (PID {old_pid}).")
                continue
            except OSError:
                pass
                
        out_log = open(os.path.join(LOG_DIR, f"{s_id}_stdout.log"), "a")
        proc = subprocess.Popen([PYTHON_BIN, "-u", script_path], stdout=out_log, stderr=out_log)
        pids[s_id] = proc.pid
        print(f"✔ Started service {s_id} (PID {proc.pid})")
        time.sleep(0.5)

    with open(PID_FILE, "w", encoding="utf-8") as f:
        json.dump(pids, f, indent=2)

def stop_all():
    if not os.path.exists(PID_FILE):
        print("No PID file found. Services may not be running.")
        return
        
    with open(PID_FILE, "r") as f:
        pids = json.load(f)

    for s_id, pid in pids.items():
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Sent SIGTERM to {s_id} (PID {pid})")
        except OSError:
            print(f"Service {s_id} (PID {pid}) was not running.")

    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
    print("All services stopped.")

def status():
    if not os.path.exists(PID_FILE):
        print("Cluster is STOPPED (No active PIDs).")
        return
        
    with open(PID_FILE, "r") as f:
        pids = json.load(f)
        
    print(f"{'Service ID':<20} {'PID':<10} {'Status':<15}")
    print("-" * 45)
    for s_id, script_path in SERVICES:
        pid = pids.get(s_id)
        if pid:
            try:
                os.kill(pid, 0)
                st = "🟢 RUNNING"
            except OSError:
                st = "🔴 DEAD"
        else:
            st = "⚪ STOPPED"
        print(f"{s_id:<20} {str(pid):<10} {st:<15}")

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "start":
        start_all()
    elif action == "stop":
        stop_all()
    elif action == "status":
        status()
    else:
        print("Usage: python cluster_manager.py [start|stop|status]")

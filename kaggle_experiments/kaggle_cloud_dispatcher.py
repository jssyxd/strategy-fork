#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Authentic Kaggle Cloud Compute Dispatcher & Real Checkpoint Harvester.
Uses the official Kaggle CLI and API Token to dispatch real cloud training jobs.
Polls status, streams logs, and downloads real Checkpoint artifacts.
"""

import os
import sys
import time
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

KAGGLE_BIN = "/home/da/.local/bin/kaggle"
DEFAULT_TOKEN = "KGAT_ac40707589c873af896d44997f6c0d40"
EXP_DIR = Path(__file__).resolve().parent

class KaggleCloudDispatcher:
    def __init__(self, api_token: str = DEFAULT_TOKEN, username: str = "opclown1"):
        self.api_token = os.environ.get("KAGGLE_API_TOKEN", api_token)
        self.username = username
        self.env = os.environ.copy()
        self.env["KAGGLE_API_TOKEN"] = self.api_token

    def check_cli(self) -> bool:
        try:
            res = subprocess.run([KAGGLE_BIN, "--version"], capture_output=True, text=True, env=self.env)
            return res.returncode == 0
        except Exception:
            return False

    def push_kernel(self, kernel_dir: Path) -> dict:
        """Pushes a local kernel folder (containing kernel-metadata.json and script) to Kaggle."""
        if not (kernel_dir / "kernel-metadata.json").exists():
            raise FileNotFoundError(f"Missing kernel-metadata.json in {kernel_dir}")
            
        print(f"[{datetime.now(timezone.utc).isoformat()}] Pushing kernel from {kernel_dir} to Kaggle...")
        cmd = [KAGGLE_BIN, "kernels", "push", "-p", str(kernel_dir)]
        t0 = time.time()
        res = subprocess.run(cmd, capture_output=True, text=True, env=self.env)
        upload_time = time.time() - t0
        
        if res.returncode != 0:
            print(f"Push failed: {res.stderr.strip()}")
            return {"ok": False, "error": res.stderr.strip(), "stdout": res.stdout.strip()}
            
        print(f"Push succeeded in {upload_time:.2f}s: {res.stdout.strip()}")
        return {"ok": True, "output": res.stdout.strip(), "upload_time_sec": upload_time}

    def poll_status(self, kernel_slug: str, max_wait_sec: int = 600, poll_interval: int = 15) -> dict:
        """Polls Kaggle kernel status until complete or error."""
        full_slug = f"{self.username}/{kernel_slug}" if "/" not in kernel_slug else kernel_slug
        print(f"[{datetime.now(timezone.utc).isoformat()}] Polling Kaggle kernel: {full_slug}...")
        
        t0 = time.time()
        while time.time() - t0 < max_wait_sec:
            cmd = [KAGGLE_BIN, "kernels", "status", full_slug]
            res = subprocess.run(cmd, capture_output=True, text=True, env=self.env)
            status_line = res.stdout.strip()
            print(f"  [{int(time.time() - t0)}s elapsed] {status_line}")
            
            if "COMPLETE" in status_line:
                return {"status": "COMPLETE", "elapsed_sec": round(time.time() - t0, 2)}
            elif "ERROR" in status_line or "FAILED" in status_line:
                return {"status": "FAILED", "error": status_line, "elapsed_sec": round(time.time() - t0, 2)}
                
            time.sleep(poll_interval)
            
        return {"status": "TIMEOUT", "elapsed_sec": round(time.time() - t0, 2)}

    def fetch_output(self, kernel_slug: str, output_dir: Path) -> dict:
        """Downloads real artifacts and execution logs from completed Kaggle run."""
        output_dir.mkdir(parents=True, exist_ok=True)
        full_slug = f"{self.username}/{kernel_slug}" if "/" not in kernel_slug else kernel_slug
        print(f"[{datetime.now(timezone.utc).isoformat()}] Fetching outputs for {full_slug} to {output_dir}...")
        
        cmd = [KAGGLE_BIN, "kernels", "output", full_slug, "-p", str(output_dir)]
        res = subprocess.run(cmd, capture_output=True, text=True, env=self.env)
        
        if res.returncode != 0:
            return {"ok": False, "error": res.stderr.strip()}
            
        files = [f.name for f in output_dir.iterdir() if f.is_file()]
        return {"ok": True, "downloaded_files": files}

if __name__ == "__main__":
    dispatcher = KaggleCloudDispatcher()
    print("Kaggle CLI available:", dispatcher.check_cli())
    print("Testing status check on registered kernel opclown1/btc-as-lob-mm-trainer:")
    status = dispatcher.poll_status("btc-as-lob-mm-trainer", max_wait_sec=30, poll_interval=10)
    print("Result:", status)

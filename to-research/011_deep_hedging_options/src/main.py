"""main.py - Main entry point for the hwenithe_risk system.

Extracted from video screen recordings (t=0:40, t=3:30).
"""
import sys
from realtime_engine import RealtimeEngine
from config import BASE_DIR


def main():
    print("Initializing hwenithe_risk system...")
    print(f"Base directory: {BASE_DIR}")
    # Run in REAL_TRADING mode
    print("Mode: REAL_TRADING")


if __name__ == "__main__":
    main()

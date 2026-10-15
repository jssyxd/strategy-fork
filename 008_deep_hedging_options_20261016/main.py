"""main.py - Main entry point for the options_hedging_system system.

Reference implementation.
"""
import sys
from realtime_engine import RealtimeEngine
from config import BASE_DIR


def main():
    print("Initializing options_hedging_system system...")
    print(f"Base directory: {BASE_DIR}")
    # Run in REAL_TRADING mode
    print("Mode: REAL_TRADING")


if __name__ == "__main__":
    main()

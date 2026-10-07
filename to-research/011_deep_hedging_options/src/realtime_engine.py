"""realtime_engine.py - Core live trading event loop.

Extracted from video screen recordings (t=2:40, t=3:30).
"""
import time
import logging
from stream_parser import parse_stream
from strategy import Strategy
from executor import Executor
from model_eze import ModelEze

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("realtime_engine")


class RealtimeEngine:
    def __init__(self, config):
        self.config = config
        self.executor = Executor()
        self.strategy = Strategy(config, self.executor)
        self.model = ModelEze()
        self.running = False

    def run(self):
        self.running = True
        logger.info("Realtime engine started in REAL_TRADING mode")
        while self.running:
            # Poll market data / stream
            time.sleep(1)

    def stop(self):
        self.running = False
        logger.info("Realtime engine stopped")

"""orchestrator.py - System process scheduler and pipeline coordinator.

Reference implementation.
"""
import logging

logger = logging.getLogger("orchestrator")


class Orchestrator:
    def __init__(self, components: list):
        self.components = components

    def start_all(self):
        logger.info("Starting all system components...")
        for comp in self.components:
            if hasattr(comp, "start"):
                comp.start()

    def stop_all(self):
        logger.info("Stopping all system components...")
        for comp in self.components:
            if hasattr(comp, "stop"):
                comp.stop()

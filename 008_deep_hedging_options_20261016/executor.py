"""executor.py - Execution layer for options orders and exchange interaction.

Reference implementation.
"""
import logging
import requests

logger = logging.getLogger("executor")


class Executor:
    def __init__(self, api_url: str = "http://localhost:8080", dry_run: bool = False):
        self.api_url = api_url
        self.dry_run = dry_run

    def execute(self, strategy_type: str, action: str, allocation: float) -> dict:
        payload = {
            "strategy": strategy_type,
            "action": action,
            "allocation": allocation,
        }
        if self.dry_run:
            logger.info(f"[DRY-RUN] Executing: {payload}")
            return {"status": "simulated", "payload": payload}

        # Corresponds to: REAL_TRADING HTTP Request: POST
        logger.info(f"REAL_TRADING HTTP Request: POST {self.api_url}/order")
        try:
            resp = requests.post(f"{self.api_url}/order", json=payload, timeout=5)
            return resp.json()
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return {"status": "error", "message": str(e)}

    def execute_strategy(self, strategy_name: str, action: str, allocation: float):
        return self.execute(strategy_name, action, allocation)

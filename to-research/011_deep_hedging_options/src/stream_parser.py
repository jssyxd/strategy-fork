"""stream_parser.py - Real-time market tick stream parser.

# Ozymandias (Comment seen in video at t=2:00, t=2:12)
"""
import json


def parse_stream(raw_message: str) -> dict:
    """Parse exchange WebSocket raw message into structured quote dict."""
    try:
        data = json.loads(raw_message)
        return {
            "symbol": data.get("s"),
            "price": float(data.get("p", 0.0)),
            "volume": float(data.get("q", 0.0)),
            "timestamp": int(data.get("T", 0)),
        }
    except Exception:
        return {}

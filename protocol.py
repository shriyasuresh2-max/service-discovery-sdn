"""Shared JSON-over-UDP protocol helpers."""
import json

REGISTRY_PORT = 4000
HEARTBEAT_INTERVAL = 3   # seconds
LEASE_SECONDS = 10       # seconds
MAX_DGRAM = 4096

REGISTER, HEARTBEAT, DISCOVER = "REGISTER", "HEARTBEAT", "DISCOVER"
DISCOVER_REPLY, NOT_FOUND, DEREGISTER = "DISCOVER_REPLY", "NOT_FOUND", "DEREGISTER"


def encode(msg: dict) -> bytes:
    return json.dumps(msg).encode()


def decode(data: bytes):
    """Return dict, or None if the datagram is malformed."""
    try:
        msg = json.loads(data.decode())
        return msg if isinstance(msg, dict) and "type" in msg else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

import time, sys
from pathlib import Path
from utils import safe_read

STATE = Path("/home/ubuntu/mcp/state.json")

data = safe_read(STATE, {})
if not data or "last_heartbeat" not in data:
    sys.exit(1)

if time.time() - data["last_heartbeat"] > 30:
    sys.exit(1)

sys.exit(0)

import time
from pathlib import Path
from utils import safe_read, safe_shell

STATE = Path("/home/ubuntu/mcp/state.json")
IDLE_LIMIT = 1800  # 30 min

while True:
    try:
        data = safe_read(STATE, {})
        if data and time.time() - data.get("last_heartbeat", 0) > IDLE_LIMIT:
            safe_shell("systemctl stop mcp")
            break
        time.sleep(60)
    except Exception:
        time.sleep(60)

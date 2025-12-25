import time
from pathlib import Path
from utils import safe_read, safe_shell
import os

########################################
# 📍 동적 MCP 경로 설정 (스크립트 기준)
########################################
SCRIPT_DIR = Path(__file__).resolve().parent
MCP_DIR = SCRIPT_DIR

STATE = MCP_DIR / "state.json"

########################################
# ⏳ Idle 기준 (기본: 30분)
# 환경변수로도 변경 가능: MCP_IDLE_LIMIT=900
########################################
IDLE_LIMIT = int(os.environ.get("MCP_IDLE_LIMIT", 1800))

SERVICE = "mcp"

while True:
    try:
        data = safe_read(STATE, {})
        last = data.get("last_heartbeat", 0)

        if last and (time.time() - last) > IDLE_LIMIT:
            safe_shell(f"systemctl stop {SERVICE}")
            break

        time.sleep(60)

    except Exception:
        # 어떤 에러도 watcher가 죽지 않도록
        time.sleep(60)
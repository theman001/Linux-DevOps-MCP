#!/usr/bin/env python3
import time
import sys
from pathlib import Path
from utils import safe_read

########################################
# 동적 경로 설정
########################################
BASE_DIR = Path(__file__).resolve().parent
STATE = BASE_DIR / "state.json"

########################################
# Health Check
########################################
data = safe_read(STATE, {})

# 파일 자체가 없거나 JSON 구조가 잘못됨
if not data or "last_heartbeat" not in data:
    sys.exit(1)

# 30초 이상 heartbeat 없으면 FAIL
if time.time() - data["last_heartbeat"] > 30:
    sys.exit(1)

# 정상
sys.exit(0)
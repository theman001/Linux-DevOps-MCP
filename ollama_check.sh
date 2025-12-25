#!/bin/bash
set -e

########################################
# 📍 동적 MCP 경로 설정 (스크립트 기준)
########################################
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MCP_DIR="$SCRIPT_DIR"
VENV_DIR="$MCP_DIR/mcp-venv"
ENV_FILE="/etc/mcp.env"

echo "======================================"
echo " Ollama Connection Check"
echo " MCP DIR : $MCP_DIR"
echo "======================================"

########################################
# 🔑 ENV 파일 확인
########################################
if [ ! -f "$ENV_FILE" ]; then
  echo "❌ ERROR: Env file not found: $ENV_FILE"
  echo "👉 setup_mcp.sh 를 먼저 실행하세요."
  exit 1
fi

########################################
# 🐍 venv 확인
########################################
if [ ! -f "$VENV_DIR/bin/python" ]; then
  echo "❌ ERROR: Python venv not found at:"
  echo "   $VENV_DIR"
  exit 1
fi

########################################
# 🔍 Python 실행 (API KEY + 모듈 + Cloud 체크)
########################################
VERIFY_RESULT=$(
set -a
source "$ENV_FILE"
set +a

"$VENV_DIR/bin/python" - <<'PYCODE'
import os
import socket
from ollama import Client

api_key = os.environ.get("OLLAMA_API_KEY")

if not api_key:
    print("FAIL: API key missing")
    raise SystemExit

try:
    client = Client(
        host="https://ollama.com",
        headers={"Authorization": "Bearer " + api_key}
    )

    client.list()
    print("SUCCESS")

except socket.gaierror:
    print("FAIL: DNS resolution failed")

except ConnectionError:
    print("FAIL: Network unreachable")

except Exception as e:
    msg = str(e).lower()

    if "401" in msg or "unauthorized" in msg:
        print("FAIL: Invalid API key")
    elif "429" in msg:
        print("FAIL: Rate limit exceeded")
    elif "500" in msg:
        print("FAIL: Server error")
    else:
        print(f"FAIL: {e}")
PYCODE
)

########################################
# 🎯 결과 출력
########################################
case "$VERIFY_RESULT" in
  *SUCCESS*)
    echo "✅ [SUCCESS] Ollama Cloud connected successfully!"
    ;;
  *missing*)
    echo "❌ API Key 없음 — /etc/mcp.env 확인"
    ;;
  *Invalid*)
    echo "❌ API Key가 올바르지 않습니다"
    ;;
  *DNS*)
    echo "❌ DNS 오류 — 네트워크 점검 필요"
    ;;
  *unreachable*)
    echo "❌ 네트워크 연결 불가"
    ;;
  *)
    echo "❌ Cloud 연결 실패"
    echo "$VERIFY_RESULT"
    ;;
esac

echo "======================================"
echo " Check Completed"
echo "======================================"
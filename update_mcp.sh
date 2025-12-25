#!/bin/bash
set -e

########################################
# 동적 MCP 경로 설정 (스크립트 기준)
########################################
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MCP_DIR="$SCRIPT_DIR"
VENV_DIR="$MCP_DIR/mcp-venv"
SERVICE="mcp"

echo "======================================"
echo " Linux Operations MCP Updater"
echo " MCP DIR : $MCP_DIR"
echo "======================================"

########################################
# 1️⃣ 서비스 중지
########################################
echo "[1/4] Stopping MCP service..."
sudo systemctl stop "$SERVICE" || true

########################################
# 2️⃣ (옵션) git pull — 필요 시만 사용
########################################
# echo "[2/4] Pulling latest code..."
# cd "$MCP_DIR"
# git pull origin main

########################################
# 3️⃣ Python 패키지 업데이트 (venv 고정)
########################################
echo "[2/4] Updating dependencies..."

if [ ! -d "$VENV_DIR" ]; then
  echo "❌ ERROR: venv not found at $VENV_DIR"
  echo "👉 setup_mcp.sh 를 먼저 실행해야 합니다."
  exit 1
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install --upgrade ollama
deactivate

########################################
# 4️⃣ 서비스 재시작
########################################
echo "[3/4] Restarting MCP service..."
sudo systemctl restart "$SERVICE"

########################################
# 5️⃣ 상태 점검
########################################
echo "[4/4] Verifying service state..."
sleep 3

if systemctl is-active --quiet "$SERVICE"; then
    echo "✅ Update Completed: Service is RUNNING"
else
    echo "❌ Update Failed: Service is NOT running. Check logs ↓"
    sudo journalctl -u "$SERVICE" -n 20 --no-pager
fi
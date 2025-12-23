#!/bin/bash
set -e

MCP_DIR="/home/ubuntu/mcp"
SERVICE="mcp"

echo "======================================"
echo " Linux Operations MCP Updater"
echo "======================================"

# 1. 서비스 중지
echo "[1/4] Stopping MCP service..."
sudo systemctl stop "$SERVICE"

# 2. 코드 업데이트 (git pull 가정 또는 수동 복사)
# 실제 git 사용 시 아래 주석 해제
# echo "[2/4] Pulling latest code..."
# cd "$MCP_DIR"
# git pull origin main

# 3. 의존성 패키지 업데이트
echo "[3/4] Updating dependencies..."
source "$MCP_DIR/mcp-venv/bin/activate"
pip install --upgrade pip
pip install --upgrade ollama
deactivate

# 4. 서비스 재시작
echo "[4/4] Restarting service..."
sudo systemctl restart "$SERVICE"

# 5. 건강 상태 확인
echo "Wait for 3 seconds..."
sleep 3
if systemctl is-active --quiet "$SERVICE"; then
    echo "✅ Update Completed: Service is RUNNING"
else
    echo "❌ Update Failed: Service is NOT running. Check logs."
    sudo journalctl -u mcp -n 20 --no-pager
fi

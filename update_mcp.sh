#!/bin/bash
set -e

echo "======================================"
echo " Linux Operations MCP update start"
echo "======================================"

MCP_DIR="/home/ubuntu/mcp"
SERVICE="mcp"

########################################
# 1️⃣ MCP 디렉터리 확인
########################################
echo "[1/5] Checking MCP directory..."

if [ ! -d "$MCP_DIR/.git" ]; then
  echo "ERROR: $MCP_DIR is not a git repository"
  exit 1
fi

cd "$MCP_DIR"

########################################
# 2️⃣ Git 최신 코드 가져오기
########################################
echo "[2/5] Pulling latest code..."

git fetch origin
LOCAL_HASH=$(git rev-parse HEAD)
REMOTE_HASH=$(git rev-parse origin/$(git branch --show-current))

if [ "$LOCAL_HASH" = "$REMOTE_HASH" ]; then
  echo "  - Already up to date"
else
  git pull
  echo "  - Code updated"
fi

########################################
# 3️⃣ MCP 무중단 재기동
########################################
echo "[3/5] Restarting MCP service..."

sudo systemctl restart "$SERVICE"

########################################
# 4️⃣ 기동 안정화 대기
########################################
echo "[4/5] Waiting for MCP to stabilize..."
sleep 5

########################################
# 5️⃣ Health check
########################################
echo "[5/5] Running health check..."

if python3 "$MCP_DIR/healthcheck.py"; then
  echo "======================================"
  echo " MCP update completed successfully"
  echo "======================================"
else
  echo "======================================"
  echo " MCP update FAILED"
  echo " Check logs:"
  echo "   - journalctl -u mcp"
  echo "   - /home/ubuntu/mcp/error.log"
  echo "======================================"
  exit 1
fi

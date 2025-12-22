#!/bin/bash
set -e

echo "======================================"
echo " Linux Operations MCP cleanup start"
echo "======================================"

MCP_DIR="/home/ubuntu/mcp"
SERVICE_FILE="/etc/systemd/system/mcp.service"

########################################
# 1️⃣ MCP 서비스 중지 및 비활성화
########################################
echo "[1/4] Stopping MCP service..."

if systemctl list-unit-files | grep -q "^mcp.service"; then
  sudo systemctl stop mcp || true
  sudo systemctl disable mcp || true
else
  echo "  - MCP service not found"
fi

########################################
# 2️⃣ systemd 서비스 파일 제거
########################################
echo "[2/4] Removing systemd service file..."

if [ -f "$SERVICE_FILE" ]; then
  sudo rm -f "$SERVICE_FILE"
  sudo systemctl daemon-reload
  echo "  - Service file removed"
else
  echo "  - Service file already removed"
fi

########################################
# 3️⃣ MCP 디렉터리 제거
########################################
echo "[3/4] Removing MCP directory..."

if [ -d "$MCP_DIR" ]; then
  sudo rm -rf "$MCP_DIR"
  echo "  - $MCP_DIR removed"
else
  echo "  - MCP directory already removed"
fi

########################################
# 4️⃣ 완료
########################################
echo "[4/4] Cleanup completed"

echo ""
echo "======================================"
echo " MCP cleanup finished successfully"
echo "======================================"

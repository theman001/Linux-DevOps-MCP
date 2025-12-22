#!/bin/bash
set -e

echo "======================================"
echo " Linux Operations MCP cleanup start"
echo "======================================"

SERVICE_FILE="/etc/systemd/system/mcp.service"
ENV_FILE="/etc/mcp.env"
MCP_DIR="/home/ubuntu/mcp"

########################################
# 1️⃣ MCP 서비스 중지 및 제거
########################################
echo "[1/5] Stopping and disabling MCP service..."

sudo systemctl stop mcp 2>/dev/null || true
sudo systemctl disable mcp 2>/dev/null || true

########################################
# 2️⃣ systemd 파일 제거
########################################
echo "[2/5] Removing systemd service..."

sudo rm -f "$SERVICE_FILE"
sudo systemctl daemon-reload

########################################
# 3️⃣ 환경변수 파일 제거
########################################
echo "[3/5] Removing LLM API environment file..."

sudo rm -f "$ENV_FILE"

########################################
# 4️⃣ MCP 디렉터리 정리 여부 안내
########################################
echo "[4/5] MCP directory cleanup (manual)"

echo "⚠ MCP directory not removed automatically:"
echo "  $MCP_DIR"
echo "If you want full removal, run:"
echo "  sudo rm -rf $MCP_DIR"

########################################
# 5️⃣ 완료
########################################
echo "[5/5] Cleanup completed."

echo ""
echo "======================================"
echo " MCP cleanup completed"
echo "======================================"
echo ""

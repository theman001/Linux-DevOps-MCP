#!/bin/bash
set -e

SERVICE_FILE="/etc/systemd/system/mcp.service"
ENV_FILE="/etc/mcp.env"
MCP_DIR="/home/ubuntu/mcp"

echo "======================================"
echo " Linux Operations MCP cleanup start"
echo "======================================"

########################################
# 1️⃣ 서비스 중지
########################################
sudo systemctl stop mcp 2>/dev/null || true
sudo systemctl disable mcp 2>/dev/null || true

########################################
# 2️⃣ systemd 제거
########################################
sudo rm -f "$SERVICE_FILE"
sudo systemctl daemon-reload

########################################
# 3️⃣ 환경변수 제거
########################################
sudo rm -f "$ENV_FILE"

########################################
# 4️⃣ 안내
########################################
echo "MCP directory not removed automatically:"
echo "  $MCP_DIR"
echo "Remove manually if needed:"
echo "  sudo rm -rf $MCP_DIR"

echo "======================================"
echo " MCP cleanup completed"
echo "======================================"

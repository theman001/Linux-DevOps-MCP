#!/bin/bash
set -e

MCP_DIR="/home/ubuntu/mcp"
VENV_DIR="$MCP_DIR/mcp-venv"
ENV_FILE="/etc/mcp.env"
SERVICE_FILE="/etc/systemd/system/mcp.service"

echo "======================================"
echo " Linux Operations MCP Cleanup"
echo "======================================"

########################################
# 1️⃣ Root 권한 확인
########################################
if [ "$EUID" -ne 0 ]; then
  echo "❌ ERROR: Please run as root (sudo)."
  exit 1
fi

########################################
# 2️⃣ 서비스 중지 및 비활성화
########################################
echo "[Step 1] Stopping MCP service..."

if systemctl list-unit-files | grep -q "^mcp.service"; then
    systemctl stop mcp || true
    systemctl disable mcp || true
else
    echo " - MCP service not registered."
fi

########################################
# 3️⃣ systemd 서비스 파일 제거
########################################
echo "[Step 2] Removing systemd service file..."

if [ -f "$SERVICE_FILE" ]; then
    rm -f "$SERVICE_FILE"
    systemctl daemon-reload
    echo " - Service file removed."
else
    echo " - Service file not found."
fi

########################################
# 4️⃣ 환경변수 파일 제거
########################################
echo "[Step 3] Removing environment file..."

if [ -f "$ENV_FILE" ]; then
    rm -f "$ENV_FILE"
    echo " - Environment file removed."
else
    echo " - Environment file not found."
fi

########################################
# 5️⃣ MCP Python venv 제거
########################################
echo "[Step 4] Removing MCP virtual environment..."

if [ -d "$VENV_DIR" ]; then
    rm -rf "$VENV_DIR"
    echo " - MCP venv removed."
else
    echo " - MCP venv not found."
fi

########################################
# 6️⃣ MCP 디렉토리 정리
########################################
echo "[Step 5] Cleaning MCP directory..."

if [ -d "$MCP_DIR" ]; then
    echo " - Contents of $MCP_DIR:"
    ls -la "$MCP_DIR"

    echo ""
    read -p "⚠️ Remove entire MCP directory ($MCP_DIR)? [y/N]: " CONFIRM
    if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
        rm -rf "$MCP_DIR"
        echo " - MCP directory removed."
    else
        echo " - MCP directory preserved."
    fi
else
    echo " - MCP directory not found."
fi

########################################
# 7️⃣ 완료
########################################
echo "======================================"
echo " Cleanup Completed"
echo "======================================"

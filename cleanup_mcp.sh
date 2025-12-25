#!/bin/bash
set -e

########################################
# 동적 MCP 경로 설정 (스크립트 기준)
########################################
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MCP_DIR="$SCRIPT_DIR"
VENV_DIR="$MCP_DIR/mcp-venv"
LOG_FILE="$MCP_DIR/error.log"
STATE_FILE="$MCP_DIR/state.json"
SERVICE_FILE="/etc/systemd/system/mcp.service"
ENV_FILE="/etc/mcp.env"

echo "======================================"
echo " Linux Operations MCP Cleanup"
echo " Target Path: $MCP_DIR"
echo "======================================"

########################################
# Root 권한 확인
########################################
if [ "$EUID" -ne 0 ]; then
  echo "❌ ERROR: Please run as root (sudo)"
  exit 1
fi

########################################
# 서비스 중지 & 비활성화
########################################
echo "[1/7] Stopping & disabling MCP service..."

if systemctl list-unit-files | grep -q "^mcp.service"; then
  systemctl stop mcp || true
  systemctl disable mcp || true
  echo " - MCP service stopped & disabled."
else
  echo " - MCP service not registered. Skipping."
fi

########################################
# systemd 서비스 삭제
########################################
echo "[2/7] Removing systemd service file..."

if [ -f "$SERVICE_FILE" ]; then
  rm -f "$SERVICE_FILE"
  systemctl daemon-reload
  echo " - Deleted: $SERVICE_FILE"
else
  echo " - Service file not found. Skipping."
fi

########################################
# Python venv 삭제
########################################
echo "[3/7] Removing Python virtual environment..."

if [ -d "$VENV_DIR" ]; then
  rm -rf "$VENV_DIR"
  echo " - Deleted venv: $VENV_DIR"
else
  echo " - No venv found."
fi

########################################
# 로그 및 상태 파일 삭제
########################################
echo "[4/7] Removing logs & state..."

rm -f "$LOG_FILE" "$STATE_FILE"
echo " - Deleted: error.log / state.json (if existed)"

########################################
# 환경 변수 파일 삭제 (/etc/mcp.env)
########################################
echo "[5/7] Removing environment key file..."

if [ -f "$ENV_FILE" ]; then
  rm -f "$ENV_FILE"
  echo " - Deleted API Key & env file: $ENV_FILE"
else
  echo " - No env file found."
fi

########################################
# 캐시 / 기타 생성물 정리 (옵션)
########################################
echo "[6/7] Cleaning __pycache__..."

find "$MCP_DIR" -type d -name "__pycache__" -exec rm -rf {} +

########################################
# 프로젝트 디렉토리 삭제 여부 질문
########################################
echo ""
echo "======================================"
echo " MCP uninstall is complete."
echo "======================================"
echo ""
read -p "📌 Delete project directory as well? ( $MCP_DIR ) [y/N]: " CONFIRM

CONFIRM=${CONFIRM:-N}

if [[ "$CONFIRM" == "y" || "$CONFIRM" == "Y" ]]; then
  echo "🚨 Deleting project directory..."
  rm -rf "$MCP_DIR"
  echo "✅ Project directory deleted."
else
  echo "👍 Project directory preserved."
fi

echo ""
echo "======================================"
echo " Cleanup Completed"
echo "======================================"
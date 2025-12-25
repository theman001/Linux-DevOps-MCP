#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MCP_DIR="${MCP_DIR:-$SCRIPT_DIR}"
SERVICE_NAME="${SERVICE_NAME:-mcp}"
VENV_DIR="$MCP_DIR/mcp-venv"

echo "======================================"
echo " MCP Update Script"
echo " MCP_DIR = $MCP_DIR"
echo "======================================"

echo "[1/4] Stopping service..."
sudo systemctl stop "$SERVICE_NAME" || true

echo "[2/4] Updating dependencies..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip ollama
deactivate

echo "[3/4] Restarting..."
sudo systemctl restart "$SERVICE_NAME"

echo "[4/4] Checking status..."
sleep 2
systemctl is-active --quiet "$SERVICE_NAME" \
  && echo "✅ Service running" \
  || echo "❌ Service not running"

echo "======================================"
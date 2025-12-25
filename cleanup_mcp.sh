#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MCP_DIR="${MCP_DIR:-$SCRIPT_DIR}"
SERVICE_NAME="${SERVICE_NAME:-mcp}"

echo "======================================"
echo " MCP Cleanup Script"
echo " MCP_DIR = $MCP_DIR"
echo "======================================"

echo "[1/3] Stopping service..."
sudo systemctl stop "$SERVICE_NAME" || true
sudo systemctl disable "$SERVICE_NAME" || true

echo "[2/3] Removing systemd unit..."
sudo rm -f "/etc/systemd/system/$SERVICE_NAME.service"
sudo systemctl daemon-reload

echo "[3/3] (Optional) Remove venv + logs"
rm -rf "$MCP_DIR/mcp-venv"
rm -f "$MCP_DIR/error.log" "$MCP_DIR/state.json"

echo "======================================"
echo " ✅ Cleanup complete"
echo "======================================"
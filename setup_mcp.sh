#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MCP_DIR="${MCP_DIR:-$SCRIPT_DIR}"
SERVICE_NAME="${SERVICE_NAME:-mcp}"
VENV_DIR="$MCP_DIR/mcp-venv"

echo "======================================"
echo " MCP Setup Script"
echo " MCP_DIR = $MCP_DIR"
echo " SERVICE = $SERVICE_NAME"
echo "======================================"

# Python venv
if [ ! -d "$VENV_DIR" ]; then
  echo "[1/4] Creating virtualenv..."
  python3 -m venv "$VENV_DIR"
fi

echo "[2/4] Installing dependencies..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip ollama
deactivate

# systemd 등록
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

echo "[3/4] Installing systemd service..."

sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=MCP Server
After=network.target

[Service]
Type=simple
ExecStart=$VENV_DIR/bin/python $MCP_DIR/mcp_server.py
WorkingDirectory=$MCP_DIR
Restart=always
User=root
Environment=MCP_DIR=$MCP_DIR

[Install]
WantedBy=multi-user.target
EOF

echo "[4/4] Enabling + starting service..."
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "======================================"
echo " ✅ Setup complete"
echo "======================================"
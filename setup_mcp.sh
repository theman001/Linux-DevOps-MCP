#!/bin/bash
set -e

MCP_DIR="/home/ubuntu/mcp"
VENV_DIR="$MCP_DIR/mcp-venv"
SERVICE_FILE="/etc/systemd/system/mcp.service"
ENV_FILE="/etc/mcp.env"

echo "======================================"
echo " Linux Operations MCP setup start"
echo "======================================"

########################################
# 1️⃣ LLM API KEY 입력
########################################
read -s -p "Enter Ollama Cloud LLM_API Key: " LLM_API
echo ""

if [ -z "$LLM_API" ]; then
  echo "ERROR: LLM_API cannot be empty"
  exit 1
fi

########################################
# 2️⃣ 환경변수 파일 저장
########################################
echo "[1/6] Writing environment file..."

sudo tee "$ENV_FILE" > /dev/null <<EOF
LLM_API=$LLM_API
EOF

sudo chmod 600 "$ENV_FILE"

########################################
# 3️⃣ 가상환경 구성
########################################
echo "[2/6] Preparing virtualenv..."

cd "$MCP_DIR"
python3 -m venv mcp-venv
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install requests
deactivate

########################################
# 4️⃣ systemd 서비스 생성
########################################
echo "[3/6] Creating systemd service..."

sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Linux Operations MCP
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$MCP_DIR
ExecStart=$VENV_DIR/bin/python $MCP_DIR/mcp_server.py

EnvironmentFile=$ENV_FILE
Restart=always
RestartSec=5

# Always Free 안정성 옵션
OOMScoreAdjust=-1000
Nice=10
CPUQuota=80%

ExecStartPre=/bin/sleep 20

[Install]
WantedBy=multi-user.target
EOF

########################################
# 5️⃣ 서비스 반영
########################################
echo "[4/6] Enabling MCP service..."

sudo systemctl daemon-reload
sudo systemctl enable mcp
sudo systemctl restart mcp

########################################
# 6️⃣ 완료
########################################
echo "======================================"
echo " MCP setup completed successfully"
echo "======================================"

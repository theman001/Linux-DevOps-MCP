#!/bin/bash
set -e

MCP_DIR="/home/ubuntu/mcp"
VENV_DIR="$MCP_DIR/mcp-venv"
ENV_FILE="/etc/mcp.env"
SERVICE_FILE="/etc/systemd/system/mcp.service"

echo "======================================"
echo " Linux Operations MCP setup"
echo "======================================"

########################################
# 1️⃣ LLM API KEY 입력
########################################
read -s -p "Enter Ollama Cloud OLLAMA_API_KEY: " OLLAMA_API_KEY
echo ""

if [ -z "$OLLAMA_API_KEY" ]; then
  echo "ERROR: API key cannot be empty"
  exit 1
fi

########################################
# 2️⃣ 환경변수 파일 생성
########################################
sudo tee "$ENV_FILE" > /dev/null <<EOF
OLLAMA_API_KEY=$OLLAMA_API_KEY
EOF

sudo chmod 600 "$ENV_FILE"

########################################
# 3️⃣ Python venv
########################################
cd "$MCP_DIR"

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install ollama
deactivate

########################################
# 4️⃣ systemd 서비스
########################################
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
OOMScoreAdjust=-1000
CPUQuota=80%

[Install]
WantedBy=multi-user.target
EOF

########################################
# 5️⃣ 서비스 활성화
########################################
sudo systemctl daemon-reload
sudo systemctl enable mcp
sudo systemctl restart mcp

echo "======================================"
echo " MCP setup completed"
echo "======================================"

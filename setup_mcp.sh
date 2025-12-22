#!/bin/bash
set -e

echo "======================================"
echo " Linux Operations MCP setup start"
echo "======================================"

MCP_DIR="/home/ubuntu/mcp"
VENV_DIR="$MCP_DIR/mcp-venv"
SERVICE_FILE="/etc/systemd/system/mcp.service"
ENV_FILE="/etc/mcp.env"

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
# 2️⃣ Environment 파일 생성
########################################
echo "[1/7] Writing environment file..."

sudo tee "$ENV_FILE" > /dev/null <<EOF
LLM_API=$LLM_API
EOF
sudo chmod 600 "$ENV_FILE"

# 현재 셸에서도 사용 가능하도록 export
export LLM_API="$LLM_API"

########################################
# 3️⃣ 기본 패키지 확인
########################################
echo "[2/7] Checking system packages..."

NEED_INSTALL=0
MISSING_PKGS=()

check_pkg () {
  dpkg -s "$1" >/dev/null 2>&1 || {
    NEED_INSTALL=1
    MISSING_PKGS+=("$1")
  }
}

check_pkg python3
check_pkg python3-venv
check_pkg python3-pip

if [ "$NEED_INSTALL" -eq 1 ]; then
  sudo apt update -y
  sudo apt install -y "${MISSING_PKGS[@]}"
fi

########################################
# 4️⃣ MCP 가상환경
########################################
echo "[3/7] Creating virtual environment..."

cd "$MCP_DIR"

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv mcp-venv
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install mcp requests
deactivate

########################################
# 5️⃣ systemd 서비스 생성
########################################
echo "[4/7] Creating systemd service..."

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
RestartSec=3
OOMScoreAdjust=-1000
Nice=10
CPUQuota=80%
ExecStartPre=/bin/sleep 20

[Install]
WantedBy=multi-user.target
EOF

########################################
# 6️⃣ 서비스 반영
########################################
echo "[5/7] Enabling MCP service..."

sudo systemctl daemon-reload
sudo systemctl enable mcp
sudo systemctl restart mcp

########################################
# 7️⃣ 확인
########################################
echo "[6/7] Verifying environment injection..."

systemctl show mcp --property=Environment

echo ""
echo "======================================"
echo " MCP setup completed successfully"
echo "======================================"

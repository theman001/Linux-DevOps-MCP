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
# 0️⃣ LLM API KEY 입력
########################################
echo "[0/7] Setting LLM API Key"

read -s -p "Enter Ollama Cloud API Key: " LLM_API
echo ""
if [ -z "$LLM_API" ]; then
  echo "❌ LLM_API key is required."
  exit 1
fi

# 현재 쉘 세션용 export
export LLM_API="$LLM_API"

# systemd용 env 파일 저장
sudo tee "$ENV_FILE" > /dev/null <<EOF
LLM_API=$LLM_API
EOF

sudo chmod 600 "$ENV_FILE"

########################################
# 1️⃣ 기본 패키지 확인 (없을 때만 설치)
########################################
echo "[1/7] Checking system packages..."

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
# 2️⃣ MCP 전용 가상환경 생성
########################################
echo "[2/7] Creating MCP virtual environment..."

cd "$MCP_DIR"

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install mcp requests
deactivate

########################################
# 3️⃣ systemd 서비스 생성
########################################
echo "[3/7] Creating systemd service..."

sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Linux Operations MCP
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$MCP_DIR
ExecStart=$VENV_DIR/bin/python $MCP_DIR/mcp_server.py

# 🔑 LLM API Key 적용
EnvironmentFile=$ENV_FILE

Restart=always
RestartSec=3

# Always Free 안정성 옵션
OOMScoreAdjust=-1000
Nice=10
CPUQuota=80%

ExecStartPre=/bin/sleep 20

[Install]
WantedBy=multi-user.target
EOF

########################################
# 4️⃣ systemd 반영 및 자동 시작
########################################
echo "[4/7] Enabling MCP service..."

sudo systemctl daemon-reload
sudo systemctl enable mcp
sudo systemctl restart mcp

########################################
# 5️⃣ Swap 존재 여부 확인
########################################
echo "[5/7] Checking swap..."

if ! swapon --show | grep -q "/swapfile"; then
  sudo fallocate -l 4G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  grep -q "^/swapfile" /etc/fstab || \
    echo "/swapfile swap swap defaults 0 0" | sudo tee -a /etc/fstab
fi

########################################
# 6️⃣ 상태 확인
########################################
echo "[6/7] MCP status:"
systemctl status mcp --no-pager || true

########################################
# 7️⃣ 완료
########################################
echo ""
echo "======================================"
echo " MCP setup completed successfully"
echo "======================================"
echo ""
echo "LLM_API 적용 상태:"
echo "  - shell      : export LLM_API=****"
echo "  - systemd    : $ENV_FILE"
echo ""

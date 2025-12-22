#!/bin/bash
set -e

echo "======================================"
echo " Linux Operations MCP setup start"
echo "======================================"

MCP_DIR="/home/ubuntu/mcp"
VENV_DIR="$MCP_DIR/mcp-venv"
SERVICE_FILE="/etc/systemd/system/mcp.service"

########################################
# 1️⃣ 기본 패키지 확인 (없을 때만 설치)
########################################
echo "[1/6] Checking system packages..."

NEED_INSTALL=0
MISSING_PKGS=()

check_pkg () {
  dpkg -s "$1" >/dev/null 2>&1 || {
    echo "  - $1 not installed"
    NEED_INSTALL=1
    MISSING_PKGS+=("$1")
  }
}

check_pkg python3
check_pkg python3-venv
check_pkg python3-pip

if [ "$NEED_INSTALL" -eq 1 ]; then
  echo "Installing missing packages: ${MISSING_PKGS[*]}"
  sudo apt update -y
  sudo apt install -y "${MISSING_PKGS[@]}"
else
  echo "All required packages are already installed."
fi

########################################
# 2️⃣ MCP 전용 가상환경 생성
########################################
echo "[2/6] Creating MCP virtual environment..."

cd "$MCP_DIR"

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv mcp-venv
  echo "  - mcp-venv created"
else
  echo "  - mcp-venv already exists"
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install mcp
deactivate

########################################
# 3️⃣ systemd 서비스 생성
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

Restart=always
RestartSec=3

# Always Free 안정성 옵션
OOMScoreAdjust=-1000
Nice=10
CPUQuota=80%

# 부팅 직후 안정화 대기
ExecStartPre=/bin/sleep 20

[Install]
WantedBy=multi-user.target
EOF

########################################
# 4️⃣ systemd 반영 및 자동 시작 설정
########################################
echo "[4/6] Enabling MCP service..."

sudo systemctl daemon-reload
sudo systemctl enable mcp
sudo systemctl restart mcp

########################################
# 5️⃣ Swap 존재 여부 확인 (없을 때만 생성)
########################################
echo "[5/6] Checking swap..."

if ! swapon --show | grep -q "/swapfile"; then
  echo "  - No swap detected. Creating 4G swapfile..."
  sudo fallocate -l 4G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile

  if ! grep -q "^/swapfile" /etc/fstab; then
    echo "/swapfile swap swap defaults 0 0" | sudo tee -a /etc/fstab
  fi
else
  echo "  - Swap already exists."
fi

########################################
# 6️⃣ 상태 확인
########################################
echo "[6/6] MCP status:"
systemctl status mcp --no-pager || true

echo ""
echo "======================================"
echo " MCP setup completed successfully"
echo "======================================"
echo ""
echo "Useful commands:"
echo "  - Start MCP   : sudo systemctl start mcp"
echo "  - Stop MCP    : sudo systemctl stop mcp"
echo "  - Restart MCP : sudo systemctl restart mcp"
echo "  - Status MCP  : systemctl status mcp"

#!/bin/bash
set -e

MCP_DIR="/home/ubuntu/mcp"
VENV_DIR="$MCP_DIR/mcp-venv"
ENV_FILE="/etc/mcp.env"
SERVICE_FILE="/etc/systemd/system/mcp.service"
REQ_FILE="$MCP_DIR/requirements.txt"

echo "======================================"
echo " Linux Operations MCP Setup"
echo "======================================"

########################################
# 1️⃣ LLM API KEY 입력
########################################
echo "Ollama Cloud API Key가 필요합니다."
echo "키가 없다면 다음 주소에서 생성하세요: https://ollama.com/settings/keys"
echo ""
read -s -p "Enter OLLAMA_API_KEY: " OLLAMA_API_KEY
echo ""

if [ -z "$OLLAMA_API_KEY" ]; then
  echo "❌ ERROR: API key cannot be empty."
  exit 1
fi

########################################
# 2️⃣ 환경변수 파일 생성
########################################
echo "[Step 1] Creating environment file..."
sudo mkdir -p "$(dirname "$ENV_FILE")"
sudo tee "$ENV_FILE" > /dev/null <<EOF
OLLAMA_API_KEY=$OLLAMA_API_KEY
EOF
sudo chmod 600 "$ENV_FILE"

########################################
# 3️⃣ MCP 디렉토리 & requirements.txt 확인
########################################
echo "[Step 2] Preparing MCP directory..."

mkdir -p "$MCP_DIR"

if [ ! -f "$REQ_FILE" ]; then
  echo " - requirements.txt not found. Creating default one."
  cat > "$REQ_FILE" <<EOF
ollama
EOF
else
  echo " - requirements.txt found."
fi

########################################
# 4️⃣ MCP 전용 Python venv 생성
########################################
echo "[Step 3] Setting up MCP Python virtual environment..."

if [ ! -d "$VENV_DIR" ]; then
    echo " - Creating venv at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
else
    echo " - Existing venv found at $VENV_DIR"
fi

########################################
# 5️⃣ MCP 의존성 즉시 설치 (requirements.txt)
########################################
echo "[Step 4] Installing Python dependencies into MCP venv..."

"$VENV_DIR/bin/python" -m pip install --upgrade pip > /dev/null
"$VENV_DIR/bin/python" -m pip install -r "$REQ_FILE" > /dev/null

########################################
# 6️⃣ systemd 서비스 등록
########################################
echo "[Step 5] Registering systemd service..."

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

[Install]
WantedBy=multi-user.target
EOF

########################################
# 7️⃣ 서비스 활성화
########################################
echo "[Step 6] Starting service..."

sudo systemctl daemon-reload
sudo systemctl enable mcp
sudo systemctl restart mcp

########################################
# 8️⃣ ☁️ Ollama Cloud 연결 검증
########################################
echo "======================================"
echo " 🔍 Verifying Ollama Cloud Connection..."
echo "======================================"

VERIFY_RESULT=$(
"$VENV_DIR/bin/python" - <<'PYCODE'
import os
from ollama import Client

try:
    client = Client(
        host="https://ollama.com",
        headers={"Authorization": "Bearer " + os.environ["OLLAMA_API_KEY"]}
    )
    client.list()
    print("SUCCESS")
except Exception as e:
    print(f"FAIL: {e}")
PYCODE
)

if [[ "$VERIFY_RESULT" == *"SUCCESS"* ]]; then
    echo "✅ [SUCCESS] Ollama Cloud connected successfully!"
    echo "   - API Key is valid."
    echo "   - MCP Service is running."
else
    echo "❌ [FAILED] Could not connect to Ollama Cloud."
    echo "   - Error details: $VERIFY_RESULT"
    echo ""
    echo "👉 Please check your API Key at: https://ollama.com/settings/keys"
    echo "👉 Update the key manually in: $ENV_FILE"
    echo "   Then restart: sudo systemctl restart mcp"
fi

echo "======================================"
echo " Setup Completed"
echo "======================================"

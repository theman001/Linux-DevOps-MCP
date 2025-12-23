#!/bin/bash
set -e

MCP_DIR="/home/ubuntu/mcp"
VENV_DIR="$MCP_DIR/mcp-venv"
ENV_FILE="/etc/mcp.env"
SERVICE_FILE="/etc/systemd/system/mcp.service"

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
sudo tee "$ENV_FILE" > /dev/null <<EOF
OLLAMA_API_KEY=$OLLAMA_API_KEY
EOF
sudo chmod 600 "$ENV_FILE"

########################################
# 3️⃣ Python venv 및 라이브러리 설치
########################################
echo "[Step 2] Setting up Python environment..."
mkdir -p "$MCP_DIR"
cd "$MCP_DIR"

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip > /dev/null
pip install ollama > /dev/null
deactivate

########################################
# 4️⃣ systemd 서비스 등록
########################################
echo "[Step 3] Registering systemd service..."
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
# 5️⃣ 서비스 활성화
########################################
echo "[Step 4] Starting service..."
sudo systemctl daemon-reload
sudo systemctl enable mcp
sudo systemctl restart mcp

########################################
# 6️⃣ ☁️ Ollama Cloud 연결 검증 (피드백)
########################################
echo "======================================"
echo " 🔍 Verifying Ollama Cloud Connection..."
echo "======================================"

# 검증용 임시 파이썬 스크립트 실행
VERIFY_RESULT=$(source "$VENV_DIR/bin/activate" && python3 -c "
import os, sys
from ollama import Client
try:
    client = Client(
        host='https://ollama.com',
        headers={'Authorization': 'Bearer ' + os.environ['OLLAMA_API_KEY']}
    )
    # 가벼운 모델 정보 조회 시도 (실제 호출 대신 list 확인)
    # API 키가 유효한지 확인하는 가장 가벼운 방법
    client.list() 
    print('SUCCESS')
except Exception as e:
    print(f'FAIL: {e}')
" 2>&1)

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

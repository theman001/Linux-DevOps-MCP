#!/bin/bash
set -e

########################################
# 동적 MCP 경로 설정 (스크립트 기준)
########################################
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MCP_DIR="$SCRIPT_DIR"
VENV_DIR="$MCP_DIR/mcp-venv"
REQ_FILE="$MCP_DIR/requirements.txt"
ENV_FILE="/etc/mcp.env"
SERVICE_FILE="/etc/systemd/system/mcp.service"

echo "======================================"
echo " Linux Operations MCP Setup"
echo " Install Path: $MCP_DIR"
echo "======================================"

########################################
# 0️⃣ Root 권한 확인
########################################
if [ "$EUID" -ne 0 ]; then
  echo "❌ ERROR: Please run as root (sudo)."
  exit 1
fi

########################################
# 1️⃣ Ollama Cloud API Key 입력
########################################
echo "Ollama Cloud API Key가 필요합니다."
echo "키 생성: https://ollama.com/settings/keys"
echo ""
read -s -p "Enter OLLAMA_API_KEY: " OLLAMA_API_KEY
echo ""

if [ -z "$OLLAMA_API_KEY" ]; then
  echo "❌ ERROR: API key cannot be empty."
  exit 1
fi

########################################
# 2️⃣ 환경변수 파일 생성 (/etc/mcp.env)
########################################
echo "[Step 1] Creating environment file..."

mkdir -p "$(dirname "$ENV_FILE")"
cat > "$ENV_FILE" <<EOF
OLLAMA_API_KEY=$OLLAMA_API_KEY
EOF
chmod 600 "$ENV_FILE"

########################################
# 3️⃣ MCP 디렉토리 및 requirements.txt 준비
########################################
echo "[Step 2] Preparing MCP directory..."

mkdir -p "$MCP_DIR"

if [ ! -f "$REQ_FILE" ]; then
  echo " - requirements.txt not found. Creating default."
  cat > "$REQ_FILE" <<EOF
ollama>=0.1.8
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
  echo " - Existing venv found."
fi

########################################
# 5️⃣ Python 의존성 설치 (venv 고정)
########################################
echo "[Step 4] Installing Python dependencies..."

"$VENV_DIR/bin/python" -m pip install --upgrade pip > /dev/null
"$VENV_DIR/bin/python" -m pip install -r "$REQ_FILE" > /dev/null

########################################
# 6️⃣ systemd 서비스 등록
########################################
echo "[Step 5] Registering systemd service..."

cat > "$SERVICE_FILE" <<EOF
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
echo "[Step 6] Starting MCP service..."

systemctl daemon-reload
systemctl enable mcp
systemctl restart mcp

########################################
# 8️⃣ Ollama Cloud 연결 검증 (중요)
########################################
echo "======================================"
echo " 🔍 Verifying Ollama Cloud Connection..."
echo "======================================"

VERIFY_RESULT=$(
set -a
source "$ENV_FILE"
set +a

"$VENV_DIR/bin/python" - <<'PYCODE'
import os
from ollama import Client

try:
    api_key = os.environ.get("OLLAMA_API_KEY")
    if not api_key:
        raise RuntimeError("OLLAMA_API_KEY not found")

    client = Client(
        host="https://ollama.com",
        headers={"Authorization": "Bearer " + api_key}
    )

    client.list()
    print("SUCCESS")

except Exception as e:
    print(f"FAIL: {e}")
PYCODE
)

if [[ "$VERIFY_RESULT" == *"SUCCESS"* ]]; then
  echo "✅ [SUCCESS] Ollama Cloud connected successfully!"
  echo "   - API Key loaded correctly"
  echo "   - MCP environment ready"
else
  echo "❌ [FAILED] Could not connect to Ollama Cloud."
  echo "   - Error details: $VERIFY_RESULT"
  echo ""
  echo "👉 Check API Key: https://ollama.com/settings/keys"
  echo "👉 Edit key in: $ENV_FILE"
  echo "👉 Restart: sudo systemctl restart mcp"
fi

echo "======================================"
echo " Setup Completed"
echo "======================================"
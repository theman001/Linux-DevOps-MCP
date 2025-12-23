#!/bin/bash
set -e

MCP_DIR="/home/ubuntu/mcp"
VENV_DIR="$MCP_DIR/mcp-venv"
ENV_FILE="/etc/mcp.env"
SERVICE_FILE="/etc/systemd/system/mcp.service"
REQ_FILE="$MCP_DIR/requirements.txt"

echo "======================================"
echo " Ollama Connection Check"
echo "======================================"

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

    # 가장 가벼운 API 호출
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
echo " Check Completed"
echo "======================================"

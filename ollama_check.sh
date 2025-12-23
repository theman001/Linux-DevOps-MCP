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

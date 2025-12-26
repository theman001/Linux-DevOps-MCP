#!/bin/bash

# ───────────────────────────────
# Root 자동 승격
# ───────────────────────────────
if [ "$EUID" -ne 0 ]; then
  exec sudo "$0" "$@"
fi

set -e

SERVICE_NAME="mcp"

echo "======================================"
echo " MCP CLI Launcher (Auto-Detect Mode)"
echo "======================================"

# ───────────────────────────────
# 1️⃣ systemd에서 ExecStart 경로 가져오기
# ───────────────────────────────
EXEC_CMD=$(systemctl show "$SERVICE_NAME" -p ExecStart --value)

if [ -z "$EXEC_CMD" ]; then
  echo "❌ ExecStart not found for service: $SERVICE_NAME"
  echo "👉 MCP가 systemctl 서비스로 설치되었는지 확인하세요"
  exit 1
fi

# ExecStart 안에서 python 경로 / script 경로 분리
MCP_PY=$(echo "$EXEC_CMD" | awk '{print $1}')
MCP_SERVER=$(echo "$EXEC_CMD" | awk '{print $2}')

echo "📌 Detected:"
echo " Python  = $MCP_PY"
echo " Server  = $MCP_SERVER"
echo ""

# ───────────────────────────────
# 2️⃣ 파일 검증
# ───────────────────────────────
if [ ! -x "$MCP_PY" ]; then
  echo "❌ MCP Python not executable:"
  echo "   $MCP_PY"
  exit 1
fi

if [ ! -f "$MCP_SERVER" ]; then
  echo "❌ MCP server file missing:"
  echo "   $MCP_SERVER"
  exit 1
fi

echo "✅ Valid MCP installation detected"
echo ""
echo "🔐 OLLAMA_API_KEY will load automatically from /etc/mcp.env"
echo ""

# ───────────────────────────────
# 3️⃣ CLI 실행
# ───────────────────────────────
exec "$MCP_PY" "$MCP_SERVER" --cli

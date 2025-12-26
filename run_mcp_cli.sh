#!/bin/bash

# 이미 root면 그대로 진행
if [ "$EUID" -ne 0 ]; then
  exec sudo "$0" "$@"
fi

set -e

########################################
# DEV → MCP CLI Bridge (NO env sourcing)
########################################

# 🔥 MCP 설치경로 자동 감지 (systemd 기준)
MCP_DIR=$(grep WorkingDirectory /etc/systemd/system/mcp.service | awk -F'=' '{print $2}')

MCP_PY="$MCP_DIR/mcp-venv/bin/python"
MCP_SERVER="$MCP_DIR/mcp_server.py"

echo "======================================"
echo " MCP CLI (from DEV venv)"
echo "======================================"

echo "📍 MCP DIR  : $MCP_DIR"
echo "🐍 MCP PY   : $MCP_PY"
echo "🖥  MCP SRV : $MCP_SERVER"
echo ""

# 1️⃣ MCP Python 확인
if [ ! -x "$MCP_PY" ]; then
  echo "❌ MCP venv python not found or not executable:"
  echo "   $MCP_PY"
  exit 1
fi

# 2️⃣ MCP 서버 확인
if [ ! -f "$MCP_SERVER" ]; then
  echo "❌ MCP server not found:"
  echo "   $MCP_SERVER"
  exit 1
fi

echo "✅ Using MCP venv:"
echo "   $MCP_PY"
echo ""
echo "🔐 MCP will load /etc/mcp.env internally"
echo ""

########################################
# 3️⃣ MCP CLI 실행
########################################
exec "$MCP_PY" "$MCP_SERVER" --cli

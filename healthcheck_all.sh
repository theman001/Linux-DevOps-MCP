#!/bin/bash

echo "======================================"
echo " Linux Operations MCP full healthcheck"
echo "======================================"

MCP_DIR="/home/ubuntu/mcp"
SERVICE="mcp"

FAIL=0

########################################
# 1️⃣ systemd 상태
########################################
echo "[1/6] Checking systemd service..."

if systemctl is-active --quiet "$SERVICE"; then
  echo "  - MCP service is running"
else
  echo "  - MCP service is NOT running"
  FAIL=1
fi

########################################
# 2️⃣ MCP heartbeat 상태
########################################
echo "[2/6] Checking MCP heartbeat..."

if python3 "$MCP_DIR/healthcheck.py"; then
  echo "  - Heartbeat OK"
else
  echo "  - Heartbeat FAIL"
  FAIL=1
fi

########################################
# 3️⃣ state.json 확인
########################################
echo "[3/6] Checking state.json..."

if [ -f "$MCP_DIR/state.json" ]; then
  cat "$MCP_DIR/state.json"
else
  echo "  - state.json missing"
  FAIL=1
fi

########################################
# 4️⃣ 최근 에러 로그
########################################
echo "[4/6] Checking recent error logs..."

if [ -f "$MCP_DIR/error.log" ]; then
  tail -n 10 "$MCP_DIR/error.log"
else
  echo "  - No error.log found (OK)"
fi

########################################
# 5️⃣ 메모리 / Swap 상태
########################################
echo "[5/6] Checking memory & swap..."

free -h
swapon --show || echo "  - No swap detected"

########################################
# 6️⃣ 최종 판단
########################################
echo "[6/6] Final result"

if [ "$FAIL" -eq 0 ]; then
  echo "======================================"
  echo " MCP STATUS: HEALTHY"
  echo "======================================"
  exit 0
else
  echo "======================================"
  echo " MCP STATUS: UNHEALTHY"
  echo " Action recommended:"
  echo "   - sudo systemctl restart mcp"
  echo "   - check /home/ubuntu/mcp/error.log"
  echo "======================================"
  exit 1
fi

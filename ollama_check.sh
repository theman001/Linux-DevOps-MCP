#!/bin/bash
set -e

echo "Checking Ollama access..."

if ! command -v ollama >/dev/null; then
  echo "❌ ollama CLI not installed"
  exit 1
fi

ollama list && echo "✅ Ollama reachable"
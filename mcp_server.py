#!/usr/bin/env python3
import os
import json
import time
import traceback
import requests
from datetime import datetime

MCP_DIR = "/home/ubuntu/mcp"
LOG_FILE = f"{MCP_DIR}/error.log"

LLM_API = os.environ.get("LLM_API")  # ← 반드시 이 변수명 사용
OLLAMA_ENDPOINT = "https://ollama.com/api/chat"
MODEL_NAME = "gpt-oss:120b"

def log_error(e: Exception):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now()}] {repr(e)}\n")
        f.write(traceback.format_exc())
        f.write("\n")

def call_llm(prompt: str) -> dict:
    if not LLM_API:
        raise RuntimeError("LLM_API environment variable not set")

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a Linux operations AI.\n"
                    "Always respond in strict JSON format.\n"
                    "Schema:\n"
                    "{"
                    "  action: one of [noop, shell, edit_file],"
                    "  reason: string,"
                    "  command?: string,"
                    "  file?: string,"
                    "  diff?: string"
                    "}"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }

    headers = {
        "Authorization": f"Bearer {LLM_API}",
        "Content-Type": "application/json",
    }

    resp = requests.post(
        OLLAMA_ENDPOINT,
        headers=headers,
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()

    data = resp.json()
    content = data["message"]["content"]
    return json.loads(content)

def rule_based_fallback(prompt: str) -> dict:
    if "disk" in prompt.lower():
        return {
            "action": "shell",
            "reason": "Rule-based disk check fallback",
            "command": "df -h",
        }

    return {
        "action": "noop",
        "reason": "Fallback: no safe automatic action",
    }

def apply_action(result: dict):
    action = result.get("action")

    if action == "shell":
        cmd = result.get("command")
        if cmd:
            os.system(cmd)

    elif action == "edit_file":
        path = result.get("file")
        diff = result.get("diff")
        if path and diff:
            with open(path, "a") as f:
                f.write("\n# MCP AUTO PATCH\n")
                f.write(diff)

def handle_event(prompt: str):
    try:
        llm_result = call_llm(prompt)
    except Exception as e:
        log_error(e)
        llm_result = rule_based_fallback(prompt)

    apply_action(llm_result)

def main():
    while True:
        try:
            prompt = input().strip()
            if prompt:
                handle_event(prompt)
        except EOFError:
            time.sleep(1)
        except Exception as e:
            log_error(e)
            time.sleep(5)

if __name__ == "__main__":
    main()

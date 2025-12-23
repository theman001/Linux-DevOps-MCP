#!/usr/bin/env python3
import os
import json
import time
import threading
import traceback
import subprocess
from pathlib import Path
from datetime import datetime

from ollama import Client

# 설정
MCP_DIR = Path("/home/ubuntu/mcp")
LOG_FILE = MCP_DIR / "error.log"
STATE_FILE = MCP_DIR / "state.json"

# Ollama Cloud 설정
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
# Cloud 모델명 (필요시 'gpt-oss:120b-cloud' 등으로 변경 가능)
OLLAMA_MODEL = "gpt-oss:120b"

def log_error(msg):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now()}] {msg}\n")

def update_heartbeat():
    """
    백그라운드에서 state.json의 타임스탬프를 갱신
    (healthcheck.py가 죽은 프로세스로 오인하지 않게 함)
    """
    while True:
        try:
            state = {"last_heartbeat": time.time(), "status": "running"}
            STATE_FILE.write_text(json.dumps(state))
        except Exception:
            pass  # 하트비트 실패는 로그 남기지 않음 (IO 부하 방지)
        time.sleep(10)

def rule_based_fallback(prompt: str, reason: str) -> dict:
    return {
        "decision": "NO_ACTION",
        "reason": f"Fallback: {reason}",
        "actions": [],
        "notes": prompt[:200]
    }

def call_llm(prompt: str) -> dict:
    if not OLLAMA_API_KEY:
        raise RuntimeError("OLLAMA_API_KEY not set")

    client = Client(
        host="https://ollama.com",
        headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"}
    )

    system_prompt = """
You are a Linux operations AI.
Respond ONLY in valid JSON with this schema:
{
  "decision": "APPLY_FIX | REPORT_ONLY | NO_ACTION",
  "reason": "string",
  "actions": [
    {
      "type": "shell | edit_file",
      "command": "string",
      "file": "string",
      "diff": "string"
    }
  ]
}
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    try:
        # format='json'을 사용하여 구조화된 데이터 강제
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=messages,
            stream=False, # 단순화를 위해 stream 끔 (JSON 파싱 안정성)
            format='json'
        )
        content = response['message']['content']
        return json.loads(content)

    except json.JSONDecodeError:
        log_error(f"JSON Parse Error. Raw content: {content}")
        return rule_based_fallback(prompt, "Invalid JSON from LLM")
    except Exception as e:
        log_error(f"LLM Call Error: {repr(e)}\n{traceback.format_exc()}")
        return rule_based_fallback(prompt, "LLM API Error")

def apply_actions(actions: list):
    results = []
    for action in actions:
        try:
            if action["type"] == "shell":
                proc = subprocess.run(
                    action["command"], shell=True, capture_output=True, text=True, timeout=30
                )
                results.append(f"CMD: {action['command']} -> {proc.returncode}")
            elif action["type"] == "edit_file":
                with open(action["file"], "a") as f:
                    f.write(f"\n# MCP AUTO PATCH ({datetime.now()})\n")
                    f.write(action.get("diff", ""))
                results.append(f"EDIT: {action['file']}")
        except Exception as e:
            log_error(f"Action Fail: {action} -> {e}")
    return results

def handle_event(prompt: str):
    result = call_llm(prompt)
    
    if result.get("decision") == "APPLY_FIX":
        logs = apply_actions(result.get("actions", []))
        result["action_logs"] = logs
        
    return result

if __name__ == "__main__":
    # 1. 하트비트 스레드 시작 (데몬)
    t = threading.Thread(target=update_heartbeat, daemon=True)
    t.start()

    # 2. 메인 루프 (stdio)
    while True:
        try:
            user_input = input()
            if not user_input:
                continue
            
            output = handle_event(user_input)
            print(json.dumps(output))
            
        except EOFError:
            break
        except Exception as e:
            log_error(f"Main Loop Error: {e}")
            print(json.dumps(rule_based_fallback("Unknown", "System Error")))

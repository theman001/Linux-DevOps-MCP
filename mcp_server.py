#!/usr/bin/env python3
import os
import json
import time
import threading
import traceback
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from ollama import Client

########################################
# 기본 경로 설정
########################################
MCP_DIR = Path("/home/ubuntu/mcp")
LOG_FILE = MCP_DIR / "error.log"
STATE_FILE = MCP_DIR / "state.json"
ENV_FILE = "/etc/mcp.env"
OLLAMA_MODEL = "gpt-oss:120b"

########################################
# 공통 유틸
########################################
def log_error(msg: str):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now()}] {msg}\n")

########################################
# 환경변수 로딩 (지연 로딩)
########################################
def ensure_env_loaded():
    """
    - systemd(root) 실행: 이미 로드됨
    - sudo / CLI 실행: /etc/mcp.env 직접 로드
    """
    if os.environ.get("OLLAMA_API_KEY"):
        return

    if not os.path.exists(ENV_FILE):
        log_error("Environment file not found: /etc/mcp.env")
        return

    try:
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)
    except Exception as e:
        log_error(f"Failed to load env file: {e}")

def get_api_key() -> str | None:
    return os.environ.get("OLLAMA_API_KEY")

########################################
# 상태 하트비트
########################################
def update_heartbeat():
    while True:
        try:
            STATE_FILE.write_text(
                json.dumps({
                    "last_heartbeat": time.time(),
                    "status": "running"
                })
            )
        except Exception:
            pass
        time.sleep(10)

########################################
# Fallback
########################################
def rule_based_fallback(prompt: str, reason: str) -> dict:
    return {
        "decision": "NO_ACTION",
        "reason": f"Fallback: {reason}",
        "actions": [],
        "notes": prompt[:200]
    }

########################################
# LLM 호출
########################################
def call_llm(prompt: str) -> dict:
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("OLLAMA_API_KEY not set")

    client = Client(
        host="https://ollama.com",
        headers={"Authorization": f"Bearer {api_key}"}
    )

    system_prompt = """
Return ONLY valid JSON.
Schema:
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

    try:
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            stream=False,
            format="json"
        )
        return json.loads(response["message"]["content"])

    except json.JSONDecodeError:
        log_error("JSON parse error from LLM")
        return rule_based_fallback(prompt, "Invalid JSON from LLM")
    except Exception as e:
        log_error(f"LLM call error: {e}\n{traceback.format_exc()}")
        return rule_based_fallback(prompt, "LLM API Error")

########################################
# 액션 실행
########################################
def apply_actions(actions: list):
    results = []
    for action in actions:
        try:
            if action["type"] == "shell":
                proc = subprocess.run(
                    action["command"],
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                results.append(
                    f"CMD[{proc.returncode}]: {action['command']}"
                )

            elif action["type"] == "edit_file":
                with open(action["file"], "a") as f:
                    f.write(f"\n# MCP AUTO PATCH {datetime.now()}\n")
                    f.write(action.get("diff", ""))
                results.append(f"EDIT: {action['file']}")

        except Exception as e:
            log_error(f"Action failed: {action} -> {e}")
            results.append(f"FAIL: {action}")

    return results

########################################
# 이벤트 처리
########################################
def handle_event(prompt: str) -> dict:
    result = call_llm(prompt)

    if result.get("decision") == "APPLY_FIX":
        logs = apply_actions(result.get("actions", []))
        result["action_logs"] = logs

    return result

########################################
# CLI 모드
########################################
def run_cli_mode():
    print("======================================")
    print(" MCP CLI MODE")
    print(" type 'quit' to exit")
    print("======================================")

    busy = False

    while True:
        try:
            user_input = input("\nMCP> ").strip()

            if user_input.lower() == "quit":
                print("Bye.")
                return

            if busy:
                print("⚠️ MCP is processing. Input ignored.")
                continue

            if not user_input:
                continue

            busy = True
            print("⏳ processing...")

            result = handle_event(user_input)
            print(json.dumps(result, indent=2))

        except Exception as e:
            log_error(f"CLI Error: {e}")
            print(json.dumps(rule_based_fallback("CLI", "System Error"), indent=2))
        finally:
            busy = False

########################################
# STDIO 서버 모드
########################################
def run_stdio_mode():
    while True:
        try:
            prompt = input()
            if not prompt:
                continue
            result = handle_event(prompt)
            print(json.dumps(result))
        except EOFError:
            return
        except Exception as e:
            log_error(f"STDIO Error: {e}")
            print(json.dumps(rule_based_fallback("STDIO", "System Error")))

########################################
# Main
########################################
def main():
    ensure_env_loaded()

    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", action="store_true")
    args = parser.parse_args()

    t = threading.Thread(target=update_heartbeat, daemon=True)
    t.start()

    if args.cli:
        run_cli_mode()
    else:
        run_stdio_mode()

if __name__ == "__main__":
    main()

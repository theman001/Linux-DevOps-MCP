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

# =========================
# 설정
# =========================
MCP_DIR = Path("/home/ubuntu/mcp")
LOG_FILE = MCP_DIR / "error.log"
STATE_FILE = MCP_DIR / "state.json"

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_MODEL = "gpt-oss:120b"

# =========================
# 공통 유틸
# =========================
def log_error(msg):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now()}] {msg}\n")

def update_heartbeat():
    while True:
        try:
            state = {"last_heartbeat": time.time(), "status": "running"}
            STATE_FILE.write_text(json.dumps(state))
        except Exception:
            pass
        time.sleep(10)

def rule_based_fallback(prompt: str, reason: str) -> dict:
    return {
        "decision": "NO_ACTION",
        "reason": f"Fallback: {reason}",
        "actions": [],
        "notes": prompt[:200]
    }

# =========================
# MCP Server Core
# =========================
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
      "type": "shell",
      "command": "string"
    }
  ]
}
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    try:
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=messages,
            stream=False,
            format="json"
        )
        return json.loads(response["message"]["content"])

    except json.JSONDecodeError as e:
        log_error(f"JSON Parse Error: {e}")
        return rule_based_fallback(prompt, "Invalid JSON from LLM")
    except Exception as e:
        log_error(f"LLM Error: {e}\n{traceback.format_exc()}")
        return rule_based_fallback(prompt, "LLM API Error")

def apply_actions(actions: list):
    results = []
    for action in actions:
        try:
            if action.get("type") == "shell":
                proc = subprocess.run(
                    action["command"],
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                results.append(f"{action['command']} -> rc={proc.returncode}")
        except Exception as e:
            log_error(f"Action Fail: {action} -> {e}")
            results.append(f"ERROR: {e}")
    return results

def handle_event(prompt: str):
    result = call_llm(prompt)
    if result.get("decision") == "APPLY_FIX":
        result["action_logs"] = apply_actions(result.get("actions", []))
    return result

# =========================
# MCP Client (CLI Mode)
# =========================
def run_cli_mode():
    print("===================================")
    print(" MCP CLI MODE (type 'quit' to exit)")
    print("===================================")

    busy = False
    lock = threading.Lock()

    while True:
        try:
            user_input = input("\n[MCP INPUT] > ").strip()

            if user_input.lower() == "quit":
                print("\n[MCP] CLI mode exited.")
                break

            with lock:
                if busy:
                    print("⚠️  MCP is processing a request. Input ignored.")
                    continue
                busy = True

            print("[MCP] Processing...")

            result = handle_event(user_input)

            print("\n[MCP OUTPUT]")
            print(json.dumps(result, indent=2, ensure_ascii=False))

        except Exception as e:
            log_error(f"CLI Error: {e}")
            print("❌ Error occurred. See error.log")

        finally:
            with lock:
                busy = False

# =========================
# Main Entry
# =========================
def main():
    parser = argparse.ArgumentParser(description="Linux Operations MCP")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run MCP in interactive CLI mode"
    )
    args = parser.parse_args()

    # 하트비트 스레드
    t = threading.Thread(target=update_heartbeat, daemon=True)
    t.start()

    if args.cli:
        run_cli_mode()
        return

    # 기본 STDIO Server 모드
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

if __name__ == "__main__":
    main()

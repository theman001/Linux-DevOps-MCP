#!/usr/bin/env python3
import os
import json
import traceback
import subprocess
from datetime import datetime

from ollama import Client

LOG_FILE = "/home/ubuntu/mcp/error.log"

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_MODEL = "gpt-oss:120b"

def log_error(e):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now()}] {repr(e)}\n")
        f.write(traceback.format_exc() + "\n")

def rule_based_fallback(prompt: str) -> dict:
    """
    LLM 실패 시 최소 안전 조치
    """
    return {
        "decision": "NO_ACTION",
        "reason": "LLM unavailable, fallback activated",
        "actions": [],
        "notes": prompt[:300]
    }

def call_llm(prompt: str) -> dict:
    if not OLLAMA_API_KEY:
        raise RuntimeError("OLLAMA_API_KEY not set")

    client = Client(
        host="https://ollama.com",
        headers={
            "Authorization": f"Bearer {OLLAMA_API_KEY}"
        }
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

    response_text = ""

    for part in client.chat(
        model=OLLAMA_MODEL,
        messages=messages,
        stream=True,
    ):
        response_text += part["message"]["content"]

    return json.loads(response_text)

def apply_actions(actions: list):
    for action in actions:
        if action["type"] == "shell":
            subprocess.run(
                action["command"],
                shell=True,
                check=False,
            )

        elif action["type"] == "edit_file":
            with open(action["file"], "a") as f:
                f.write("\n# MCP AUTO PATCH\n")
                f.write(action.get("diff", ""))

def handle_event(prompt: str):
    try:
        result = call_llm(prompt)
    except Exception as e:
        log_error(e)
        result = rule_based_fallback(prompt)

    if result.get("decision") == "APPLY_FIX":
        apply_actions(result.get("actions", []))

    return result

if __name__ == "__main__":
    # MCP stdin/stdout 루프 단순화 버전
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
            log_error(e)

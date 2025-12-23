#!/usr/bin/env python3
import os
import json
import subprocess
import traceback
from datetime import datetime
from typing import Dict, Any

from ollama import Client

MCP_DIR = "/home/ubuntu/mcp"
ERROR_LOG = f"{MCP_DIR}/error.log"
INCIDENTS = f"{MCP_DIR}/incidents.json"

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_MODEL = "gpt-oss:120b"

# -----------------------------
# Logging helpers
# -----------------------------
def log_error(err: Exception):
    with open(ERROR_LOG, "a") as f:
        f.write(f"[{datetime.now()}] {repr(err)}\n")
        f.write(traceback.format_exc())
        f.write("\n")

def record_incident(reason: str):
    data = []
    if os.path.exists(INCIDENTS):
        try:
            data = json.load(open(INCIDENTS))
        except Exception:
            pass

    data.append({
        "time": datetime.now().isoformat(),
        "reason": reason
    })

    with open(INCIDENTS, "w") as f:
        json.dump(data, f, indent=2)

# -----------------------------
# LLM Call (Ollama Cloud)
# -----------------------------
def call_llm(prompt: str) -> Dict[str, Any]:
    if not OLLAMA_API_KEY:
        raise RuntimeError("OLLAMA_API_KEY not set")

    client = Client(
        host="https://ollama.com",
        headers={
            "Authorization": f"Bearer {OLLAMA_API_KEY}"
        }
    )

    response = client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a Linux operations AI. "
                    "Respond ONLY in valid JSON.\n\n"
                    "Schema:\n"
                    "{\n"
                    "  \"decision\": \"auto_fix | advise | noop\",\n"
                    "  \"actions\": [\"shell commands\"],\n"
                    "  \"summary\": \"human readable summary\"\n"
                    "}"
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        stream=False
    )

    content = response["message"]["content"]
    return json.loads(content)

# -----------------------------
# Rule-based fallback
# -----------------------------
def fallback_decision(prompt: str) -> Dict[str, Any]:
    if "disk" in prompt.lower():
        return {
            "decision": "advise",
            "actions": ["df -h", "du -sh /var/log/*"],
            "summary": "Disk-related issue detected. Manual inspection recommended."
        }

    if "memory" in prompt.lower():
        return {
            "decision": "auto_fix",
            "actions": ["free -m", "sync; echo 3 > /proc/sys/vm/drop_caches"],
            "summary": "Memory pressure detected. Dropping caches."
        }

    return {
        "decision": "noop",
        "actions": [],
        "summary": "No actionable issue detected."
    }

# -----------------------------
# Action executor
# -----------------------------
def execute_actions(actions):
    results = []
    for cmd in actions:
        try:
            out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=30)
            results.append(out.decode())
        except Exception as e:
            log_error(e)
            results.append(str(e))
    return results

# -----------------------------
# MCP Entry Point
# -----------------------------
def handle_event(event: Dict[str, Any]) -> Dict[str, Any]:
    prompt = event.get("prompt", "")

    try:
        llm_result = call_llm(prompt)
    except Exception as e:
        log_error(e)
        record_incident("LLM failure → fallback used")
        llm_result = fallback_decision(prompt)

    if llm_result["decision"] == "auto_fix":
        outputs = execute_actions(llm_result["actions"])
        llm_result["outputs"] = outputs

    return llm_result

# -----------------------------
# Main loop (stdin/stdout MCP)
# -----------------------------
if __name__ == "__main__":
    while True:
        try:
            raw = input()
            event = json.loads(raw)
            result = handle_event(event)
            print(json.dumps(result), flush=True)
        except EOFError:
            break
        except Exception as e:
            log_error(e)

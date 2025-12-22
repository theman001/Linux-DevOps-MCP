import os
import json
import traceback
import subprocess
import requests
from datetime import datetime
from typing import Dict, Any

STATE_FILE = "state.json"
INCIDENT_FILE = "incidents.json"
PATTERN_FILE = "patterns.json"
ERROR_LOG = "error.log"

OLLAMA_ENDPOINT = "https://api.ollama.com/v1/chat/completions"
LLM_API = os.getenv("LLM_API")

# -----------------------------
# Utilities
# -----------------------------

def log_error(e: Exception):
    with open(ERROR_LOG, "a") as f:
        f.write(f"[{datetime.now()}] {repr(e)}\n")
        f.write(traceback.format_exc() + "\n")

def safe_load(path, default):
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default

def safe_save(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log_error(e)

# -----------------------------
# LLM Call (Ollama Cloud)
# -----------------------------

def call_llm(prompt: str) -> Dict[str, Any]:
    if not LLM_API:
        raise RuntimeError("LLM_API environment variable not set")

    payload = {
        "model": "gpt-oss-20b",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a Linux operations and software maintenance AI.\n"
                    "Respond ONLY in valid JSON matching this schema:\n"
                    "{\n"
                    "  \"analysis\": string,\n"
                    "  \"decision\": \"no_action\" | \"shell\" | \"code_patch\",\n"
                    "  \"command\": string | null,\n"
                    "  \"patch\": {\"file\": string, \"diff\": string} | null,\n"
                    "  \"confidence\": number\n"
                    "}"
                )
            },
            {"role": "user", "content": prompt}
        ]
    }

    headers = {
        "Authorization": f"Bearer {LLM_API}",
        "Content-Type": "application/json"
    }

    resp = requests.post(
        OLLAMA_ENDPOINT,
        headers=headers,
        json=payload,
        timeout=30
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]

    return json.loads(content)

# -----------------------------
# Rule-based fallback
# -----------------------------

def fallback_decision(context: str) -> Dict[str, Any]:
    if "disk" in context.lower():
        return {
            "decision": "shell",
            "command": "df -h && du -sh /* | sort -h | tail",
            "patch": None
        }
    if "memory" in context.lower():
        return {
            "decision": "shell",
            "command": "free -h && ps aux --sort=-%mem | head",
            "patch": None
        }
    return {"decision": "no_action", "command": None, "patch": None}

# -----------------------------
# Code patch applier
# -----------------------------

def apply_patch(patch: Dict[str, str]):
    try:
        file = patch["file"]
        diff = patch["diff"]
        proc = subprocess.run(
            ["patch", file],
            input=diff,
            text=True,
            capture_output=True
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr)
    except Exception as e:
        log_error(e)
        raise

# -----------------------------
# Main MCP handler
# -----------------------------

def handle_event(event: str, context: str):
    patterns = safe_load(PATTERN_FILE, {})
    incidents = safe_load(INCIDENT_FILE, [])

    prompt = (
        f"Event: {event}\n"
        f"Context:\n{context}\n\n"
        f"Known patterns:\n{json.dumps(patterns, indent=2)}"
    )

    try:
        llm_result = call_llm(prompt)
    except Exception as e:
        log_error(e)
        llm_result = fallback_decision(context)

    try:
        decision = llm_result["decision"]

        if decision == "shell":
            subprocess.run(llm_result["command"], shell=True)

        elif decision == "code_patch":
            apply_patch(llm_result["patch"])

        # pattern learning
        patterns.setdefault(event, 0)
        patterns[event] += 1

    except Exception as e:
        log_error(e)
        incidents.append({
            "time": str(datetime.now()),
            "event": event,
            "error": repr(e)
        })

    safe_save(PATTERN_FILE, patterns)
    safe_save(INCIDENT_FILE, incidents)

# -----------------------------
# Example entry
# -----------------------------

if __name__ == "__main__":
    handle_event(
        "boot_check",
        subprocess.getoutput("uptime && free -h && df -h")
    )

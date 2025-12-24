#!/usr/bin/env python3
import os
import json
import time
import threading
import subprocess
import argparse
import traceback
import sys
from pathlib import Path
from datetime import datetime
from ollama import Client

########################################
# 기본 경로 / 설정
########################################
MCP_DIR = Path("/home/ubuntu/mcp")
LOG_FILE = MCP_DIR / "error.log"
STATE_FILE = MCP_DIR / "state.json"
ENV_FILE = "/etc/mcp.env"

########################################
# 모델 정책
########################################
MODEL_CLASSIFIER = "nemotron-3-nano:30b-cloud"

MODEL_CHAINS = {
    "server_operation": [
        "gpt-oss:120b",
        "qwen3-next:80b",
    ],
    "code_generation": [
        "devstral-2:123b-cloud",
        "qwen3-coder:30b-cloud",
    ],
    "explanatory": [
        "gemini-3-flash-preview:cloud",
        "mistral-large-3",
    ],
    "unknown": [
        "ministral-3:14b",
        "glm-4.6",
    ],
}

CONFIDENCE_THRESHOLD = 0.6

########################################
# report mode 판단
########################################
REPORT_KEYWORDS = [
    "report mode",
    "report_only",
    "--report",
    "[report]"
]

########################################
# 캐시
########################################
CLASSIFY_CACHE: dict[str, dict] = {}

########################################
# 공통 유틸
########################################
def log_error(msg: str):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now()}] {msg}\n")

def progress(msg: str):
    print(msg, file=sys.stderr, flush=True)

########################################
# ENV 로딩
########################################
def ensure_env_loaded():
    if os.environ.get("OLLAMA_API_KEY"):
        return
    if not os.path.exists(ENV_FILE):
        return
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)

########################################
# Heartbeat
########################################
def update_heartbeat():
    while True:
        try:
            STATE_FILE.write_text(json.dumps({
                "last_heartbeat": time.time(),
                "status": "running"
            }))
        except Exception:
            pass
        time.sleep(10)

########################################
# Ollama Client
########################################
def ollama_client():
    return Client(
        host="https://ollama.com",
        headers={"Authorization": f"Bearer {os.environ.get('OLLAMA_API_KEY')}"}
    )

########################################
# report mode 룰 체크
########################################
def is_report_mode(user_input: str) -> bool:
    t = user_input.lower()
    return any(k in t for k in REPORT_KEYWORDS)

########################################
# 1차 분류
########################################
def classify_request(user_input: str) -> dict:
    if user_input in CLASSIFY_CACHE:
        return CLASSIFY_CACHE[user_input]

    system_prompt = """
Return ONLY valid JSON.
Do not generate commands.
Nature values:
server_operation | code_generation | explanatory | unknown
"""

    user_prompt = f"""
User request:
{user_input}

Return JSON:
{{
  "nature": "string",
  "rewritten_request": "string",
  "confidence": 0.0
}}
"""

    try:
        progress("⏳ 요청 분류 중 (nemotron-3-nano)")
        client = ollama_client()
        resp = client.chat(
            model=MODEL_CLASSIFIER,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            format="json",
            stream=False
        )
        result = json.loads(resp["message"]["content"])
        CLASSIFY_CACHE[user_input] = result
        return result
    except Exception as e:
        log_error(traceback.format_exc())
        return {
            "nature": "unknown",
            "rewritten_request": user_input,
            "confidence": 0.0
        }

########################################
# LLM 호출 (자동 스위칭)
########################################
def call_with_fallback(models: list[str], system_prompt: str, user_prompt: str) -> dict:
    last_error = None
    client = ollama_client()

    for model in models:
        try:
            progress(f"## {model} 에 요청")
            resp = client.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                format="json",
                stream=False
            )
            return json.loads(resp["message"]["content"])
        except Exception as e:
            last_error = str(e)
            progress(f"@@ {model} 에 요청 실패 (실패 사유: {last_error})")
            log_error(traceback.format_exc())

    raise RuntimeError(f"All models failed. Last error: {last_error}")

########################################
# 실행 계획 생성
########################################
def build_execution_plan(models: list[str], rewritten_request: str) -> dict:
    system_prompt = """
Return ONLY valid JSON.
Schema:
{
  "description": "string",
  "commands": ["string"],
  "output_file": "string | null"
}
"""
    return call_with_fallback(models, system_prompt, rewritten_request)

########################################
# EXECUTE
########################################
def execute_plan(plan: dict) -> dict:
    progress("⏳ 명령어 실행 중 (root)")
    results = []

    for cmd in plan.get("commands", []):
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        results.append({
            "command": cmd,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip()
        })

    if plan.get("output_file"):
        with open(plan["output_file"], "w") as f:
            for r in results:
                f.write(f"$ {r['command']}\n{r['stdout']}\n\n")

    return {
        "mode": "EXECUTE",
        "description": plan.get("description"),
        "results": results,
        "saved_to": plan.get("output_file")
    }

########################################
# REPORT
########################################
def generate_report(models: list[str], rewritten_request: str) -> dict:
    system_prompt = "Explain the request clearly for an operator."
    result = call_with_fallback(models, system_prompt, rewritten_request)
    return {
        "mode": "REPORT",
        "report": result
    }

########################################
# 메인 처리
########################################
def handle_input(user_input: str) -> dict:
    report_mode = is_report_mode(user_input)
    cls = classify_request(user_input)

    nature = cls.get("nature", "unknown")
    if cls.get("confidence", 0.0) < CONFIDENCE_THRESHOLD:
        nature = "unknown"

    rewritten = cls.get("rewritten_request", user_input)
    models = MODEL_CHAINS.get(nature, MODEL_CHAINS["unknown"])

    if report_mode:
        return generate_report(models, rewritten)

    plan = build_execution_plan(models, rewritten)
    return execute_plan(plan)

########################################
# CLI
########################################
def run_cli():
    print("=== MCP CLI ===")
    while True:
        try:
            text = input("\nMCP> ").strip()
            if text.lower() in ("quit", "exit"):
                return
            result = handle_input(text)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        except Exception:
            log_error(traceback.format_exc())
            print("❌ error occurred")

########################################
# Main
########################################
def main():
    if os.geteuid() != 0:
        print("❌ MCP must be run as root", file=sys.stderr)
        return

    ensure_env_loaded()
    threading.Thread(target=update_heartbeat, daemon=True).start()

    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", action="store_true")
    args = parser.parse_args()

    if args.cli:
        run_cli()

if __name__ == "__main__":
    main()

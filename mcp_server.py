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
        "qwen3-coder:480b-cloud",
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
# 1차 분류 (nemotron)
########################################
def classify_request(user_input: str) -> dict:
    if user_input in CLASSIFY_CACHE:
        return CLASSIFY_CACHE[user_input]

    system_prompt = """
You are an intent classification and request rewriting engine
for an automated Linux DevOps control assistant.

Your responsibilities:
1. Understand the user's natural language request
2. Rewrite it into a concise, unambiguous technical task description
3. Select ONE best-fitting category

Allowed categories:
- server_operation   (Linux 운영/관리/자동화/설정/점검/배포/장애조치)
- code_generation    (스크립트/코드/프로그램 생성/수정/디버깅)
- explanatory        (설명/해설/지식요청/보고서 형태 요청)
- unknown            (판단이 어려운 경우)

Important Rules:
- DO NOT generate shell commands
- DO NOT generate code
- DO NOT execute anything
- Output ONLY valid JSON (NO markdown)

Return format:
{
  "nature": "server_operation | code_generation | explanatory | unknown",
  "rewritten_request": "rewritten task",
  "confidence": 0.0
}
"""

    user_prompt = f"""
User submitted request:

{user_input}

Return JSON ONLY.
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
    except Exception:
        log_error(traceback.format_exc())
        return {
            "nature": "unknown",
            "rewritten_request": user_input,
            "confidence": 0.0
        }

########################################
# LLM 호출 (자동 스위칭)
########################################
def call_with_fallback(models: list[str], system_prompt: str, user_prompt: str, expect_json=True):
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
                format="json" if expect_json else None,
                stream=False
            )

            if expect_json:
                return json.loads(resp["message"]["content"])
            else:
                return resp["message"]["content"]

        except Exception as e:
            last_error = str(e)
            progress(f"@@ {model} 요청 실패 (이유: {last_error})")
            log_error(traceback.format_exc())

    raise RuntimeError(f"모든 모델 요청 실패. 마지막 오류: {last_error}")

########################################
# 실행 계획 생성
########################################
def build_execution_plan(models: list[str], rewritten_request: str) -> dict:

    system_prompt = """
You are a **senior DevOps / Linux operations engineer**.

Your job:
Convert the user's rewritten request into a SAFE execution plan.

Return ONLY JSON in the following schema:

{
  "description": "what will be done in natural language",
  "commands": [
    "shell command 1",
    "shell command 2"
  ],
  "output_file": "path or null"
}

Rules:
- Commands must be valid Linux shell commands
- Prefer idempotent & safe commands
- Never include destructive actions unless explicitly required
- DO NOT add explanations
- DO NOT return markdown
"""
    return call_with_fallback(models, system_prompt, rewritten_request, expect_json=True)

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

    system_prompt = """
You are an expert Korean technical writer.

Explain the user's request in clear Korean so that a system operator can easily understand it.

Rules:
- 자연스럽고 명확한 한국어로 작성
- 불필요한 장황한 표현 금지
- 요약 + 필요한 경우 bullet 사용
- JSON 반환 금지
"""

    result = call_with_fallback(models, system_prompt, rewritten_request, expect_json=False)

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

    if report_mode or nature == "explanatory":
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

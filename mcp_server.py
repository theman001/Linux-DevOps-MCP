#!/usr/bin/env python3
import os
import json
import time
import threading
import subprocess
import argparse
import traceback
import sys
import glob
import re
from pathlib import Path
from datetime import datetime
from ollama import Client

########################################
# 동적 설치 경로 지원
########################################
BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "error.log"
STATE_FILE = BASE_DIR / "state.json"
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
# 코드 컨텍스트 트리거 키워드
########################################
CONTEXT_TRIGGERS = [
    "이 폴더",
    "현재 폴더",
    "파일 참고",
    "코드 참고",
    "스크립트 참고",
    "project",
    "context"
]

########################################
# 캐시
########################################
CLASSIFY_CACHE = {}

########################################
# 로깅 / 유틸
########################################
def log_error(msg):
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now()}] {msg}\n")

def progress(msg):
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
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)

########################################
# Ollama
########################################
def ollama_client():
    return Client(
        host="https://ollama.com",
        headers={"Authorization": f"Bearer {os.environ.get('OLLAMA_API_KEY')}"}
    )

########################################
# 파일 컨텍스트 로딩
########################################
def should_attach_context(user_input: str) -> bool:
    t = user_input.lower()
    return any(k.lower() in t for k in CONTEXT_TRIGGERS)

SENSITIVE_PATTERN = re.compile(
    r"(api[_-]?key|password|secret|token|auth|authorization)",
    re.IGNORECASE
)

ALLOWED_EXT = (".py", ".sh", ".conf", ".yml", ".yaml", ".json")

def load_file_context(max_per_file=60000, max_total=250000):
    ctx = {}
    total = 0

    for path in BASE_DIR.glob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_EXT:
            continue

        try:
            data = path.read_text(errors="ignore")

            if len(data) > max_per_file:
                data = data[:max_per_file] + "\n...[TRUNCATED]"

            # 민감 정보 마스킹
            data = SENSITIVE_PATTERN.sub("[MASKED]", data)

            new_total = total + len(data)
            if new_total > max_total:
                break

            ctx[path.name] = data
            total = new_total

        except Exception as e:
            log_error(f"ctx fail {path}: {e}")

    return ctx

########################################
# report mode
########################################
def is_report_mode(user_input):
    t = user_input.lower()
    return any(k in t for k in REPORT_KEYWORDS)

########################################
# 1차 분류
########################################
def classify_request(user_input: str, file_ctx=None) -> dict:
    key = (user_input, bool(file_ctx))
    if key in CLASSIFY_CACHE:
        return CLASSIFY_CACHE[key]

    system_prompt = """
You are an intent classification and request rewriting engine.

Rules:
- Output ONLY valid JSON
- Do NOT generate commands
- Do NOT decide execution or report mode
- Be concise

Nature values:
server_operation | code_generation | explanatory | unknown
"""

    user_prompt = {
        "user_request": user_input,
        "project_context": file_ctx or {}
    }

    try:
        progress("⏳ 요청 분류 중 (nemotron-3-nano)")
        client = ollama_client()
        resp = client.chat(
            model=MODEL_CLASSIFIER,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_prompt)}
            ],
            format="json",
            stream=False
        )
        result = json.loads(resp["message"]["content"])
        CLASSIFY_CACHE[key] = result
        return result
    except Exception:
        log_error(traceback.format_exc())
        return {
            "nature": "unknown",
            "rewritten_request": user_input,
            "confidence": 0.0
        }

########################################
# fallback LLM 호출
########################################
def call_with_fallback(models, system_prompt, user_prompt):
    last = None
    client = ollama_client()

    for model in models:
        try:
            progress(f"## {model} 에 요청")
            resp = client.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_prompt)}
                ],
                format="json",
                stream=False
            )
            return json.loads(resp["message"]["content"])
        except Exception as e:
            last = str(e)
            progress(f"@@ {model} 실패 (사유:{last})")
            log_error(traceback.format_exc())

    raise RuntimeError(last)

########################################
# 실행 계획
########################################
def build_execution_plan(models, rewritten_request, file_ctx):
    system_prompt = """
You are a Linux DevOps assistant.

Your job:
- Convert the request into a SAFE execution plan
- RETURN ONLY VALID JSON

Rules:
- Never embed shell redirection into code files unless explicitly required
- Prefer pure script output w/o here-doc unless really requested
- Avoid creating secrets or credentials
- Output format must be:

{
 "description": "string",
 "commands": ["cmd", "cmd2"],
 "output_file": "string | null"
}
"""
    return call_with_fallback(
        models,
        system_prompt,
        {
            "rewritten_request": rewritten_request,
            "project_context": file_ctx or {}
        }
    )

########################################
# EXECUTE
########################################
def execute_plan(plan):
    progress("⏳ 명령어 실행 중 (root)")
    results = []

    for cmd in plan.get("commands", []):
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=90
        )
        results.append({
            "command": cmd,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip()
        })

    return {
        "mode": "EXECUTE",
        "description": plan.get("description"),
        "results": results,
        "saved_to": plan.get("output_file")
    }

########################################
# REPORT
########################################
def generate_report(models, rewritten_request, file_ctx):
    system_prompt = "Explain clearly in Korean for a Linux operator."
    res = call_with_fallback(
        models,
        system_prompt,
        {
            "rewritten_request": rewritten_request,
            "project_context": file_ctx or {}
        }
    )
    return {"mode": "REPORT", "report": res}

########################################
# 메인 로직
########################################
def handle_input(user_input):
    file_ctx = load_file_context() if should_attach_context(user_input) else {}

    cls = classify_request(user_input, file_ctx)
    nature = cls.get("nature", "unknown")

    if cls.get("confidence", 0.0) < CONFIDENCE_THRESHOLD:
        nature = "unknown"

    models = MODEL_CHAINS.get(nature, MODEL_CHAINS["unknown"])
    rewritten = cls.get("rewritten_request", user_input)

    if is_report_mode(user_input):
        return generate_report(models, rewritten, file_ctx)

    plan = build_execution_plan(models, rewritten, file_ctx)
    return execute_plan(plan)

########################################
# CLI
########################################
def run_cli():
    print("=== MCP CLI ===")
    while True:
        text = input("\nMCP> ").strip()
        if text.lower() in ("quit", "exit"):
            return
        try:
            print(json.dumps(handle_input(text), indent=2, ensure_ascii=False))
        except Exception:
            log_error(traceback.format_exc())
            print("❌ error occurred")

########################################
# MAIN
########################################
def main():
    if os.geteuid() != 0:
        print("❌ must run as root", file=sys.stderr)
        return
    ensure_env_loaded()

    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", action="store_true")
    args = parser.parse_args()

    if args.cli:
        run_cli()

if __name__ == "__main__":
    main()
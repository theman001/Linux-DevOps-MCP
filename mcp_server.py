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
# JSON 유효성 강제
########################################
def safe_load_json(text, default):
    try:
        return json.loads(text)
    except Exception:
        return default

########################################
# 1차 분류
########################################
def classify_request(user_input: str, file_ctx=None) -> dict:
    key = (user_input, bool(file_ctx))
    if key in CLASSIFY_CACHE:
        return CLASSIFY_CACHE[key]

    system_prompt = """
You are an intent classifier for Linux/DevOps automation.

Your ONLY job:
- Identify the *intent category* of the user request
- Rewrite the request into a normalized clean form
- Estimate confidence

You MUST return ONLY valid JSON.

ACCEPTABLE VALUES for field "nature":
- "server_operation"   (Linux admin, DevOps, commands, scripts)
- "code_generation"    (programming, debugging, code writing)
- "explanatory"        (ask for explanation, guides, learning)
- "unknown"            (unclear / mixed / unsafe / other)

MANDATORY JSON SCHEMA:
{
 "nature": "server_operation | code_generation | explanatory | unknown",
 "rewritten_request": "string",
 "confidence": number(0.0 - 1.0)
}

Rules you MUST follow strictly:
1. Return ONLY JSON. No markdown. No extra text.
2. rewritten_request MUST be concise but complete
3. If you are uncertain, set nature="unknown"
4. If classification confidence is weak, set confidence <= 0.5
5. DO NOT include opinions
6. DO NOT include commands
7. DO NOT embed code blocks
8. DO NOT hallucinate missing context
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

        result = safe_load_json(
            resp["message"]["content"],
            {"nature": "unknown", "rewritten_request": user_input, "confidence": 0.0}
        )

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
You are a Linux DevOps automation assistant.

Your job:
Convert the rewritten request + optional project context into a SAFE execution plan.

YOU MUST RETURN JSON ONLY:

{
 "description": "string",
 "commands": ["string", ...],
 "output_file": "string or null"
}

MANDATORY SAFETY RULES
You MUST NOT recommend commands that:
- delete or destroy system files
- remove packages or format disks
- modify bootloader or kernel
- disable security protections
- create/modify system users
- modify sudoers
- reboot or shutdown
- execute malware or attacks
- access secrets
- require interactive input

If the user request appears unsafe:
- commands MUST be []
- description MUST explain WHY it was blocked

COMMAND RULES
- Commands MUST be POSIX shell compatible
- No here-docs unless explicitly required
- Do NOT embed authentication secrets
- Avoid environment-dependent side effects
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

    commands = plan.get("commands", [])
    if not isinstance(commands, list):
        commands = []

    for cmd in commands:
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
    system_prompt = """
You are a Korean-language technical explainer for Linux DevOps.

You MUST return ONLY JSON:

{
 "summary": "string",
 "steps": ["string", ...],
 "risk": "low | medium | high"
}

Rules:
- Output must be Korean
- No markdown
- No code fences
- No emojis
"""

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
    parser.add_argument("--text", type=str)
    args = parser.parse_args()

    if args.cli:
        run_cli()
    elif args.text:
        try:
            result = handle_input(args.text)
            print(json.dumps(result, ensure_ascii=False))
        except Exception:
            log_error(traceback.format_exc())
            print(json.dumps({"error": "AI processing failed"}, ensure_ascii=False))

if __name__ == "__main__":
    main()

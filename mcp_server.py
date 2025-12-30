#!/usr/bin/env python3
import os
import json
import subprocess
import argparse
import traceback
import sys
import re
import time
import signal
import logging
from pathlib import Path
from datetime import datetime
from ollama import Client

########################################
# Paths
########################################
BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "error.log"
ENV_FILE = "/etc/mcp.env"

PROMPT_DIR = BASE_DIR / "prompts"
CLASSIFIER_FILE = PROMPT_DIR / "classifier.txt"
PLANNER_FILE = PROMPT_DIR / "planner.txt"
REPORTER_FILE = PROMPT_DIR / "reporter.txt"

########################################
# Logging
########################################
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("MCP-Server")

########################################
# Model policy
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
# Allowed file extensions for context
########################################
ALLOWED_EXT = (
    ".py", ".sh", ".conf", ".yaml", ".yml",
    ".json", ".ini", ".cfg", ".go", ".js", ".ts"
)

########################################
# Utilities
########################################
def log_error(msg):
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now()}] {msg}\n")

def progress(msg):
    print(msg, file=sys.stderr, flush=True)

########################################
# ENV loader
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
                os.environ.setdefault(k, v.strip().strip('"').strip("'"))

########################################
# Ollama client
########################################
def ollama_client():
    return Client(
        host="https://ollama.com",
        headers={"Authorization": f"Bearer {os.environ.get('OLLAMA_API_KEY')}"}
    )

########################################
# JSON safe loader
########################################
def safe_load_json(text, default=None):
    try:
        clean = re.sub(r"```json\s*|\s*```", "", text).strip()
        return json.loads(clean)
    except Exception:
        return default

########################################
# Prompt loaders (hot reload)
########################################
def load_prompt(path: Path):
    if not path.exists():
        raise RuntimeError(f"Prompt not found: {path}")
    return path.read_text()

########################################
# Classifier
########################################
def classify(user_input):
    try:
        system_prompt = load_prompt(CLASSIFIER_FILE)
        client = ollama_client()

        progress("🔍 Classifier 호출 (nemotron-3-nano)")

        resp = client.chat(
            model=MODEL_CLASSIFIER,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            format="json",
            stream=False
        )

        parsed = safe_load_json(resp["message"]["content"], {})

        return {
            "category": parsed.get("category", "unknown"),
            "confidence": parsed.get("confidence", 0.0),
            "needs_context": parsed.get("needs_context", False),
            "reason": parsed.get("reason", "")
        }

    except Exception:
        log_error(traceback.format_exc())
        return {
            "category": "unknown",
            "confidence": 0.0,
            "needs_context": False,
            "reason": "classification failed"
        }

########################################
# Context loader
########################################
def load_project_context(max_per_file=60000, max_total=250000):
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

            if total + len(data) > max_total:
                break

            ctx[path.name] = data
            total += len(data)

        except Exception:
            continue

    return ctx

########################################
# Model chain executor
########################################
def call_with_models(models, system_prompt, user_payload):
    client = ollama_client()
    last = None

    for model in models:
        try:
            progress(f"🤖 모델 호출: {model}")

            resp = client.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
                ],
                format="json",
                stream=False
            )

            return safe_load_json(resp["message"]["content"], {})

        except Exception as e:
            last = str(e)
            log_error(traceback.format_exc())
            progress(f"⚠️ 실패: {model}: {last}")

    raise RuntimeError(last)

########################################
# Planner
########################################
def build_execution_plan(models, rewritten_request, ctx):
    system_prompt = load_prompt(PLANNER_FILE)

    payload = {
        "rewritten_request": rewritten_request,
        "project_context": ctx or {}
    }

    return call_with_models(models, system_prompt, payload)

########################################
# Reporter
########################################
def generate_report(models, rewritten_request, ctx):
    system_prompt = load_prompt(REPORTER_FILE)

    payload = {
        "rewritten_request": rewritten_request,
        "project_context": ctx or {}
    }

    res = call_with_models(models, system_prompt, payload)

    return {"mode": "REPORT", "report": res}

########################################
# Executor
########################################
def execute_plan(plan):
    commands = plan.get("commands", [])
    if not isinstance(commands, list):
        commands = []

    if not commands:
        return {
            "mode": "NO_EXEC",
            "description": plan.get("description", "No commands generated")
        }

    progress("🛠 명령 실행 중...")

    results = []
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
            "stderr": proc.stderr.strip(),
        })

    return {
        "mode": "EXECUTE",
        "description": plan.get("description"),
        "results": results,
        "saved_to": plan.get("output_file")
    }

########################################
# Dispatcher
########################################
def handle_input(text):
    cls = classify(text)

    category = cls["category"]
    confidence = cls["confidence"]
    needs_ctx = cls["needs_context"]

    if confidence < CONFIDENCE_THRESHOLD:
        category = "unknown"

    models = MODEL_CHAINS.get(category, MODEL_CHAINS["unknown"])

    progress(f"📌 category={category}, needs_context={needs_ctx}")

    ctx = load_project_context() if needs_ctx else {}

    if category == "explanatory":
        return generate_report(models, text, ctx)

    plan = build_execution_plan(models, text, ctx)
    return execute_plan(plan)

########################################
# Service mode
########################################
def run_as_service():
    logger.info("MCP 서비스 실행됨 (대기)")

    stop = False

    def handler(sig, frame):
        nonlocal stop
        stop = True
        logger.info("종료 요청 수신...")

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

    while not stop:
        time.sleep(1)

    logger.info("MCP 서비스 종료 완료")

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
        print("=== MCP CLI MODE ===")
        while True:
            try:
                line = input("\nMCP> ").strip()
            except EOFError:
                break

            if line.lower() in ("quit", "exit"):
                break

            try:
                res = handle_input(line)
                print(json.dumps(res, ensure_ascii=False, indent=2))
            except Exception:
                log_error(traceback.format_exc())
                print("❌ error")

    elif args.text:
        try:
            res = handle_input(args.text)
            print(json.dumps(res, ensure_ascii=False))
        except Exception:
            log_error(traceback.format_exc())
            print(json.dumps({"error": "AI processing failed"}, ensure_ascii=False))
    else:
        run_as_service()

if __name__ == "__main__":
    main()

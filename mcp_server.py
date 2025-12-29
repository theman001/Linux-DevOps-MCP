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

# 로깅 설정 (systemctl 및 journalctl 연동용)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
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
# Report detection keywords
########################################
REPORT_KEYWORDS = [
    "report mode",
    "report_only",
    "--report",
    "[report]"
]

########################################
# Context trigger keywords
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
# Cache
########################################
CLASSIFY_CACHE = {}

########################################
# Logging / utilities
########################################
def log_error(msg):
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now()}] {msg}\n")

def progress(msg):
    # main.go에서 실시간 읽기를 위해 stderr로 출력
    print(msg, file=sys.stderr, flush=True)

########################################
# ENV load
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
# Context loader (masked)
########################################
SENSITIVE_PATTERN = re.compile(
    r"(api[_-]?key|password|secret|token|auth|authorization)",
    re.IGNORECASE
)

ALLOWED_EXT = (".py", ".sh", ".conf", ".yml", ".yaml", ".json")

def should_attach_context(user_input: str) -> bool:
    t = user_input.lower()
    return any(k.lower() in t for k in CONTEXT_TRIGGERS)

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
            data = SENSITIVE_PATTERN.sub("[MASKED]", data)
            new_total = total + len(data)
            if new_total > max_total:
                break
            ctx[path.name] = data
            total = new_total
        except Exception as e:
            log_error(f"context load fail {path}: {e}")
    return ctx

########################################
# Report mode detect
########################################
def is_report_mode(user_input):
    t = user_input.lower()
    return any(k in t for k in REPORT_KEYWORDS)

########################################
# Safe JSON load
########################################
def safe_load_json(text, default):
    try:
        # AI가 마크다운 블록을 씌우는 경우 대비
        clean_text = re.sub(r"```json\s*|\s*```", "", text).strip()
        return json.loads(clean_text)
    except Exception:
        return default

########################################
# Classifier
########################################
def classify_request(user_input: str, file_ctx=None) -> dict:
    key = (user_input, bool(file_ctx))
    if key in CLASSIFY_CACHE:
        return CLASSIFY_CACHE[key]

    system_prompt = """
You are an intent classifier and request normalizer for a Linux/DevOps AI automation system.
Your job consists of TWO tasks ONLY:
(1) CLASSIFY THE USER REQUEST
(2) NORMALIZE THE REQUEST
MANDATORY OUTPUT FORMAT: JSON ONLY.
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
        return {"nature": "unknown", "rewritten_request": user_input, "confidence": 0.0}

########################################
# Fallback invocation
########################################
def call_with_fallback(models, system_prompt, user_prompt):
    client = ollama_client()
    last = None
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
            return safe_load_json(resp["message"]["content"], {})
        except Exception as e:
            last = str(e)
            log_error(traceback.format_exc())
            progress(f"@@ {model} 실패: {last}")
    raise RuntimeError(last)

########################################
# Execution plan builder
########################################
def build_execution_plan(models, rewritten_request, file_ctx):
    system_prompt = """
You are a SAFE Linux DevOps automation planner.
RETURN JSON ONLY with 'description', 'commands', 'output_file'.
"""
    return call_with_fallback(
        models,
        system_prompt,
        {"rewritten_request": rewritten_request, "project_context": file_ctx or {}}
    )

########################################
# EXECUTE — SAFE MODE
########################################
def execute_plan(plan):
    commands = plan.get("commands", [])
    if not isinstance(commands, list):
        commands = []

    if len(commands) == 0:
        return {
            "mode": "NO_EXEC",
            "description": plan.get("description", "No commands to execute")
        }

    progress("⏳ 명령어 실행 중 (root)")
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
            "stderr": proc.stderr.strip()
        })

    return {
        "mode": "EXECUTE",
        "description": plan.get("description"),
        "results": results,
        "saved_to": plan.get("output_file")
    }

########################################
# REPORT — ALWAYS JSON
########################################
def generate_report(models, rewritten_request, file_ctx):
    system_prompt = """
You are a Korean Linux/DevOps technical explainer.
RETURN JSON ONLY: {"summary": "string", "steps": ["string", ...], "risk": "low | medium | high"}
"""
    res = call_with_fallback(
        models,
        system_prompt,
        {"rewritten_request": rewritten_request, "project_context": file_ctx or {}}
    )
    return {"mode": "REPORT", "report": res}

########################################
# Main handler
########################################
def handle_input(user_input):
    file_ctx = load_file_context() if should_attach_context(user_input) else {}
    cls = classify_request(user_input, file_ctx)
    nature = cls.get("nature", "unknown")

    if cls.get("confidence", 0.0) < CONFIDENCE_THRESHOLD:
        nature = "unknown"

    models = MODEL_CHAINS.get(nature, MODEL_CHAINS["unknown"])
    rewritten = cls.get("rewritten_request", user_input)

    if nature == "explanatory" or is_report_mode(user_input):
        return generate_report(models, rewritten, file_ctx)

    plan = build_execution_plan(models, rewritten, file_ctx)
    return execute_plan(plan)

########################################
# Service Management (무한 재시작 해결 루프)
########################################
def run_as_service():
    """인자 없이 실행 시 systemd에서 죽지 않고 대기하도록 하는 루프"""
    logger.info("MCP 서비스가 가동되었습니다. (대기 모드)")
    
    # 종료 시그널 처리
    stop_signal = False
    def signal_handler(sig, frame):
        nonlocal stop_signal
        logger.info("종료 시그널 수신 중...")
        stop_signal = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 서비스가 즉시 종료되지 않도록 무한 루프 유지
    while not stop_signal:
        time.sleep(1)
    
    logger.info("MCP 서비스가 안전하게 종료되었습니다.")

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
        print("=== MCP CLI Mode ===")
        while True:
            text = input("\nMCP> ").strip()
            if text.lower() in ("quit", "exit"):
                break
            try:
                print(json.dumps(handle_input(text), indent=2, ensure_ascii=False))
            except Exception:
                log_error(traceback.format_exc())
                print("❌ error occurred")
    elif args.text:
        try:
            result = handle_input(args.text)
            print(json.dumps(result, ensure_ascii=False))
        except Exception:
            log_error(traceback.format_exc())
            print(json.dumps({"error": "AI processing failed"}, ensure_ascii=False))
    else:
        # 인자 없이 실행 시 서비스 모드 (Restart Loop 해결책)
        run_as_service()

if __name__ == "__main__":
    main()#!/usr/bin/env python3
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

# 로깅 설정 (systemctl 및 journalctl 연동용)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
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
# Report detection keywords
########################################
REPORT_KEYWORDS = [
    "report mode",
    "report_only",
    "--report",
    "[report]"
]

########################################
# Context trigger keywords
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
# Cache
########################################
CLASSIFY_CACHE = {}

########################################
# Logging / utilities
########################################
def log_error(msg):
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now()}] {msg}\n")

def progress(msg):
    # main.go에서 실시간 읽기를 위해 stderr로 출력
    print(msg, file=sys.stderr, flush=True)

########################################
# ENV load
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
# Context loader (masked)
########################################
SENSITIVE_PATTERN = re.compile(
    r"(api[_-]?key|password|secret|token|auth|authorization)",
    re.IGNORECASE
)

ALLOWED_EXT = (".py", ".sh", ".conf", ".yml", ".yaml", ".json")

def should_attach_context(user_input: str) -> bool:
    t = user_input.lower()
    return any(k.lower() in t for k in CONTEXT_TRIGGERS)

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
            data = SENSITIVE_PATTERN.sub("[MASKED]", data)
            new_total = total + len(data)
            if new_total > max_total:
                break
            ctx[path.name] = data
            total = new_total
        except Exception as e:
            log_error(f"context load fail {path}: {e}")
    return ctx

########################################
# Report mode detect
########################################
def is_report_mode(user_input):
    t = user_input.lower()
    return any(k in t for k in REPORT_KEYWORDS)

########################################
# Safe JSON load
########################################
def safe_load_json(text, default):
    try:
        # AI가 마크다운 블록을 씌우는 경우 대비
        clean_text = re.sub(r"```json\s*|\s*```", "", text).strip()
        return json.loads(clean_text)
    except Exception:
        return default

########################################
# Classifier
########################################
def classify_request(user_input: str, file_ctx=None) -> dict:
    key = (user_input, bool(file_ctx))
    if key in CLASSIFY_CACHE:
        return CLASSIFY_CACHE[key]

    system_prompt = """
You are an intent classifier and request normalizer for a Linux/DevOps AI automation system.
Your job consists of TWO tasks ONLY:
(1) CLASSIFY THE USER REQUEST
(2) NORMALIZE THE REQUEST
MANDATORY OUTPUT FORMAT: JSON ONLY.
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
        return {"nature": "unknown", "rewritten_request": user_input, "confidence": 0.0}

########################################
# Fallback invocation
########################################
def call_with_fallback(models, system_prompt, user_prompt):
    client = ollama_client()
    last = None
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
            return safe_load_json(resp["message"]["content"], {})
        except Exception as e:
            last = str(e)
            log_error(traceback.format_exc())
            progress(f"@@ {model} 실패: {last}")
    raise RuntimeError(last)

########################################
# Execution plan builder
########################################
def build_execution_plan(models, rewritten_request, file_ctx):
    system_prompt = """
You are a SAFE Linux DevOps automation planner.
RETURN JSON ONLY with 'description', 'commands', 'output_file'.
"""
    return call_with_fallback(
        models,
        system_prompt,
        {"rewritten_request": rewritten_request, "project_context": file_ctx or {}}
    )

########################################
# EXECUTE — SAFE MODE
########################################
def execute_plan(plan):
    commands = plan.get("commands", [])
    if not isinstance(commands, list):
        commands = []

    if len(commands) == 0:
        return {
            "mode": "NO_EXEC",
            "description": plan.get("description", "No commands to execute")
        }

    progress("⏳ 명령어 실행 중 (root)")
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
            "stderr": proc.stderr.strip()
        })

    return {
        "mode": "EXECUTE",
        "description": plan.get("description"),
        "results": results,
        "saved_to": plan.get("output_file")
    }

########################################
# REPORT — ALWAYS JSON
########################################
def generate_report(models, rewritten_request, file_ctx):
    system_prompt = """
You are a Korean Linux/DevOps technical explainer.
RETURN JSON ONLY: {"summary": "string", "steps": ["string", ...], "risk": "low | medium | high"}
"""
    res = call_with_fallback(
        models,
        system_prompt,
        {"rewritten_request": rewritten_request, "project_context": file_ctx or {}}
    )
    return {"mode": "REPORT", "report": res}

########################################
# Main handler
########################################
def handle_input(user_input):
    file_ctx = load_file_context() if should_attach_context(user_input) else {}
    cls = classify_request(user_input, file_ctx)
    nature = cls.get("nature", "unknown")

    if cls.get("confidence", 0.0) < CONFIDENCE_THRESHOLD:
        nature = "unknown"

    models = MODEL_CHAINS.get(nature, MODEL_CHAINS["unknown"])
    rewritten = cls.get("rewritten_request", user_input)

    if nature == "explanatory" or is_report_mode(user_input):
        return generate_report(models, rewritten, file_ctx)

    plan = build_execution_plan(models, rewritten, file_ctx)
    return execute_plan(plan)

########################################
# Service Management (무한 재시작 해결 루프)
########################################
def run_as_service():
    """인자 없이 실행 시 systemd에서 죽지 않고 대기하도록 하는 루프"""
    logger.info("MCP 서비스가 가동되었습니다. (대기 모드)")
    
    # 종료 시그널 처리
    stop_signal = False
    def signal_handler(sig, frame):
        nonlocal stop_signal
        logger.info("종료 시그널 수신 중...")
        stop_signal = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 서비스가 즉시 종료되지 않도록 무한 루프 유지
    while not stop_signal:
        time.sleep(1)
    
    logger.info("MCP 서비스가 안전하게 종료되었습니다.")

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
        print("=== MCP CLI Mode ===")
        while True:
            text = input("\nMCP> ").strip()
            if text.lower() in ("quit", "exit"):
                break
            try:
                print(json.dumps(handle_input(text), indent=2, ensure_ascii=False))
            except Exception:
                log_error(traceback.format_exc())
                print("❌ error occurred")
    elif args.text:
        try:
            result = handle_input(args.text)
            print(json.dumps(result, ensure_ascii=False))
        except Exception:
            log_error(traceback.format_exc())
            print(json.dumps({"error": "AI processing failed"}, ensure_ascii=False))
    else:
        # 인자 없이 실행 시 서비스 모드 (Restart Loop 해결책)
        run_as_service()

if __name__ == "__main__":
    main()

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

########################################
# 기본 경로 설정 (기존 유지)
########################################
MCP_DIR = Path("/home/ubuntu/mcp")
LOG_FILE = MCP_DIR / "error.log"
STATE_FILE = MCP_DIR / "state.json"
ENV_FILE = "/etc/mcp.env"
OLLAMA_MODEL = "gpt-oss:120b"

########################################
# 실행 상태
########################################
LAST_REPORTED_COMMAND = None

REPORT_KEYWORDS = [
    "report mode",
    "report_only",
    "report-only",
    "--report",
    "[report]"
]

########################################
# 공통 유틸
########################################
def log_error(msg: str):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now()}] {msg}\n")

########################################
# 환경변수 로딩 (기존 유지)
########################################
def ensure_env_loaded():
    if os.environ.get("OLLAMA_API_KEY"):
        return

    if not os.path.exists(ENV_FILE):
        log_error("Environment file not found: /etc/mcp.env")
        return

    try:
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)
    except Exception as e:
        log_error(f"Failed to load env file: {e}")

########################################
# 상태 하트비트 (기존 유지)
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
# 판단 로직 (NEW)
########################################
def is_report_mode(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in REPORT_KEYWORDS)

def strip_report_keywords(cmd: str) -> str:
    for k in REPORT_KEYWORDS:
        cmd = cmd.replace(k, "")
    return cmd.strip()

########################################
# LLM (REPORT 전용, 선택적)
########################################
def call_llm_for_report(prompt: str) -> str:
    try:
        api_key = os.environ.get("OLLAMA_API_KEY")
        if not api_key:
            return "LLM API Key가 설정되지 않았습니다."

        client = Client(
            host="https://ollama.com",
            headers={"Authorization": f"Bearer {api_key}"}
        )

        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": "운영자에게 설명하는 보고용 요약만 생성하세요."},
                {"role": "user", "content": prompt},
            ],
            stream=False
        )

        return response["message"]["content"]

    except Exception as e:
        log_error(f"LLM report error: {e}")
        return "LLM 보고 생성 중 오류 발생"

########################################
# EXECUTE (root)
########################################
def execute_command(command: str) -> dict:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            timeout=60
        )

        return {
            "mode": "EXECUTE",
            "command": command,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip()
        }

    except Exception as e:
        log_error(f"Execution error: {e}")
        return {
            "mode": "EXECUTE",
            "error": str(e)
        }

########################################
# REPORT_ONLY
########################################
def report_only(raw_input: str) -> dict:
    global LAST_REPORTED_COMMAND

    cleaned = strip_report_keywords(raw_input)
    LAST_REPORTED_COMMAND = cleaned

    llm_summary = call_llm_for_report(
        f"다음 명령을 실행하기 전 점검 관점에서 설명하세요:\n{cleaned}"
    )

    return {
        "mode": "REPORT_ONLY",
        "요청_내용": raw_input,
        "실행_예정_명령": cleaned,
        "설명": (
            "현재 요청은 report mode로 처리되었습니다.\n"
            "아래 명령은 EXECUTE 모드였다면 root 권한으로 실행됩니다.\n\n"
            f"[LLM 요약]\n{llm_summary}\n\n"
            "실행 방법:\n"
            "  run         : 실행\n"
            "  run --force : 확인 없이 실행"
        )
    }

########################################
# 출력
########################################
def print_execute(r: dict):
    print("\n=== EXECUTE RESULT ===")
    print(f"command    : {r.get('command')}")
    print(f"returncode : {r.get('returncode')}")
    if r.get("stdout"):
        print("\n[STDOUT]\n" + r["stdout"])
    if r.get("stderr"):
        print("\n[STDERR]\n" + r["stderr"])
    print("======================\n")

def print_report(r: dict):
    print("\n=== REPORT MODE ===")
    print(f"요청 내용 : {r['요청_내용']}")
    print("\n[실행 예정 명령]")
    print(r["실행_예정_명령"])
    print("\n[설명]")
    print(r["설명"])
    print("===================\n")

########################################
# CLI / STDIO 공용
########################################
def process_input(text: str):
    global LAST_REPORTED_COMMAND

    if text.lower() == "run --force":
        if not LAST_REPORTED_COMMAND:
            return {"error": "실행할 report 명령 없음"}
        result = execute_command(LAST_REPORTED_COMMAND)
        LAST_REPORTED_COMMAND = None
        return result

    if text.lower() == "run":
        if not LAST_REPORTED_COMMAND:
            return {"error": "실행할 report 명령 없음"}
        result = execute_command(LAST_REPORTED_COMMAND)
        LAST_REPORTED_COMMAND = None
        return result

    if is_report_mode(text):
        return report_only(text)

    return execute_command(text)

########################################
# CLI 모드
########################################
def run_cli_mode():
    print("=== MCP CLI MODE (Hybrid) ===")
    while True:
        try:
            text = input("\nMCP> ").strip()
            if text.lower() in ("quit", "exit"):
                return
            result = process_input(text)
            if result.get("mode") == "REPORT_ONLY":
                print_report(result)
            elif result.get("mode") == "EXECUTE":
                print_execute(result)
            else:
                print(result)
        except Exception as e:
            log_error(str(e))
            print("오류 발생")

########################################
# STDIO 모드
########################################
def run_stdio_mode():
    while True:
        try:
            text = input()
            if not text:
                continue
            result = process_input(text)
            print(json.dumps(result))
        except EOFError:
            return

########################################
# Main
########################################
def main():
    if os.geteuid() != 0:
        print("❌ MCP must be run as root")
        return

    ensure_env_loaded()

    threading.Thread(target=update_heartbeat, daemon=True).start()

    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", action="store_true")
    args = parser.parse_args()

    if args.cli:
        run_cli_mode()
    else:
        run_stdio_mode()

if __name__ == "__main__":
    main()

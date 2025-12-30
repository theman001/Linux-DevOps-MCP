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
PROMPT_DIR = BASE_DIR / "prompts"
LOG_FILE = BASE_DIR / "error.log"
ENV_FILE = "/etc/mcp.env"

########################################
# Logging
########################################
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("MCP")

########################################
# Models
########################################
MODEL_CLASSIFIER = "nemotron-3-nano:30b-cloud"

MODEL_CHAINS = {
    "server_operation": ["gpt-oss:120b", "qwen3-next:80b"],
    "code_generation": ["devstral-2:123b-cloud", "qwen3-coder:480b-cloud"],
    "explanatory": ["gemini-3-flash-preview:cloud", "mistral-large-3"],
    "unknown": ["ministral-3:14b", "glm-4.6"],
}

CONFIDENCE_THRESHOLD = 0.6


########################################
# ENV LOAD
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
# OLLAMA CLIENT
########################################
def ollama_client():
    return Client(
        host="https://ollama.com",
        headers={"Authorization": f"Bearer {os.environ.get('OLLAMA_API_KEY')}"}
    )


########################################
# PROMPT LOADER
########################################
def load_prompt(name):
    path = PROMPT_DIR / name
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"❌ 프롬프트 로드 실패: {name} — {e}")
        return ""


########################################
# SAFE JSON PARSE
########################################
def safe_json(text, default=None):
    try:
        clean = re.sub(r"```json|```", "", text).strip()
        return json.loads(clean)
    except Exception:
        return default


########################################
# FRIENDLY PROGRESS PRINT
########################################
def step(msg):
    print(f"\n🔹 {msg}", flush=True)


########################################
# MODEL CALL WITH FALLBACK
########################################
def call_with_fallback(models, system_prompt, user_payload):
    client = ollama_client()
    last_error = None

    for m in models:
        try:
            step(f"모델 호출: {m}")
            resp = client.chat(
                model=m,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
                ],
                format="json",
                stream=False
            )
            return safe_json(resp["message"]["content"], {})
        except Exception as e:
            last_error = str(e)
            logger.error(traceback.format_exc())
            step(f"⚠️ {m} 호출 실패 — 다음 모델로 대체 시도")

    raise RuntimeError(last_error)


########################################
# CLASSIFIER
########################################
def classify(user_text):
    step("요청 분류 중… (Classifier 호출)")

    system_prompt = load_prompt("classifier.txt")

    client = ollama_client()

    try:
        resp = client.chat(
            model=MODEL_CLASSIFIER,
            messages=[
                {"role":"system","content":system_prompt},
                {"role":"user","content":user_text}
            ],
            format="json",
            stream=False
        )
    except Exception as e:
        print("❌ 분류 모델 호출 실패:", e)
        return {"category":"unknown","confidence":0.0,"needs_context":False,"reason":"classifier error"}

    result = safe_json(resp["message"]["content"], None)

    if not result:
        print("⚠️ Classifier 응답 JSON 파싱 실패 — unknown 처리")
        return {"category":"unknown","confidence":0.0,"needs_context":False,"reason":"parse failed"}

    return result


########################################
# PLAN BUILDER
########################################
def build_plan(category, rewritten, ctx):
    system_prompt = load_prompt("planner.txt")
    models = MODEL_CHAINS.get(category, MODEL_CHAINS["unknown"])

    return call_with_fallback(
        models,
        system_prompt,
        {"rewritten_request": rewritten, "context": ctx}
    )


########################################
# REPORT
########################################
def build_report(category, rewritten, ctx):
    system_prompt = load_prompt("reporter.txt")
    models = MODEL_CHAINS.get(category, MODEL_CHAINS["unknown"])

    return call_with_fallback(
        models,
        system_prompt,
        {"rewritten_request": rewritten, "context": ctx}
    )


########################################
# EXECUTION
########################################
def execute(plan):
    commands = plan.get("commands", [])
    if not commands:
        return {"mode":"NO_EXEC","description":"실행할 명령이 없습니다."}

    results = []

    step("명령 실행 중…")

    for cmd in commands:
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True
        )

        result = {
            "command": cmd,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip()
        }

        if proc.returncode != 0:
            print(f"\n❌ 명령 실패: {cmd}")
            print(f"stderr: {proc.stderr.strip()}")

        results.append(result)

    return {
        "mode":"EXECUTE",
        "description":plan.get("description"),
        "results":results,
        "saved_to":plan.get("output_file")
    }


########################################
# PRETTY PRINT
########################################
def pretty_print(result):
    mode = result.get("mode")

    if mode == "EXECUTE":
        print("\n🛠 실행 완료")
        print("📄 설명:", result.get("description","-"))

        for r in result.get("results",[]):
            print(f"\n🔹 {r['command']}")
            print(f"➡️ 코드: {r['returncode']}")
            if r['stdout']:
                print(r['stdout'])
            if r['stderr']:
                print("⚠️", r['stderr'])

        if result.get("saved_to"):
            print("\n💾 저장 위치:", result["saved_to"])

    elif mode == "REPORT":
        print("\n📘 기술 설명 보고서 생성 완료\n")
        rep = result["report"]
        print("📝 요약:", rep.get("summary"))
        print("\n📌 단계별 설명:")
        for s in rep.get("steps",[]):
            print(" -", s)
        print("\n⚠️ 위험도:", rep.get("risk"))

    else:
        print("\nℹ️", result.get("description","실행 없음"))


########################################
# HANDLE USER INPUT
########################################
def handle_input(text):

    cls = classify(text)

    category = cls.get("category","unknown")
    conf = cls.get("confidence",0.0)

    print(f"\n📌 분류 결과 — category={category}, confidence={conf}")

    if conf < CONFIDENCE_THRESHOLD:
        category = "unknown"

    # context load는 이후 추가 가능 (지금은 빈 dict)
    ctx = {}

    rewritten = text

    if category == "explanatory":
        rep = build_report(category, rewritten, ctx)
        pretty_print({"mode":"REPORT","report":rep})
    else:
        plan = build_plan(category, rewritten, ctx)
        if not isinstance(plan,dict) or "commands" not in plan:
            print("\n⚠️ 실행계획 JSON 구조 오류")
            return
        res = execute(plan)
        pretty_print(res)


########################################
# SERVICE LOOP
########################################
def run_as_service():
    logger.info("MCP Service Running…")
    stop = False

    def sig(_sig,_frm):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT,sig)
    signal.signal(signal.SIGTERM,sig)

    while not stop:
        time.sleep(1)

    logger.info("MCP Service Exit")


########################################
# MAIN
########################################
def main():
    ensure_env_loaded()

    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", action="store_true")
    parser.add_argument("--text", type=str)
    args = parser.parse_args()

    if args.cli:
        print("=== MCP CLI MODE ===")
        while True:
            text = input("\nMCP> ").strip()
            if text in ("quit","exit"):
                break
            try:
                handle_input(text)
            except Exception:
                logger.error(traceback.format_exc())
                print("\n❌ 내부 오류 발생")

    elif args.text:
        try:
            handle_input(args.text)
        except Exception:
            logger.error(traceback.format_exc())
            print("\n❌ 처리 실패")

    else:
        run_as_service()


if __name__ == "__main__":
    main()

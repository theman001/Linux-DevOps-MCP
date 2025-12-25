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
# MCP DIR (자동 감지 + ENV override)
########################################
if os.environ.get("MCP_DIR"):
    MCP_DIR = Path(os.environ["MCP_DIR"]).expanduser().resolve()
else:
    MCP_DIR = Path(__file__).resolve().parent

MCP_DIR.mkdir(parents=True, exist_ok=True)

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
    print(f"⏳ {msg}", file=sys.stderr, flush=True)

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
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k,v=line.split("=",1)
            os.environ.setdefault(k,v)

########################################
# Heartbeat
########################################
def update_heartbeat():
    while True:
        try:
            STATE_FILE.write_text(json.dumps({
                "last_heartbeat": time.time(),
                "status":"running"
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
        headers={"Authorization":f"Bearer {os.environ.get('OLLAMA_API_KEY')}"}
    )

########################################
# report mode 룰 체크
########################################
def is_report_mode(user_input:str)->bool:
    t=user_input.lower()
    return any(k in t for k in REPORT_KEYWORDS)

########################################
# 1차 분류 (nemotron)
########################################
CLASSIFIER_PROMPT = r"""
You are an intent classification and request rewriting engine
for an automated infrastructure control system.

Your job:
1. Understand the user's natural language request
2. Rewrite it into a concise, unambiguous task description
3. Classify into one of ONLY these categories:

- server_operation
- code_generation
- explanatory
- unknown

DISAMBIGUATION RULES:
- If the user explicitly requests a Python script, default to code_generation
  unless the script is only a thin wrapper around shell execution.
- If both development and OS operation are present,
  choose code_generation when application-level logic is needed.
- If unsure, choose unknown.

Output ONLY valid JSON in this shape:

{
  "nature": "server_operation | code_generation | explanatory | unknown",
  "rewritten_request": "concise cleaned request",
  "confidence": 0.0
}

No markdown. No comments. No explanations.
"""

def classify_request(user_input:str)->dict:
    if user_input in CLASSIFY_CACHE:
        return CLASSIFY_CACHE[user_input]

    user_prompt = f"""
User request:
{user_input}
"""

    try:
        progress("요청 분류 중 (nemotron-3-nano)")
        client = ollama_client()
        resp = client.chat(
            model=MODEL_CLASSIFIER,
            messages=[
                {"role":"system","content":CLASSIFIER_PROMPT},
                {"role":"user","content":user_prompt}
            ],
            format="json",
            stream=False
        )
        result = json.loads(resp["message"]["content"])
        CLASSIFY_CACHE[user_input]=result
        return result
    except Exception:
        log_error(traceback.format_exc())
        return {
            "nature":"unknown",
            "rewritten_request":user_input,
            "confidence":0.0
        }

########################################
# 카테고리별 SYSTEM PROMPTS
########################################
PROMPT_SERVER_OP = r"""
You are a senior Linux / DevOps / SRE engineer.

Your job:
Convert the user's request into a SAFE execution plan.

VERY IMPORTANT SAFETY RULES
------------------------------------------------
1. DO NOT embed shell syntax into source code
2. DO NOT use heredoc (<<EOF)
3. DO NOT write redirection (> or >>)
4. DO NOT include Markdown in the JSON
5. DO NOT actually execute commands
6. Return ONLY JSON
------------------------------------------------

Return JSON exactly in this schema:

{
  "description": "high level explanation",
  "files": [
    {
      "path": "/abs/or/relative/file/path",
      "content": "file content ONLY. No shell syntax."
    }
  ],
  "commands": [
    "linux shell commands ONLY",
    "never include code here"
  ],
  "output_file": "null or filename"
}

All source code MUST go inside files[].content.
All shell commands MUST go inside commands[].
Nothing may mix the two.
"""

PROMPT_CODE_GEN = r"""
You are a professional software engineer.

Your task:
Generate source code or scripts cleanly and safely.

RULES
------------------------------------------------
1. DO NOT use heredoc syntax
2. DO NOT embed shell syntax into source code
3. DO NOT include markdown fences
4. All code MUST be returned ONLY inside files[].content
5. Shell commands belong ONLY in commands[]
------------------------------------------------

Return JSON in this schema ONLY:

{
  "description": "what the program does",
  "files": [
    {
      "path": "filename.ext",
      "content": "program code ONLY"
    }
  ],
  "commands": [
    "commands to run or prepare the program"
  ],
  "output_file": "or null"
}
"""

PROMPT_EXPLANATORY = r"""
You are a Korean technical writer.

Explain the user's request clearly and simply in Korean.
Do NOT return JSON. Do NOT include code.
"""

PROMPT_UNKNOWN = r"""
User intent unclear.
Return JSON:

{
 "error": "intent unclear",
 "missing_information": []
}
"""

########################################
# LLM 호출 (자동 스위칭)
########################################
def call_with_fallback(models:list[str], system_prompt:str, user_prompt:str)->dict:
    last_error=None
    client=ollama_client()

    for model in models:
        try:
            progress(f"## {model} 에 요청")
            resp = client.chat(
                model=model,
                messages=[
                    {"role":"system","content":system_prompt},
                    {"role":"user","content":user_prompt}
                ],
                format="json",
                stream=False
            )
            return json.loads(resp["message"]["content"])
        except Exception as e:
            last_error=str(e)
            progress(f"@@ {model} 실패 (사유: {last_error})")
            log_error(traceback.format_exc())

    raise RuntimeError(f"All models failed. Last error={last_error}")

########################################
# 실행 계획 생성
########################################
def build_execution_plan(nature:str, rewritten:str)->dict:
    if nature=="server_operation":
        prompt=PROMPT_SERVER_OP
    elif nature=="code_generation":
        prompt=PROMPT_CODE_GEN
    elif nature=="explanatory":
        return {"mode":"REPORT_REQUEST","rewritten_request":rewritten}
    else:
        prompt=PROMPT_UNKNOWN

    models = MODEL_CHAINS.get(nature, MODEL_CHAINS["unknown"])
    return call_with_fallback(models, prompt, rewritten)

########################################
# EXECUTE
########################################
def execute_plan(plan:dict)->dict:
    progress("명령 실행 준비")

    results=[]

    for f in plan.get("files",[]):
        path=f["path"]
        content=f.get("content","")
        p=Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p,"w") as fp:
            fp.write(content)

    for cmd in plan.get("commands",[]):
        proc=subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        results.append({
            "command":cmd,
            "returncode":proc.returncode,
            "stdout":proc.stdout.strip(),
            "stderr":proc.stderr.strip()
        })

    return {
        "mode":"EXECUTE",
        "description":plan.get("description"),
        "results":results
    }

########################################
# REPORT
########################################
def generate_report(text:str)->dict:
    client=ollama_client()
    resp=client.chat(
        model="gemini-3-flash-preview:cloud",
        messages=[
            {"role":"system","content":PROMPT_EXPLANATORY},
            {"role":"user","content":text}
        ]
    )
    return {
        "mode":"REPORT",
        "report":resp["message"]["content"]
    }

########################################
# 메인 처리
########################################
def handle_input(user_input:str)->dict:
    report_mode=is_report_mode(user_input)
    cls=classify_request(user_input)

    nature=cls.get("nature","unknown")
    if cls.get("confidence",0.0)<CONFIDENCE_THRESHOLD:
        nature="unknown"

    rewritten=cls.get("rewritten_request",user_input)

    if report_mode or nature=="explanatory":
        return generate_report(rewritten)

    plan=build_execution_plan(nature,rewritten)

    if plan.get("mode")=="REPORT_REQUEST":
        return generate_report(rewritten)

    return execute_plan(plan)

########################################
# CLI
########################################
def run_cli():
    print("=== MCP CLI ===")
    while True:
        try:
            text=input("\nMCP> ").strip()
            if text.lower() in ("quit","exit"):
                return
            result=handle_input(text)
            print(json.dumps(result,indent=2,ensure_ascii=False))
        except Exception:
            log_error(traceback.format_exc())
            print("❌ error occurred")

########################################
# Main
########################################
def main():
    if os.geteuid()!=0:
        print("❌ MUST RUN AS ROOT",file=sys.stderr)
        return

    ensure_env_loaded()
    threading.Thread(target=update_heartbeat,daemon=True).start()

    parser=argparse.ArgumentParser()
    parser.add_argument("--cli",action="store_true")
    args=parser.parse_args()

    if args.cli:
        run_cli()

if __name__=="__main__":
    main()
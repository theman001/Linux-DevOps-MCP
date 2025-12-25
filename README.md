# Linux-DevOps-MCP

Linux-DevOps-MCP는 **자연어 기반으로 리눅스 서버 운영 작업을 수행할 수 있도록 설계된 MCP(Model Context Protocol) 서버**입니다.

이 프로젝트는 단순 쉘 실행 도구가 아니라,

> **운영자의 의도를 이해 → 작업 성격을 분석 → 실행 계획을 수립 → root 권한으로 안전하게 실행까지 수행하는**
>
> DevOps·운영 자동화 전용 AI 에이전트입니다.

---

## 🚀 핵심 동작 흐름

Linux-DevOps-MCP는 다음과 같이 동작합니다.

1️⃣ 사용자가 자연어로 요청  
2️⃣ **1차 LLM(nemotron-3-nano)** 이 요청을 분석 → 성격(Nature) 분류 & 내용을 정리  
3️⃣ 성격에 맞는 **전용 LLM 체인(자동 스위칭 포함)** 으로 라우팅  
4️⃣ **실행이 필요한 경우 “실행 계획(JSON)”을 생성**  
5️⃣ root 권한으로 실제 Linux 명령어 실행  
6️⃣ JSON 결과 & 필요 시 파일 저장  

---

## ⚙️ 실행 모드 (Mode)

### 🟢 **EXECUTE 모드 — 기본값**
✔ 실제 명령어 실행  
✔ 결과 JSON 반환  
✔ 필요하면 파일 저장  

예)
```
리눅스 서버 상태 점검하고 결과를 result.txt 에 저장해
```

---

### 🔵 **REPORT 모드 — 설명 전용**
✔ **실제 실행 없이 설명만 제공**  
✔ 운영 절차·가이드·문서 작성에 적합  

REPORT 모드는 **요청 문자열에 아래 키워드가 포함될 때만 활성화됩니다.**

- report mode  
- report_only  
- --report  
- [report]  

예)
```
리눅스 서버 일일 점검 절차를 정리해줘 --report
```

---

## 🧠 요청 성격 분류 (Nature)

요청은 아래 카테고리 중 하나로 자동 분류됩니다.

| Nature | 설명 |
|-------|------|
| server_operation | 서버 운영/점검/서비스 관리/로그 분석 |
| code_generation | 스크립트/설정/코드 생성 |
| explanatory | 설명/문서화/가이드 |
| unknown | 분류 불가 – 안전 Fallback |

⚠️ 분류 결과는 **“모델 선택용”이며 실행 여부를 결정하지는 않습니다.**

---

## 🧩 모델 구조

### 🔹 **1차 분류 모델**
```
nemotron-3-nano:30b-cloud
```
→ 자연어 요청을 구조화 & Nature 분류

---

### 🔹 **2차 모델 (자동 스위칭 포함)**

각 카테고리별 **우선순위 체인**이 존재하며  
요청 실패 시 자동으로 다음 후보로 전환됩니다.

```python
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
```

---

### 🔁 **자동 스위칭 메시지 예시**
```
## devstral-2:123b-cloud 에 요청
@@ devstral-2:123b-cloud 에 요청 실패 (사유: 502 Server Error)
## qwen3-coder:480b-cloud 에 요청
```

---

## 🔐 실행 권한 정책

✔ **항상 root 권한으로 실행되어야 합니다**  
✔ 모든 명령어는 root 권한으로 수행됩니다  
✔ 요청에 sudo 붙일 필요 없습니다  

---

## 🏗 실행 구조

### CLI 실행

```
sudo ./mcp_server.py --cli
```

종료:

```
quit
exit
```

---

## 📤 출력 형식

### EXECUTE 모드 예시
```json
{
  "mode": "EXECUTE",
  "description": "서버 점검",
  "results": [
    {
      "command": "df -h",
      "returncode": 0,
      "stdout": "...",
      "stderr": ""
    }
  ],
  "saved_to": "result.txt"
}
```

---

### REPORT 모드 예시
```json
{
  "mode": "REPORT",
  "report": "리눅스 서버 점검 시 다음 항목을 확인해야 합니다..."
}
```

---

## ❤️ 운영 기능

### 🔥 Heartbeat (상태 저장)

`state.json`에 10초마다 상태 기록

---

### 🩺 healthcheck

서비스 정상 여부 점검 가능

```
./healthcheck_all.sh
```

---

### 🛑 idle watcher

30분 이상 heartbeat 없으면 MCP 자동 종료

---

### 🔐 Ollama Cloud 연결 확인

```
./ollama_check.sh
```

API KEY / 네트워크 / DNS 오류 구분 출력

---

## 📦 설치 구조

### Python venv 사용
```
Linux-DevOps-MCP/mcp-venv
```

### systemd 서비스 실행
```
/etc/systemd/system/mcp.service
```

---

## 📁 설치 경로

> **⚠️ 중요**
>
> 이 프로젝트는 **특정 디렉토리에 묶이지 않습니다.**
>
> 어느 디렉토리에 clone 하든 정상 동작하도록 설계되었습니다.

---

## 🛠 설치 방법

```
sudo ./setup_mcp.sh
```

자동 수행 내용:
✔ venv 생성  
✔ requirements 설치  
✔ /etc/mcp.env 생성  
✔ systemd 등록  
✔ Ollama Cloud 연결 검증  

---

## 🔄 업데이트

```
sudo ./update_mcp.sh
```

---

## 🗑 제거 (정리)

```
sudo ./cleanup_mcp.sh
```

✔ API KEY 포함 전체 삭제 가능  
✔ **최종 디렉토리 삭제 여부는 사용자에게 확인 후 진행**

---

## 🧪 MCP 사용 예시

👍 적합

✔ 서버 전반 점검  
✔ 로그 분석  
✔ 배포 자동화  
✔ 스크립트 생성  
✔ 운영 가이드 문서화  

---

## ⚠️ 비권장 사용

🚫 단순 명령 실행:

```
ls
pwd
cd /tmp
```

MCP는

> **“판단이 필요한 운영작업”에 최적화된 도구입니다.**

---

## 🧭 설계 철학

✔ 실행 여부는 규칙 기반  
✔ LLM은 의사결정·계획에만 사용  
✔ Root 운영 안정성 최우선  
✔ 자동화 친화적 JSON 결과  
✔ 장애 대비 — 모델 자동 스위칭  
✔ 운영 관점 추적 가능 로그  

---

## 📌 요약

Linux-DevOps-MCP는

> **“명령어 대신 쳐주는 봇”이 아니라**
>
> **운영자의 생각을 실행 가능한 운영 작업으로 바꿔주는 AI 운영 에이전트입니다.**

---

## 👤 Author
김태욱
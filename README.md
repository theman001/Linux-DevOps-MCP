# Linux-DevOps-MCP

⚠️ **중요 공지 (Security Notice)**  
본 프로젝트의 현재 구현은 **LLM이 생성한 명령을 실제로 실행할 수 있는 구조를 포함**하고 있습니다.  
운영 환경에서 사용 시 반드시 본 문서의 *Security Model*과 *Safe Usage Guidelines*를 숙지하십시오.

---

## Overview

Linux-DevOps-MCP는  
**LLM(Model)을 활용하여 서버 운영 판단 및 조치를 자동화하기 위한 MCP(Model Context Protocol) 서버**입니다.

이 프로젝트는 다음을 목표로 합니다:

- 시스템 상태(Context) 수집 및 구조화
- 장애 이력 및 패턴 기반 판단
- LLM을 통한 **운영 조치(action) 제안 또는 실행**
- Always Free / 저사양 서버 환경에서의 실험적 DevOps 자동화

> ❗ 본 프로젝트는 **연구·실험 목적**이며, 기본 설정 상태에서 **실제 명령 실행이 발생할 수 있습니다**.

---

## Architecture Overview (Current Implementation)

```
User Request
     ↓
MCP Server
     ↓
Context Builder (state / incidents / patterns)
     ↓
LLM (Ollama / Cloud)
     ↓
Structured JSON Response
     ↓
Decision Engine
     ↓
Action Executor (⚠️ shell command execution 가능)
```

---

## How MCP Uses LLM (Actual Behavior)

LLM은 다음과 같은 **구조화된 JSON 응답**을 반환하도록 설계되어 있습니다:

```json
{
  "decision": "APPLY_FIX | REPORT_ONLY | NO_ACTION",
  "reason": "string",
  "actions": [
    {
      "type": "shell | edit_file",
      "command": "string"
    }
  ]
}
```

### Current Behavior
- `decision == APPLY_FIX`
- `action.type == "shell"`

인 경우, MCP 서버는 **`subprocess.run(..., shell=True)`를 통해 명령을 실제 실행**합니다.

✔ 예시:
```
User: aa.txt 생성해줘
LLM: touch aa.txt
MCP: 실제로 aa.txt 생성됨
```

---

## ⚠️ Security Model (현재 상태 기준)

### 현재 포함된 보안 특성

| 항목 | 상태 |
|---|---|
| LLM 명령 실행 | ✅ 가능 |
| Allowlist / Denylist | ❌ 없음 |
| Human Approval | ❌ 없음 |
| Sandbox 실행 | ❌ 없음 |
| shell=True 사용 | ⚠️ 사용 중 |

👉 즉, **LLM 응답은 신뢰된 입력으로 취급됩니다.**

---

## Known Risks

- 프롬프트 인젝션에 의한 임의 명령 실행
- LLM hallucination → 파괴적 명령 실행
- `rm`, `shutdown`, `curl | bash` 등의 위험 명령 가능성
- 외부 입력과 결합 시 RCE 위험

---

## Safe Usage Guidelines (강력 권장)

운영 환경에서 사용 시 반드시 다음 중 하나 이상을 적용하십시오:

### 1️⃣ 실행 비활성화 (권장)
```python
# apply_actions() 호출 제거 또는
# decision == APPLY_FIX 분기 차단
```

### 2️⃣ Allowlist 기반 명령 제한
```text
허용 예:
- systemctl status *
- df -h
- free -m
```

### 3️⃣ Human-in-the-loop 승인
```
LLM Action: restart nginx
Require approval: YES / NO
```

### 4️⃣ Sandbox / 제한 계정 실행
- root ❌
- 제한된 사용자 계정 ✔
- 컨테이너 / chroot ✔

---

## LLM-less Fallback Mode

- LLM 미사용 시 MCP는 **상태 수집 및 기록만 수행**
- 실행 로직은 호출되지 않음
- 운영 가시성 유지 가능

---

## State Files

| 파일 | 설명 |
|---|---|
| state.json | 현재 시스템 상태 |
| incidents.json | 장애 이력 |
| patterns.json | 학습된 패턴 |

---

## Example Operational Scenario (Current)

### 파일 생성 요청

```
User: aa.txt 생성해줘
LLM: touch aa.txt
MCP: shell 명령 실행 → aa.txt 생성
```

⚠️ **이 동작은 의도된 현재 구현이며, 안전하지 않을 수 있습니다.**

---

## Design Philosophy (Revised)

- MCP는 **실행 가능한 에이전트**로 동작할 수 있음
- 그러나:
  - 실행 책임은 운영자에게 있음
  - 보안 제어는 필수
- 본 프로젝트는 **실험적 자동화 프레임워크**임

---

## Non-Goals

- ❌ 무조건적인 완전 자동 운영
- ❌ 무검증 자가 치유 시스템
- ❌ 보안 솔루션 대체

---

## Disclaimer

이 프로젝트는 **연구 및 실험 목적**으로 제공됩니다.  
실제 운영 환경에서 사용 시 발생하는 모든 결과에 대한 책임은 사용자에게 있습니다.

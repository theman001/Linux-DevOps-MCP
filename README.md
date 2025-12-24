# Linux-DevOps-MCP

Linux-DevOps-MCP는 자연어 기반으로 리눅스 서버 운영 작업을 수행할 수 있도록 설계된 MCP(Model Context Protocol) 서버입니다.

이 프로젝트의 목적은 단순히 명령어를 대신 실행하는 것이 아니라,  
**운영자의 의도를 이해하고 → 필요한 작업을 판단 → 실행 계획을 수립 → 실제 작업을 수행**하는  
DevOps 전용 AI 운영 에이전트를 제공하는 것입니다.

---

## 핵심 개념

Linux-DevOps-MCP는 다음과 같은 흐름으로 동작합니다.

1. 사용자가 자연어로 요청
2. 1차 LLM이 요청을 분석하여 의도와 성격(nature)을 분류
3. 분류 결과에 따라 적절한 2차 LLM으로 라우팅
4. 실행이 필요한 경우 실행 계획을 생성
5. root 권한으로 실제 명령어 실행
6. 결과를 JSON 형태로 반환하거나 파일로 저장

---

## 실행 모드 개념

이 MCP 서버에는 두 가지 동작 모드가 있습니다.

### 1. EXECUTE 모드 (기본)

- 기본 동작 방식
- 실제 서버 명령어를 실행함
- 결과를 JSON 및 파일로 반환

예시 요청:
`서버 전반 상태를 점검하고 결과를 result.txt에 저장해`

---

### 2. REPORT 모드 (설명 전용)

- 실제 명령어를 실행하지 않음
- 작업 절차나 점검 방법을 자연어로 설명
- **오직 요청 문자열에 report 관련 키워드가 있을 때만 활성화**

REPORT 모드 트리거 키워드:
- report mode
- report_only
- --report
- [report]

예시 요청:
`리눅스 서버 일일 점검 절차를 정리해줘 report mode`

---

## 요청 분류 (Nature)

요청의 성격은 1차 분류 모델에 의해 다음 중 하나로 분류됩니다.

- server_operation  
  서버 상태 점검, 서비스 관리, 로그 분석 등 운영 작업

- code_generation  
  스크립트, 설정 파일, 코드 생성 요청

- explanatory  
  설명, 절차 정리, 문서화 성격의 요청

- unknown  
  명확히 분류되지 않는 요청 (fallback)

※ 이 분류는 **모델 선택을 위한 힌트**일 뿐이며  
실행 여부를 결정하지 않습니다.

---

## 모델 라우팅 정책

요청 분류 결과에 따라 다음과 같이 LLM이 선택됩니다.

- server_operation → gpt-oss:120b  
- code_generation → devstral-2:123b-cloud  
- explanatory → gemini-3-flash-preview:cloud  
- unknown → ministral-3:14b  

1차 분류는 항상 nemotron-3-nano 모델을 사용합니다.

---

## 실행 권한

- MCP 서버는 **반드시 root 권한으로 실행되어야 합니다**
- MCP 내부에서 실행되는 모든 명령어는 root 권한으로 수행됩니다
- sudo를 개별 명령어에 붙일 필요는 없습니다

---

## 실행 방법

CLI 모드로 실행:

`sudo ./mcp_server.py --cli`

종료:
`quit` 또는 `exit`

---

## 출력 형식

### EXECUTE 모드 결과 예시

`{
  "mode": "EXECUTE",
  "description": "서버 상태 점검",
  "results": [
    {
      "command": "df -h",
      "returncode": 0,
      "stdout": "...",
      "stderr": ""
    }
  ],
  "saved_to": "result.txt"
}`

---

### REPORT 모드 결과 예시

`{
  "mode": "REPORT",
  "report": "리눅스 서버 점검 시 다음 항목을 확인해야 합니다..."
}`

---

## MCP를 사용하는 적절한 예시

- 서버 전반 점검
- 장애 원인 분석
- 로그 패턴 분석
- 반복적인 운영 작업 자동화
- 운영 절차 문서화
- “무엇을 점검해야 할지 애매한 상황”에서의 판단 보조

---

## MCP에 적합하지 않은 사용

다음과 같은 단순 작업에는 MCP 사용을 권장하지 않습니다.

- ls, cd 등 단일 명령어 실행
- 명확한 명령어를 이미 알고 있는 경우

MCP는 **판단과 계획이 필요한 작업**에 최적화되어 있습니다.

---

## 설계 철학

- 실행 여부는 룰 기반으로 명확히 결정
- LLM은 판단과 계획에만 사용
- 자연어 입력은 항상 허용
- 결과는 자동화 친화적인 JSON 형식 유지
- 사람과 자동화 모두를 고려한 구조

---

## 요약

Linux-DevOps-MCP는  
“명령어를 대신 쳐주는 도구”가 아니라  
“**운영자의 판단을 실행으로 바꿔주는 도구**"입니다.


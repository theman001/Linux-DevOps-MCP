# Linux-DevOps-MCP

Linux-DevOps-MCP는  
단순한 자동화 스크립트나 모니터링 도구가 아닌,  
**시스템 상태(Context)를 이해하고 판단할 수 있도록 설계된 MCP(Model Context Protocol) 서버**입니다.

본 프로젝트는 특히 **OCI Always Free 환경**과 같은  
리소스가 제한된 Linux 서버에서 다음을 목표로 합니다:

- 시스템 상태의 구조화(Context화)
- 장애 이력 및 패턴의 누적 학습
- LLM 기반 운영 판단 보조
- LLM 부재 시에도 안정적으로 동작하는 fallback 구조

---

## What is MCP in this project?

이 프로젝트에서 MCP(Model Context Protocol)는 다음을 의미합니다:

> **시스템을 직접 제어하는 주체가 아니라,  
> 시스템의 상태를 모델이 이해할 수 있는 Context로 변환하는 중간 계층**

### 기존 자동화와의 차이

| 구분 | 일반 자동화 | Linux-DevOps-MCP |
|---|---|---|
| 판단 | if/else | Context 기반 |
| 상태 인식 | 단일 시점 | 누적 상태 |
| 장애 대응 | 사전 정의 | 패턴 기반 |
| LLM 의존 | 없음 | 선택적 |

---

## Architecture Overview

```
[ System Metrics ]
        ↓
[ Health / Idle / Boot Checkers ]
        ↓
[ Context Builder ]
        ↓
[ MCP Server ]
        ↓
[ LLM (Optional) ]
        ↓
[ Recommendation / Decision ]
```

---

## Core Components

### mcp_server.py
- MCP 서버의 중심
- 시스템 상태를 Context로 통합
- LLM 호출 여부와 무관하게 동작 가능
- 판단 보조 역할에 집중

### healthcheck.py
- CPU, Memory, Disk 상태 점검
- 결과를 state.json에 반영

### idle_watcher.py
- 유휴 상태 감지
- 장기 idle 패턴 수집

### boot_check.py
- 재부팅 이후 과거 incident / pattern 기반 점검

---

## State & Learning Files

| 파일 | 설명 | 갱신 시점 |
|---|---|---|
| state.json | 현재 시스템 상태 | healthcheck |
| incidents.json | 장애 이력 | 장애 발생 시 |
| patterns.json | 학습된 패턴 | reboot 이후 |

---

## LLM-less Fallback Mode

Linux-DevOps-MCP는 **LLM이 없어도 정상 동작**하도록 설계되었습니다.

- 상태 수집 ✔
- JSON 기록 ✔
- 위험도 분류 ✔
- LLM 판단 ❌

---

## Example Operational Scenarios

### Scenario 1: 재부팅 후 상태 점검
- boot_check 실행
- 과거 패턴 기반 위험 요소 사전 탐지

### Scenario 2: 장기 메모리 증가 감지
- healthcheck 누적
- 경고 로그 기록

### Scenario 3: LLM 기반 판단 보조
- CPU spike 패턴 분석
- 권장 조치 텍스트 반환

### Scenario 4: 외부 통신 차단 환경
- 완전 로컬 분석
- JSON 기반 사후 분석

### Scenario 5: 운영자 인수인계
- 서버 장애 이력 자체 보존

### Scenario 6: 자동 실행 없는 판단 보조
- 실행 ❌ / 판단 ✔ / 기록 ✔

---

## Design Philosophy

- 무조건적인 자동 실행 배제
- 판단과 실행의 분리
- Context 우선 설계
- 장기 운영 안정성

---

## Intended Use

- DevOps / SRE 실험
- LLM 운영 자동화 PoC
- Always Free 서버 관리

---

## Disclaimer

본 프로젝트는 **연구 및 실험 목적**으로 설계되었습니다.

# 🚀 Linux-DevOps-MCP

OCI Always Free 환경에 최적화된 **자율 운영 및 장애 학습형** MCP(Model Context Protocol) 서버입니다.

이 프로젝트는 단순한 명령 수행을 넘어, 서버의 상태를 지속적으로 감시하고 장애 패턴을 학습하며, 재부팅 이후에도 과거 패턴을 기반으로 선제 점검을 수행하는 **자율 Linux 운영 에이전트**를 목표로 합니다.

---

## 🎯 설계 목표

* OCI Always Free 저사양 환경에서도 안정적으로 동작
* 예외 발생 시 MCP 프로세스가 죽지 않도록 설계
* 서버 상태와 장애 패턴을 “기억”
* GPT가 단순 출력이 아닌 운영 판단 주체로 동작
* 설치, 업데이트, 점검, 제거까지 운영 사이클 완성

---

## 📂 프로젝트 디렉터리 구조

MCP 서버는 프로젝트 작업 경로와 물리적으로 분리되어 관리됩니다.
```text
/home/ubuntu/mcp/
├─ mcp_server.py          # MCP 메인 서버 (중앙 관제)
├─ utils.py               # 공통 예외처리 및 유틸리티
├─ healthcheck.py         # MCP self-health 체크 로직
├─ idle_watcher.py        # 리소스 절약을 위한 휴면 관리
├─ boot_check.py          # 재부팅 후 패턴 기반 점검
├─ state.json             # MCP 서버 현재 상태 데이터
├─ incidents.json         # 발생한 장애 이력 기록
├─ patterns.json          # 학습된 장애 해결 패턴
├─ error.log              # 실시간 예외 발생 로그
├─ setup_mcp.sh           # 서버 설치 및 가상환경 구축
├─ update_mcp.sh          # 최신 코드 업데이트 스크립트
├─ healthcheck_all.sh     # 전체 시스템 상태 점검
├─ cleanup_mcp.sh         # 서비스 중지 및 완전 제거
└─ mcp-venv/              # MCP 전용 독립 가상환경
```
---

## 🌟 핵심 기능

1. **장애 이력 학습 (Learning Context):**
   - 발생한 장애를 incidents.json에 기록하고 patterns.json으로 구조화하여 동일 문제 발생 시 GPT가 즉각적인 해결책을 제시합니다.
2. **자가 치유 및 선제 점검:**
   - healthcheck.py가 프로세스를 상시 감시하며, boot_check.py가 부팅 직후 시스템 안정성을 확보합니다.
3. **OCI Always Free 최적화:**
   - Swap 사용 전제(OOM 방지) 및 idle_watcher.py를 통해 저사양 환경에서도 안정적인 운용이 가능합니다.

---

## 🚀 운영 스크립트

### 1. 설치 (Setup)
```bash
./setup_mcp.sh
```

### 2. 업데이트 (Update)
```bash
./update_mcp.sh
```

### 3. 상태 점검 (Health Check)
```bash
./healthcheck_all.sh
```

### 4. 완전 제거 (Cleanup)
```bash
./cleanup_mcp.sh
```

---

## ⚠️ 주의사항
- 본 서버는 강력한 시스템 접근 권한을 전제로 합니다.
- 실서비스 환경에서는 반드시 보안 정책을 검토하세요.
- 모든 상세 운영 로그는 error.log에서 실시간으로 확인할 수 있습니다.

---

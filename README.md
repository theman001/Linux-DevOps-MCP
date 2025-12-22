# Linux-DevOps-MCP

OCI Always Free 환경을 기준으로 설계된  
**개발 + 서버 운영 통합 MCP(Model Context Protocol) 서버**입니다.

이 프로젝트는 단순한 코드 에이전트가 아니라,

- 서버 상태를 지속적으로 감시하고
- 장애 이력을 기록·학습하며
- 재부팅 이후에도 과거 패턴을 기반으로 선제 점검을 수행하고
- GPT가 로그와 상태를 읽고 판단하여 조치를 결정할 수 있도록 하는

**자율 Linux 운영 에이전트**를 목표로 합니다.

---

## 🎯 설계 목표

- OCI Always Free 저사양 환경에서도 안정적으로 동작
- 예외 발생 시 MCP 프로세스가 죽지 않도록 설계
- 서버 상태와 장애 패턴을 “기억”
- GPT가 단순 출력이 아닌 **운영 판단 주체**로 동작
- 설치 · 업데이트 · 점검 · 제거까지 운영 사이클 완성

---

## 📌 디렉터리 구조

### MCP 서버 경로
```
/home/ubuntu/mcp
```

### 프로젝트 작업 경로
```
/home/ubuntu/dev/프로젝트
```

MCP 서버는 프로젝트 디렉터리와 **물리적으로 분리**되어 있으며,

- 일상적인 코드 작업 → 프로젝트 경로 중심
- 서버 장애·운영 작업 → 시스템 전체 접근

이라는 명확한 역할 분리를 가집니다.

---

## 🗂️ MCP 디렉터리 구조

```
/home/ubuntu/mcp/
├─ mcp_server.py          # MCP 메인 서버
├─ utils.py               # 공통 예외처리 / 유틸
├─ healthcheck.py         # MCP self-health 체크
├─ idle_watcher.py        # 장시간 미사용 시 휴면
├─ boot_check.py          # 재부팅 후 패턴 기반 점검
├─ state.json             # MCP 상태 (자동 생성)
├─ incidents.json         # 장애 이력 (자동 생성)
├─ patterns.json          # 장애 패턴 (자동 생성)
├─ error.log              # 예외 로그 (자동 생성)
├─ setup_mcp.sh
├─ update_mcp.sh
├─ healthcheck_all.sh
├─ cleanup_mcp.sh
├─ README.md
└─ mcp-venv/
```

---

## 🐍 가상환경 분리 전략

- `/home/ubuntu/mcp/mcp-venv` : MCP 서버 전용 가상환경  
- `/home/ubuntu/dev/.../venv` : 프로젝트/실험용 가상환경

두 환경은 완전히 분리되어 있으며 서로 영향을 주지 않습니다.

---

## 🚀 주요 기능

### 프로젝트 / 서버 운영
- 프로젝트 코드 읽기 및 수정
- 빌드 및 테스트 실행
- 서버 상태 점검 및 장애 분석

### 안정성 및 자율 운영
- heartbeat 기반 self-health
- systemd 자동 재기동
- 장애 이력 및 패턴 학습
- 재부팅 후 패턴 기반 점검

---

## 🛠️ 운영 스크립트

### 설치
```bash
./setup_mcp.sh
```

### 업데이트
```bash
./update_mcp.sh
```

### 상태 점검
```bash
./healthcheck_all.sh
```

### 완전 제거
```bash
./cleanup_mcp.sh
```

---

## ⚙️ Always Free 최적화

- Swap 사용 전제 (OOM 방지)
- CPU 사용 제한
- 불필요한 상시 작업 제거
- GPT 추론은 외부에서 수행

---

## ⚠️ 주의

이 프로젝트는 강력한 시스템 접근 권한을 전제로 합니다.  
실서비스 환경에서는 반드시 보안 정책을 검토하세요.

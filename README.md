# Linux-DevOps-MCP

OCI Always Free 환경을 대상으로 설계된  
**개발 + 서버 운영 통합 MCP(Model Context Protocol) 서버**입니다.

이 프로젝트의 목표는 다음과 같습니다.

- 저사양 서버에서도 안정적으로 동작
- 예외가 발생해도 MCP가 멈추지 않음
- 서버 상태와 장애 이력을 “기억”
- GPT가 로그와 상태를 읽고 판단 가능
- 재부팅 후에도 과거 패턴을 기반으로 선제 점검 수행

---

## 📌 기본 구조

### MCP 서버 경로
```
/home/ubuntu/mcp
```

### 프로젝트 작업 경로
```
/home/ubuntu/dev/프로젝트
```

MCP 서버는 프로젝트 디렉터리와 **물리적으로 분리**되어 있으며,  
일상적인 작업은 프로젝트 경로를 중심으로 수행하고  
필요 시 서버 전체(`/etc`, `/var`, `/proc` 등)에 접근합니다.

---

## 🚀 주요 기능

### 1. 프로젝트 코드 관리
- 프로젝트 파일 읽기
- 코드 수정 및 구조 분석
- 디렉터리 트리 조회
- 빌드 / 테스트 실행

### 2. 서버 운영 및 진단
- 시스템 로그 조회
- 메모리 / 디스크 / 서비스 상태 점검
- 패키지 설치 및 설정 변경
- 장애 발생 시 원인 분석

### 3. Self-Health & 안정성
- MCP heartbeat 기반 상태 감시
- healthcheck 스크립트 제공
- systemd 기반 자동 재기동
- 예외 발생 시에도 프로세스 유지

### 4. 장애 기록 및 패턴 학습
- OOM, 빌드 실패, 명령 실행 실패 등 장애 이력 저장
- 장애 유형별 발생 빈도 누적
- “이 서버는 자주 OOM 발생” 같은 패턴 인식

### 5. 재부팅 후 패턴 기반 초기 점검
- 서버 부팅 시 과거 장애 패턴 로드
- 문제가 있었던 영역만 선별 점검
- 불필요한 전체 점검 제거 (Always Free 최적화)

### 6. GPT 판단 연계
- 에러 로그, 상태 파일, 장애 이력을 GPT가 직접 조회 가능
- GPT가 재기동, 재시도, 무시 여부를 판단
- 운영자 개입 최소화

---

## 🗂️ 디렉터리 구조

```
/home/ubuntu/mcp/
├─ mcp_server.py
├─ utils.py
├─ healthcheck.py
├─ idle_watcher.py
├─ boot_check.py
├─ state.json
├─ incidents.json
├─ patterns.json
├─ error.log
├─ README.md
└─ mcp-venv/
```

---

## ⚙️ Always Free 환경 최적화 포인트

- Swap 사용 전제 (OOM 방지)
- CPU 사용 최소화
- 불필요한 상시 작업 제거
- GPT 추론은 외부에서 수행

---

## 🔁 실행 및 관리

```bash
sudo systemctl start mcp
```

```bash
systemctl status mcp
```

```bash
python3 /home/ubuntu/mcp/healthcheck.py
```

---

## 🧠 MCP 성격

이 MCP는 단순한 코드 에이전트가 아니라  
**기억하고 판단하는 자율 Linux 운영 에이전트**입니다.

---

## ⚠️ 주의

강력한 시스템 권한을 전제로 합니다.  
실서비스 적용 시 보안 정책을 반드시 검토하세요.

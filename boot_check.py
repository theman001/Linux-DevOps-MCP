#!/usr/bin/env python3
import time
from pathlib import Path
from utils import safe_read, safe_write, safe_shell

########################################
# 동적 경로 설정
########################################
# 현재 파일이 위치한 repo 기준
BASE_DIR = Path(__file__).resolve().parent

PATTERNS = BASE_DIR / "patterns.json"
REPORT = BASE_DIR / "boot_report.json"

########################################
# 핵심 점검 함수
########################################
def run_checks(patterns):
    result = {
        "timestamp": time.time(),
        "repo_path": str(BASE_DIR),
        "checks": {}
    }

    # Out Of Memory 기록 확인
    if "OOM" in patterns:
        result["checks"]["OOM"] = {
            "swap": safe_shell("swapon --show").stdout,
            "recent": safe_shell("dmesg | grep -i 'out of memory' | tail -5").stdout
        }

    # 디스크 용량 점검
    if "DISK" in patterns:
        result["checks"]["DISK"] = safe_shell("df -h /").stdout

    # 실패한 서비스 확인
    if "SERVICE" in patterns:
        result["checks"]["SERVICE"] = safe_shell("systemctl --failed").stdout

    return result


########################################
# 실행부
########################################
def main():
    patterns = safe_read(PATTERNS, default=[])
    report = run_checks(patterns)
    safe_write(REPORT, report)


if __name__ == "__main__":
    main()
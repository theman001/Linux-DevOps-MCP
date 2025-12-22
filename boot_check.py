import time, json
from pathlib import Path
from utils import safe_read, safe_write, safe_shell

PATTERNS = Path("/home/ubuntu/mcp/patterns.json")
REPORT = Path("/home/ubuntu/mcp/boot_report.json")

def run_checks(patterns):
    result = {"timestamp": time.time(), "checks": {}}

    if "OOM" in patterns:
        result["checks"]["OOM"] = {
            "swap": safe_shell("swapon --show").stdout,
            "recent": safe_shell("dmesg | grep -i 'out of memory' | tail -5").stdout
        }

    if "DISK" in patterns:
        result["checks"]["DISK"] = safe_shell("df -h /").stdout

    if "SERVICE" in patterns:
        result["checks"]["SERVICE"] = safe_shell("systemctl --failed").stdout

    return result

patterns = safe_read(PATTERNS, {})
report = run_checks(patterns)
safe_write(REPORT, report)

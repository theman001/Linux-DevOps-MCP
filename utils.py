import json, time, traceback, subprocess
from pathlib import Path

LOG = Path("/home/ubuntu/mcp/error.log")

def log_error(msg: str):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"[{time.time()}] {msg}\n")

def safe_read(path: Path, default):
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text())
    except Exception:
        log_error(f"READ_FAIL {path}\n{traceback.format_exc()}")
        return default

def safe_write(path: Path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))
    except Exception:
        log_error(f"WRITE_FAIL {path}\n{traceback.format_exc()}")

def safe_shell(cmd: str, timeout=30):
    try:
        return subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
    except subprocess.TimeoutExpired:
        log_error(f"SHELL_TIMEOUT {cmd}")
        return None
    except Exception:
        log_error(f"SHELL_FAIL {cmd}\n{traceback.format_exc()}")
        return None

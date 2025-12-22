import os, time, json
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from utils import safe_read, safe_write, safe_shell

STATE = Path("/home/ubuntu/mcp/state.json")
INCIDENTS = Path("/home/ubuntu/mcp/incidents.json")
PATTERNS = Path("/home/ubuntu/mcp/patterns.json")
PROJECT_ROOT = Path("/home/ubuntu/dev/프로젝트")

mcp = FastMCP("OCI-Autonomous-MCP")

def heartbeat():
    try:
        safe_write(STATE, {
            "last_heartbeat": time.time(),
            "pid": os.getpid()
        })
    except Exception:
        pass

def record_incident(incident):
    incidents = safe_read(INCIDENTS, [])
    incidents.append(incident)
    safe_write(INCIDENTS, incidents)
    update_patterns(incident)

def update_patterns(incident):
    patterns = safe_read(PATTERNS, {})
    t = incident["type"]
    entry = patterns.get(t, {"count": 0, "contexts": []})
    entry["count"] += 1
    entry["contexts"].append(incident.get("context"))
    entry["last_seen"] = incident["timestamp"]
    patterns[t] = entry
    safe_write(PATTERNS, patterns)

# ================= Project tools =================

@mcp.tool()
def project_read(path: str) -> str:
    try:
        return (PROJECT_ROOT / path).read_text(errors="ignore")
    except Exception as e:
        record_incident({
            "timestamp": time.time(),
            "type": "PROJECT_READ_FAIL",
            "context": path,
            "error": str(e)
        })
        return f"ERROR: {e}"

@mcp.tool()
def project_write(path: str, content: str) -> str:
    try:
        (PROJECT_ROOT / path).write_text(content)
        return "OK"
    except Exception as e:
        record_incident({
            "timestamp": time.time(),
            "type": "PROJECT_WRITE_FAIL",
            "context": path,
            "error": str(e)
        })
        return f"ERROR: {e}"

@mcp.tool()
def project_tree(path: str = ".") -> list:
    try:
        return [p.name for p in (PROJECT_ROOT / path).iterdir()]
    except Exception as e:
        return [f"ERROR: {e}"]

# ================= System tools =================

@mcp.tool()
def system_read(path: str) -> str:
    try:
        return Path(path).read_text(errors="ignore")
    except Exception as e:
        return f"ERROR: {e}"

@mcp.tool()
def shell(command: str) -> str:
    proc = safe_shell(command)
    if proc is None:
        record_incident({
            "timestamp": time.time(),
            "type": "SHELL_FAIL",
            "context": command
        })
        return "ERROR: command failed"
    return proc.stdout + proc.stderr

@mcp.tool()
def system_summary() -> str:
    cmds = [
        "uptime",
        "free -h",
        "df -h /",
        "systemctl --failed",
        "journalctl -p 3 -n 5"
    ]
    out = []
    for c in cmds:
        out.append(f"$ {c}\n")
        r = safe_shell(c)
        out.append(r.stdout if r else "ERROR\n")
    return "\n".join(out)

# ================= Health =================

@mcp.tool()
def check_mcp_health() -> str:
    r = safe_shell("python3 /home/ubuntu/mcp/healthcheck.py")
    return "OK" if r and r.returncode == 0 else "FAIL"

# ================= Main loop =================

if __name__ == "__main__":
    while True:
        heartbeat()
        time.sleep(10)

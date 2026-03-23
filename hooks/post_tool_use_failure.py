#!/usr/bin/env python3
"""PostToolUseFailure hook — logs tool failures for pattern detection.

Logs all tool failures to .claude/logs/audit/tool_failures.jsonl
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MB


def enforce_max_size_text(file_path: Path) -> None:
    """Trim a text log file to MAX_LOG_BYTES by removing oldest lines."""
    file_size = file_path.stat().st_size
    if file_size <= MAX_LOG_BYTES:
        return
    excess = file_size - MAX_LOG_BYTES
    with open(file_path, "rb") as f:
        f.seek(excess)
        f.readline()  # skip partial line
        tail = f.read()
    with open(file_path, "wb") as f:
        f.write(tail)


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return

    cwd = payload.get("cwd", os.getcwd())

    audit_dir = Path(cwd) / ".claude" / "logs" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    log_file = audit_dir / "tool_failures.jsonl"

    entry = {
        "_timestamp": datetime.now(timezone.utc).isoformat(),
        "tool_name": payload.get("tool_name", ""),
        "tool_use_id": payload.get("tool_use_id", ""),
        "tool_input": payload.get("tool_input", {}),
        "error": payload.get("error", {}),
        "session_id": payload.get("session_id", ""),
        "agent_type": payload.get("agent_type"),
        "agent_id": payload.get("agent_id"),
    }

    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")
    enforce_max_size_text(log_file)


if __name__ == "__main__":
    main()

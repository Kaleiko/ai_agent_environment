#!/usr/bin/env python3
"""Session-start hook.

On startup, injects the previous session's chat log as additional context
so Claude has awareness of what was discussed last time.
Only activates on source="startup" (skips resume/clear/compact).
Logs start events to .claude/logs/audit/session_start.jsonl.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MB


def enforce_max_size_text(file_path: Path) -> None:
    """Trim a text log file to MAX_LOG_BYTES by removing oldest lines."""
    if not file_path.exists():
        return
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


def log_audit(cwd: str, session_id: str, source: str, injected: bool) -> None:
    """Log start event to audit file."""
    audit_dir = Path(cwd) / ".claude" / "logs" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_file = audit_dir / "session_start.jsonl"

    entry = {
        "session_id": session_id,
        "source": source,
        "injected": injected,
        "_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(audit_file, "a") as f:
        f.write(json.dumps(entry) + "\n")
    enforce_max_size_text(audit_file)


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return

    session_id = payload.get("session_id", "unknown")
    source = payload.get("source", "")
    cwd = payload.get("cwd", os.getcwd())

    # Only inject on fresh startup, not resume/clear/compact
    if source != "startup":
        log_audit(cwd, session_id, source, injected=False)
        return

    # Read previous session chat log
    last_session_file = Path(cwd) / ".claude" / "logs" / "last_session.md"
    if not last_session_file.exists():
        log_audit(cwd, session_id, source, injected=False)
        return

    content = last_session_file.read_text().strip()
    if not content:
        log_audit(cwd, session_id, source, injected=False)
        return

    # Inject as additional context
    result = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": f"## Previous Session Chat Log\n\n{content}",
        }
    }
    print(json.dumps(result))

    log_audit(cwd, session_id, source, injected=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Session-start hook.

On startup, archives the previous session's chat log to .claude/logs/sessions/,
then injects up to 2 sessions of context so Claude can pick up where it left off.
Also lists any active plan files from .claude/plans/.
Only activates on source="startup" (skips resume/clear/compact).
Logs start events to .claude/logs/audit/session_start.jsonl.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_RECENT_SESSION_CHARS = 15_000
MAX_OLDER_SESSION_CHARS = 5_000
MAX_SESSIONS_TO_KEEP = 2


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


def truncate_content(content: str, max_chars: int) -> str:
    """Truncate content to max_chars, keeping the tail (most recent messages)."""
    if len(content) <= max_chars:
        return content
    truncated = content[-max_chars:]
    # Find the first complete section header to avoid partial messages
    first_header = truncated.find("\n## ")
    if first_header != -1:
        truncated = truncated[first_header + 1:]
    return truncated


def archive_last_session(logs_dir: Path) -> None:
    """Move last_session.md into sessions/ with a timestamp."""
    last_session_file = logs_dir / "last_session.md"
    if not last_session_file.exists():
        return

    content = last_session_file.read_text().strip()
    if not content:
        return

    sessions_dir = logs_dir / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    archived_file = sessions_dir / f"{timestamp}_session.md"
    archived_file.write_text(content)

    # Clear last_session.md so it's fresh for the new session
    last_session_file.write_text("")


def cleanup_old_sessions(sessions_dir: Path) -> None:
    """Keep only the most recent MAX_SESSIONS_TO_KEEP session files."""
    if not sessions_dir.is_dir():
        return

    session_files = sorted(sessions_dir.glob("*_session.md"))
    if len(session_files) <= MAX_SESSIONS_TO_KEEP:
        return

    # Delete oldest files, keep the most recent ones
    for old_file in session_files[:-MAX_SESSIONS_TO_KEEP]:
        old_file.unlink()


def get_session_context(sessions_dir: Path) -> str:
    """Read the 2 most recent session files and return formatted context."""
    if not sessions_dir.is_dir():
        return ""

    session_files = sorted(sessions_dir.glob("*_session.md"))
    if not session_files:
        return ""

    sections = []

    # Most recent session gets more chars
    recent_file = session_files[-1]
    recent_content = recent_file.read_text().strip()
    if recent_content:
        recent_content = truncate_content(recent_content, MAX_RECENT_SESSION_CHARS)
        sections.append(f"### Most Recent Session\n\n{recent_content}")

    # Older session gets fewer chars
    if len(session_files) >= 2:
        older_file = session_files[-2]
        older_content = older_file.read_text().strip()
        if older_content:
            older_content = truncate_content(older_content, MAX_OLDER_SESSION_CHARS)
            sections.append(f"### Earlier Session\n\n{older_content}")

    return "\n\n---\n\n".join(sections)


def get_active_plans(cwd: str) -> str:
    """List any active plan files in .claude/plans/."""
    plans_dir = Path(cwd) / ".claude" / "plans"
    if not plans_dir.is_dir():
        return ""

    plan_files = sorted(plans_dir.glob("*.md"))
    if not plan_files:
        return ""

    lines = ["### Active Plans", ""]
    for plan_file in plan_files:
        lines.append(f"- `.claude/plans/{plan_file.name}`")
    lines.append("")
    lines.append("Review these plans before starting new work.")
    return "\n".join(lines)


def log_audit(
    cwd: str, session_id: str, source: str, injected: bool,
    sessions_loaded: int = 0, plans_found: int = 0
) -> None:
    """Log start event to audit file."""
    audit_dir = Path(cwd) / ".claude" / "logs" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_file = audit_dir / "session_start.jsonl"

    entry = {
        "session_id": session_id,
        "source": source,
        "injected": injected,
        "sessions_loaded": sessions_loaded,
        "plans_found": plans_found,
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

    logs_dir = Path(cwd) / ".claude" / "logs"
    sessions_dir = logs_dir / "sessions"

    # Archive the previous session's last_session.md into sessions/
    archive_last_session(logs_dir)

    # Clean up old sessions (keep only 2)
    cleanup_old_sessions(sessions_dir)

    # Build context from previous sessions
    session_context = get_session_context(sessions_dir)
    plans_context = get_active_plans(cwd)

    if not session_context and not plans_context:
        log_audit(cwd, session_id, source, injected=False)
        return

    # Count what we're injecting for audit
    session_files = sorted(sessions_dir.glob("*_session.md")) if sessions_dir.is_dir() else []
    plans_dir = Path(cwd) / ".claude" / "plans"
    plan_files = sorted(plans_dir.glob("*.md")) if plans_dir.is_dir() else []

    # Build the injection
    parts = ["## Previous Session Chat Log"]

    if session_context:
        parts.append(session_context)

    if plans_context:
        parts.append(plans_context)

    combined = "\n\n".join(parts)

    result = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": combined,
        }
    }
    print(json.dumps(result))

    log_audit(
        cwd, session_id, source, injected=True,
        sessions_loaded=len(session_files),
        plans_found=len(plan_files),
    )


if __name__ == "__main__":
    main()

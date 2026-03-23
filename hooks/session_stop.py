#!/usr/bin/env python3
"""Session-stop hook.

Parses the session transcript and writes a condensed chat log of user/assistant
messages to .claude/logs/last_session.md for cross-session context.
Logs stop events to .claude/logs/audit/session_stop.jsonl.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

MAX_CHAT_CHARS = 4000
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


def extract_user_text(entry: dict) -> str | None:
    """Extract text from a user message entry."""
    message = entry.get("message", {})
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
            elif isinstance(block, str):
                texts.append(block)
        result = "\n".join(texts).strip()
        return result if result else None
    return None


def extract_assistant_text(entry: dict) -> str | None:
    """Extract only text blocks from an assistant message entry."""
    message = entry.get("message", {})
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "").strip()
                if text:
                    texts.append(text)
        result = "\n\n".join(texts).strip()
        return result if result else None
    return None


def parse_transcript(transcript_path: str) -> str:
    """Parse a JSONL transcript and return a markdown chat log."""
    if not os.path.isfile(transcript_path):
        return ""

    messages = []

    with open(transcript_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            entry_type = entry.get("type", "")

            if entry_type == "user":
                text = extract_user_text(entry)
                if text:
                    messages.append(f"## User\n{text}")

            elif entry_type == "assistant":
                text = extract_assistant_text(entry)
                if text:
                    messages.append(f"## Assistant\n{text}")

    if not messages:
        return ""

    chat_log = "\n\n".join(messages)

    # Cap at MAX_CHAT_CHARS, trimming from the top to keep recent messages
    if len(chat_log) > MAX_CHAT_CHARS:
        chat_log = chat_log[-MAX_CHAT_CHARS:]
        # Find the first complete section header to avoid partial messages
        first_header = chat_log.find("\n## ")
        if first_header != -1:
            chat_log = chat_log[first_header + 1:]  # +1 to skip the leading newline

    return chat_log


def log_audit(cwd: str, session_id: str, transcript_path: str, chat_length: int) -> None:
    """Log stop event to audit file."""
    audit_dir = Path(cwd) / ".claude" / "logs" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_file = audit_dir / "session_stop.jsonl"

    entry = {
        "session_id": session_id,
        "transcript_path": transcript_path,
        "chat_length": chat_length,
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
    transcript_path = payload.get("transcript_path", "")
    cwd = payload.get("cwd", os.getcwd())

    # Parse transcript into condensed chat log
    chat_log = parse_transcript(transcript_path)

    # Write chat log to last_session.md
    logs_dir = Path(cwd) / ".claude" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    last_session_file = logs_dir / "last_session.md"
    last_session_file.write_text(chat_log)

    # Audit log
    log_audit(cwd, session_id, transcript_path, len(chat_log))


if __name__ == "__main__":
    main()

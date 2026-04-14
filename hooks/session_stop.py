#!/usr/bin/env python3
"""Session-stop hook.

Parses the session transcript and writes a condensed chat log of user/assistant
messages to .claude/logs/last_session.md for cross-session context.
Logs stop events to .claude/logs/audit/session_stop.jsonl.

When the FULL_LOG environment variable is set (truthy), also appends new
conversation messages to .claude/logs/full_log.md as a persistent, append-only
log across sessions.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

MAX_CHAT_CHARS = 20_000
MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MB
FULL_LOG_STATE_FILENAME = ".full_log_state.json"


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
            chat_log = chat_log[first_header + 1 :]  # +1 to skip the leading newline

    return chat_log


def is_full_log_enabled() -> bool:
    """Check whether the FULL_LOG environment variable is set and truthy.

    Returns:
        True if FULL_LOG is set to a non-empty, truthy value.
    """
    value = os.environ.get("FULL_LOG", "").strip().lower()
    return value not in ("", "0", "false", "no")


def load_full_log_state(state_path: Path) -> dict:
    """Load the full-log state file that tracks the last written offset.

    Args:
        state_path: Path to the JSON state file.

    Returns:
        Dictionary with 'transcript_path' and 'line_offset' keys,
        or defaults if the file does not exist or is corrupt.
    """
    if state_path.exists():
        try:
            return json.loads(state_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"transcript_path": "", "line_offset": 0}


def save_full_log_state(
    state_path: Path, transcript_path: str, line_offset: int
) -> None:
    """Persist the full-log state so the next invocation knows where it left off.

    Args:
        state_path: Path to the JSON state file.
        transcript_path: The transcript file that was just processed.
        line_offset: The number of lines already written from this transcript.
    """
    state_path.write_text(
        json.dumps({"transcript_path": transcript_path, "line_offset": line_offset})
    )


def parse_transcript_lines(transcript_path: str) -> list[str]:
    """Read all non-empty lines from a JSONL transcript file.

    Args:
        transcript_path: Filesystem path to the JSONL transcript.

    Returns:
        List of stripped, non-empty lines from the file.
    """
    if not os.path.isfile(transcript_path):
        return []
    with open(transcript_path, "r") as f:
        return [line.strip() for line in f if line.strip()]


def format_messages_from_lines(lines: list[str]) -> str:
    """Convert raw JSONL lines into markdown-formatted chat messages.

    Args:
        lines: List of JSON strings, each representing a transcript entry.

    Returns:
        Markdown string with ## User / ## Assistant headers.
    """
    messages = []
    for line in lines:
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

    return "\n\n".join(messages)


def append_full_log(logs_dir: Path, transcript_path: str) -> None:
    """Append new transcript messages to full_log.md (delta-only).

    Uses a state file to track which lines have already been written so that
    repeated invocations within the same session do not duplicate content.
    When the transcript path changes (new session), a session separator header
    is inserted.

    Args:
        logs_dir: The .claude/logs directory.
        transcript_path: Filesystem path to the current JSONL transcript.
    """
    state_path = logs_dir / FULL_LOG_STATE_FILENAME
    state = load_full_log_state(state_path)

    all_lines = parse_transcript_lines(transcript_path)
    total_lines = len(all_lines)

    # Determine if this is a new session (different transcript file)
    is_new_session = state["transcript_path"] != transcript_path
    offset = 0 if is_new_session else state["line_offset"]

    # Nothing new to write
    if offset >= total_lines:
        return

    new_lines = all_lines[offset:]
    new_content = format_messages_from_lines(new_lines)

    if not new_content:
        # Lines existed but produced no user/assistant messages; still advance offset
        save_full_log_state(state_path, transcript_path, total_lines)
        return

    full_log_path = logs_dir / "full_log.md"

    with open(full_log_path, "a") as f:
        if is_new_session:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            f.write(f"\n---\n\n# Session: {timestamp}\n\n")
        elif offset > 0:
            # Separate from previously written content within the same session
            f.write("\n\n")
        f.write(new_content)

    save_full_log_state(state_path, transcript_path, total_lines)


def log_audit(
    cwd: str, session_id: str, transcript_path: str, chat_length: int
) -> None:
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
    """Parse session transcript and write condensed logs.

    Each operation (last_session write, full_log append, audit log) is
    isolated in its own try/except so that a transient failure in one
    (e.g., Dropbox file-lock contention) does not prevent the others
    from succeeding and does not crash the hook process.  An unhandled
    exception would cause a non-zero exit code, which may lead Claude
    Code to stop invoking this hook for the remainder of the session.
    """
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        return

    session_id = payload.get("session_id", "unknown")
    transcript_path = payload.get("transcript_path", "")
    cwd = payload.get("cwd", os.getcwd())

    # Parse transcript into condensed chat log
    chat_log = ""
    try:
        chat_log = parse_transcript(transcript_path)
    except Exception as exc:
        print(f"session_stop: parse_transcript failed: {exc}", file=sys.stderr)

    # Write chat log to last_session.md
    logs_dir = Path(cwd) / ".claude" / "logs"
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        last_session_file = logs_dir / "last_session.md"
        last_session_file.write_text(chat_log)
    except Exception as exc:
        print(f"session_stop: write last_session.md failed: {exc}", file=sys.stderr)

    # Append to full_log.md when FULL_LOG is enabled
    try:
        if is_full_log_enabled() and transcript_path:
            append_full_log(logs_dir, transcript_path)
    except Exception as exc:
        print(f"session_stop: append_full_log failed: {exc}", file=sys.stderr)

    # Audit log
    try:
        log_audit(cwd, session_id, transcript_path, len(chat_log))
    except Exception as exc:
        print(f"session_stop: log_audit failed: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()

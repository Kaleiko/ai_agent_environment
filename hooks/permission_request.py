#!/usr/bin/env python3
"""PermissionRequest hook — auto-allows read-only operations.

Auto-allows: Read, Glob, Grep, and safe Bash commands (ls, pwd, git status, etc.)
Logs all permission requests to .claude/logs/audit/permission_request.jsonl
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MB

# Tools that are always safe (read-only)
ALWAYS_ALLOW_TOOLS = {"Read", "Glob", "Grep"}

# Safe standalone commands (no arguments needed to be safe)
SAFE_COMMANDS = {"ls", "pwd", "wc", "which", "file", "stat", "head", "tail"}

# Safe commands with version flags
VERSION_COMMANDS = {"python", "python3", "node", "npm", "pip", "pip3"}

# Safe git subcommands (read-only)
SAFE_GIT_SUBCOMMANDS = {"status", "log", "diff", "show", "branch", "tag"}

# Safe npm subcommands (read-only)
SAFE_NPM_SUBCOMMANDS = {"list", "ls", "outdated", "view"}

# Safe pip subcommands (read-only)
SAFE_PIP_SUBCOMMANDS = {"list", "show", "freeze"}

# Characters that indicate potentially unsafe shell operations
UNSAFE_SHELL_CHARS = re.compile(r"[>|;`$(&]")


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


def log_request(cwd: str, payload: dict, decision: str) -> None:
    """Append the permission request to .claude/logs/audit/permission_request.jsonl."""
    audit_dir = Path(cwd) / ".claude" / "logs" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    log_file = audit_dir / "permission_request.jsonl"

    entry = {
        "_timestamp": datetime.now(timezone.utc).isoformat(),
        "tool_name": payload.get("tool_name", ""),
        "decision": decision,
        "agent_type": payload.get("agent_type"),
        "agent_id": payload.get("agent_id"),
    }
    # Include command for Bash calls
    if payload.get("tool_name") == "Bash":
        entry["command"] = payload.get("tool_input", {}).get("command", "")

    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")
    enforce_max_size_text(log_file)


def allow() -> dict:
    """Return an allow decision."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {
                "behavior": "allow",
            },
        }
    }


def is_safe_bash(command: str) -> bool:
    """Check if a Bash command is safe (read-only)."""
    command = command.strip()
    if not command:
        return False

    # Reject commands with shell operators that could chain unsafe operations
    # But allow pipes for read-only chains like `git log | head`
    # and allow $() for safe subshells
    if re.search(r"[>;`(&]", command):
        # Allow `cat` without redirection — but `>` is already caught above
        return False

    # Split on pipes to check each segment
    segments = [s.strip() for s in command.split("|")]

    for segment in segments:
        parts = segment.split()
        if not parts:
            return False

        cmd = os.path.basename(parts[0])

        # Safe standalone commands
        if cmd in SAFE_COMMANDS:
            continue

        # cat without redirection (already checked for > above)
        if cmd == "cat":
            continue

        # Version checks: python --version, node --version, etc.
        if cmd in VERSION_COMMANDS and len(parts) == 2 and parts[1] == "--version":
            continue

        # git read-only subcommands
        if cmd == "git" and len(parts) >= 2:
            subcommand = parts[1]
            if subcommand in SAFE_GIT_SUBCOMMANDS:
                continue
            # git remote -v
            if subcommand == "remote" and parts[2:] == ["-v"]:
                continue
            return False

        # npm read-only subcommands
        if cmd == "npm" and len(parts) >= 2 and parts[1] in SAFE_NPM_SUBCOMMANDS:
            continue

        # pip/pip3 read-only subcommands
        if cmd in ("pip", "pip3") and len(parts) >= 2 and parts[1] in SAFE_PIP_SUBCOMMANDS:
            continue

        # Not recognized as safe
        return False

    return True


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return

    tool_name = payload.get("tool_name", "")
    cwd = payload.get("cwd", os.getcwd())

    # Always allow read-only tools
    if tool_name in ALWAYS_ALLOW_TOOLS:
        log_request(cwd, payload, "allow")
        print(json.dumps(allow()))
        return

    # Check safe Bash commands
    if tool_name == "Bash":
        command = payload.get("tool_input", {}).get("command", "")
        if is_safe_bash(command):
            log_request(cwd, payload, "allow")
            print(json.dumps(allow()))
            return

    # Not auto-allowed — pass through to user prompt
    log_request(cwd, payload, "pass_through")


if __name__ == "__main__":
    main()

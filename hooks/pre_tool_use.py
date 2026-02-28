#!/usr/bin/env python3
"""Pre-tool-use security hook.

Blocks destructive commands targeting outside the project CWD.
Logs all security decisions to .claude/logs/security/pre_tool_use.log
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# --- Tier 1: Hard-blocked patterns (catastrophic, always blocked) ---

TIER1_PATTERNS = [
    # Wipe root / home
    r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?(-[a-zA-Z]*r[a-zA-Z]*\s+|--recursive\s+)?\s*/\s*$",
    r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*\s+)?(-[a-zA-Z]*f[a-zA-Z]*\s+)?\s*/\s*$",
    r"\brm\s+-rf\s+/\b",
    r"\brm\s+-rf\s+~",
    r"\brm\s+-rf\s+\$HOME\b",
    r"\brm\s+-rf\s+\$\{HOME\}",
    # Disk destruction
    r">\s*/dev/sd[a-z]",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    # Force push to main/master
    r"\bgit\s+push\s+.*--force.*\b(main|master)\b",
    r"\bgit\s+push\s+-f\s+.*\b(main|master)\b",
]

TIER1_COMPILED = [re.compile(p) for p in TIER1_PATTERNS]

# --- Tier 2: Destructive commands that must stay within CWD ---

DESTRUCTIVE_COMMANDS = {"rm", "mv", "chmod", "chown", "shred", "unlink"}

# Tools with file_path that should be CWD-checked
FILE_PATH_TOOLS = {"Read", "Write", "Edit"}

# Directories outside CWD that are allowed for file path tools
ALLOWED_EXTERNAL_DIRS = [
    os.path.join(os.path.expanduser("~"), ".claude"),
]


def get_cwd(payload: dict) -> str:
    """Get the working directory from the hook payload."""
    return payload.get("cwd", os.getcwd())


def log_decision(cwd: str, decision: str, tool_name: str, detail: str) -> None:
    """Append a log entry to .claude/logs/security/pre_tool_use.log."""
    log_dir = Path(cwd) / ".claude" / "logs" / "security"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "pre_tool_use.log"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry = f"[{timestamp}] {decision} {tool_name}: {detail}\n"
    with open(log_file, "a") as f:
        f.write(entry)


def deny(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def check_tier1(command: str) -> str | None:
    """Return a reason string if the command matches a Tier 1 pattern."""
    for pattern in TIER1_COMPILED:
        if pattern.search(command):
            return f"Blocked: catastrophic command detected ({command.strip()[:80]})"
    return None


def extract_paths_from_command(command: str) -> list[str]:
    """Extract file/directory path arguments from a shell command.

    This is a best-effort extraction — it splits on whitespace and picks
    tokens that look like paths (start with /, ./, ../, ~, or are bare names
    after the command+flags).
    """
    parts = command.strip().split()
    if not parts:
        return []

    paths = []
    skip_next = False
    for i, part in enumerate(parts):
        if skip_next:
            skip_next = False
            continue
        # Skip the command itself
        if i == 0:
            continue
        # Skip flags, but note flags that take a value argument
        if part.startswith("-"):
            # Common flags that consume the next token as a value
            if part in ("-t", "--target-directory"):
                skip_next = True
            continue
        # Everything else is likely a path argument
        paths.append(part)
    return paths


def resolve_path(path_str: str, cwd: str) -> str:
    """Resolve a path string to an absolute path relative to cwd."""
    p = path_str.replace("~", os.path.expanduser("~"))
    if not os.path.isabs(p):
        p = os.path.join(cwd, p)
    return os.path.normpath(p)


def is_within_cwd(resolved_path: str, cwd: str) -> bool:
    """Check if a resolved path is within (or equal to) cwd."""
    norm_cwd = os.path.normpath(cwd)
    return resolved_path == norm_cwd or resolved_path.startswith(norm_cwd + os.sep)


def check_bash_command(command: str, cwd: str) -> str | None:
    """Check a Bash command for security violations. Returns reason if blocked."""
    # Tier 1: catastrophic commands
    reason = check_tier1(command)
    if reason:
        return reason

    # Tier 2: destructive commands outside CWD
    # Handle piped/chained commands by splitting on pipe, &&, ||, ;
    sub_commands = re.split(r"\s*(?:\||\|\||&&|;)\s*", command)
    for sub in sub_commands:
        parts = sub.strip().split()
        if not parts:
            continue
        cmd = parts[0]
        # Strip any leading path (e.g., /bin/rm -> rm)
        cmd_base = os.path.basename(cmd)
        if cmd_base in DESTRUCTIVE_COMMANDS:
            paths = extract_paths_from_command(sub)
            for p in paths:
                resolved = resolve_path(p, cwd)
                if not is_within_cwd(resolved, cwd):
                    return (
                        f"Blocked: {cmd_base} targets outside project directory ({p})"
                    )
    return None


def is_in_allowed_external_dir(resolved_path: str) -> bool:
    """Check if a resolved path is within an allowed external directory."""
    for allowed_dir in ALLOWED_EXTERNAL_DIRS:
        norm_allowed = os.path.normpath(allowed_dir)
        if resolved_path == norm_allowed or resolved_path.startswith(
            norm_allowed + os.sep
        ):
            return True
    return False


def check_file_path_tool(tool_input: dict, cwd: str) -> str | None:
    """Check Read/Write/Edit tool file_path against CWD."""
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return None
    resolved = resolve_path(file_path, cwd)
    if not is_within_cwd(resolved, cwd) and not is_in_allowed_external_dir(resolved):
        return f"Blocked: file path targets outside project directory ({file_path})"
    return None


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        # Can't parse input — allow by default, don't break the workflow
        return

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    cwd = get_cwd(payload)
    reason = None

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        reason = check_bash_command(command, cwd)
        detail = command.strip()[:120]
    elif tool_name in FILE_PATH_TOOLS:
        reason = check_file_path_tool(tool_input, cwd)
        detail = tool_input.get("file_path", "")[:120]
    else:
        # Tool not in our watch list — allow
        return

    if reason:
        log_decision(cwd, "BLOCKED", tool_name, reason)
        result = deny(reason)
        print(json.dumps(result))
    else:
        log_decision(cwd, "ALLOWED", tool_name, detail)


if __name__ == "__main__":
    main()

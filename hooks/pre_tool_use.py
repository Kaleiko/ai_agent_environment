#!/usr/bin/env python3
"""Pre-tool-use security hook.

Blocks destructive commands targeting outside the project CWD.
Logs blocked tool calls to .claude/logs/security/blocked.jsonl
Logs all tool call payloads to .claude/logs/audit/pre_tool_use.jsonl
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
    r"\brm\s+-rf\s+/(?:[*\s;|&]|$)",
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
FILE_PATH_TOOLS = {"Read", "Write", "Edit", "MultiEdit"}

# Directories outside CWD that are allowed for file path tools
# NOTE: {CWD}/.claude/ is also allowed — see get_allowed_external_dirs()
ALLOWED_EXTERNAL_DIRS = [
    os.path.join(os.path.expanduser("~"), ".claude"),
]

# Add AI agent environment if configured
_ai_env = os.environ.get("AI_AGENT_ENV_PATH")
if _ai_env and os.path.isdir(_ai_env):
    ALLOWED_EXTERNAL_DIRS.append(_ai_env)


def get_allowed_external_dirs(cwd: str) -> list[str]:
    """Return all allowed external directories, including {CWD}/.claude/.

    Args:
        cwd: The current working directory.

    Returns:
        List of allowed directory paths.
    """
    return ALLOWED_EXTERNAL_DIRS + [os.path.join(cwd, ".claude")]


MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MB


def enforce_max_size_text(file_path: Path) -> None:
    """Trim a text log file to MAX_LOG_BYTES by removing oldest lines."""
    file_size = file_path.stat().st_size
    if file_size <= MAX_LOG_BYTES:
        return
    # Seek to the excess portion, then find the next newline to keep whole lines
    excess = file_size - MAX_LOG_BYTES
    with open(file_path, "rb") as f:
        f.seek(excess)
        f.readline()  # skip partial line
        tail = f.read()
    with open(file_path, "wb") as f:
        f.write(tail)


def get_cwd(payload: dict) -> str:
    """Get the working directory from the hook payload."""
    return payload.get("cwd", os.getcwd())


def log_audit(cwd: str, payload: dict) -> None:
    """Append the full tool call payload to .claude/logs/audit/pre_tool_use.jsonl."""
    audit_dir = Path(cwd) / ".claude" / "logs" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_file = audit_dir / "pre_tool_use.jsonl"

    payload["_timestamp"] = datetime.now(timezone.utc).isoformat()
    # Ensure agent identity fields are present for subagent attribution
    payload.setdefault("agent_type", None)
    payload.setdefault("agent_id", None)
    with open(audit_file, "a") as f:
        f.write(json.dumps(payload) + "\n")
    enforce_max_size_text(audit_file)


def log_blocked(
    cwd: str,
    tool_name: str,
    tool_input: dict,
    reason: str,
    agent_type: str | None = None,
    agent_id: str | None = None,
) -> None:
    """Append blocked tool call details to .claude/logs/security/blocked.jsonl."""
    security_dir = Path(cwd) / ".claude" / "logs" / "security"
    security_dir.mkdir(parents=True, exist_ok=True)
    blocked_file = security_dir / "blocked.jsonl"

    entry = {
        "_timestamp": datetime.now(timezone.utc).isoformat(),
        "tool_name": tool_name,
        "tool_input": tool_input,
        "reason": reason,
        "agent_type": agent_type,
        "agent_id": agent_id,
    }
    with open(blocked_file, "a") as f:
        f.write(json.dumps(entry) + "\n")
    enforce_max_size_text(blocked_file)


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
    """Resolve a path string to an absolute, symlink-resolved path relative to cwd.

    Args:
        path_str: The raw path string (may be relative, contain ~, or have symlinks).
        cwd: The current working directory to resolve relative paths against.

    Returns:
        A fully resolved absolute path with symlinks resolved.
    """
    p = path_str.replace("~", os.path.expanduser("~"))
    if not os.path.isabs(p):
        p = os.path.join(cwd, p)
    return os.path.realpath(p)


def is_within_cwd(resolved_path: str, cwd: str) -> bool:
    """Check if a resolved path is within (or equal to) cwd.

    Both paths are resolved via realpath to handle symlinks consistently.

    Args:
        resolved_path: The fully resolved file path to check.
        cwd: The current working directory.

    Returns:
        True if resolved_path is within or equal to cwd.
    """
    real_cwd = os.path.realpath(cwd)
    real_path = os.path.realpath(resolved_path)
    return real_path == real_cwd or real_path.startswith(real_cwd + os.sep)


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


def is_in_allowed_external_dir(resolved_path: str, cwd: str = "") -> bool:
    """Check if a resolved path is within an allowed external directory.

    Args:
        resolved_path: The fully resolved file path to check.
        cwd: The current working directory (used to allow {CWD}/.claude/).

    Returns:
        True if the path is within an allowed external directory.
    """
    allowed_dirs = get_allowed_external_dirs(cwd) if cwd else ALLOWED_EXTERNAL_DIRS
    real_path = os.path.realpath(resolved_path)
    for allowed_dir in allowed_dirs:
        real_allowed = os.path.realpath(allowed_dir)
        if real_path == real_allowed or real_path.startswith(real_allowed + os.sep):
            return True
    return False


def is_env_file(path_str: str) -> bool:
    """Check if a path targets a .env file (but allow .env.sample, .env.example)."""
    basename = os.path.basename(path_str)
    safe_suffixes = (".sample", ".example", ".template", ".test")
    return basename == ".env" or (
        basename.startswith(".env.")
        and not any(basename.endswith(s) for s in safe_suffixes)
    )


def check_env_in_command(command: str) -> str | None:
    """Check if a Bash command accesses .env files.

    Only matches actual .env file access patterns (e.g., `cat .env`, `source .env`,
    `cp .env .env.bak`, file paths containing .env). Does NOT match the string ".env"
    when it appears inside quoted content, heredocs, or echo/printf arguments.

    Args:
        command: The bash command string to check.

    Returns:
        A reason string if blocked, or None if allowed.
    """
    # First, strip out heredocs, then quoted strings, to avoid false positives.
    # Remove heredoc content FIRST (before quote stripping mangles the delimiter).
    # Matches: <<EOF ... EOF, <<'EOF' ... EOF, <<"EOF" ... EOF, <<-EOF ... EOF
    stripped = re.sub(r"<<-?\s*['\"]?(\w+)['\"]?.*", "", command, flags=re.DOTALL)
    # Remove single-quoted strings (no interpolation, so safe to strip entirely)
    stripped = re.sub(r"'[^']*'", "''", stripped)
    # Remove double-quoted strings
    stripped = re.sub(r'"[^"]*"', '""', stripped)

    # Allow listing .env files (ls is read-only)
    parts = stripped.split()
    if parts and os.path.basename(parts[0]) == "ls":
        return None

    # Safe suffixes that are not secret files
    safe_suffix = r"(?!\.(?:sample|example|template|test)\b)"

    # Match .env as a file path token — preceded by whitespace, path separator, or start of line
    # This catches: cat .env, source .env, /path/to/.env, ./.env, cp .env.local foo
    if re.search(rf"(?:^|[\s/])\.env\b{safe_suffix}", stripped):
        return "Blocked: access to .env files containing secrets is prohibited (use .env.sample instead)"
    return None


def is_full_log_file(path_str: str) -> bool:
    """Check if a path targets full_log.md.

    Args:
        path_str: The file path string to check.

    Returns:
        True if the path refers to full_log.md.
    """
    return os.path.basename(path_str) == "full_log.md" or "full_log.md" in path_str


def check_file_path_tool(tool_name: str, tool_input: dict, cwd: str) -> str | None:
    """Check Read/Write/Edit tool file_path against CWD, .env, and full_log protection.

    Args:
        tool_name: The name of the tool being invoked.
        tool_input: The tool's input parameters.
        cwd: The current working directory.

    Returns:
        A reason string if blocked, or None if allowed.
    """
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return None

    # Block reading full_log.md (any tool that reads)
    if tool_name == "Read" and is_full_log_file(file_path):
        return "Blocked: reading full_log.md is prohibited — this file is write-only for the session hook"

    # Block .env file access
    if is_env_file(file_path):
        return "Blocked: access to .env files containing secrets is prohibited (use .env.sample instead)"

    resolved = resolve_path(file_path, cwd)
    if not is_within_cwd(resolved, cwd) and not is_in_allowed_external_dir(
        resolved, cwd
    ):
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
    agent_type = payload.get("agent_type")
    agent_id = payload.get("agent_id")

    # Audit log: capture every tool call payload
    log_audit(cwd, payload)

    reason = None

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        reason = check_env_in_command(command) or check_bash_command(command, cwd)
    elif tool_name in FILE_PATH_TOOLS:
        reason = check_file_path_tool(tool_name, tool_input, cwd)
    else:
        return

    if reason:
        log_blocked(cwd, tool_name, tool_input, reason, agent_type, agent_id)
        result = deny(reason)
        print(json.dumps(result))


if __name__ == "__main__":
    main()

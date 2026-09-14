#!/usr/bin/env python3
"""Merge hook definitions into ~/.claude/settings.json.

Reads the existing settings file, sets/replaces the 'hooks' key with all hook
definitions (each command embeds the ABSOLUTE hook script path resolved at
install time — no environment variable is read at runtime), guarantees the 'env'
block pins AI_AGENT_ENV_PATH to this repo's absolute path as a shell convenience,
and writes back without touching other keys (theme, tui, statusLine, etc.).
"""

import json
import sys
from pathlib import Path

SETTINGS_PATH = Path.home() / ".claude" / "settings.json"

# Repo root resolved from this script's OWN location so the pin never depends on
# the AI_AGENT_ENV_PATH environment variable being set (the whole point of the
# pin is to stop relying on that variable). The script lives at
# <repo>/scripts/merge_global_settings.py, so the repo root is parent.parent.
REPO_ROOT = Path(__file__).resolve().parent.parent

# Env var pinned in settings.json purely as a shell convenience; nothing at
# runtime depends on it (hook commands embed absolute paths — see build_hooks).
AI_AGENT_ENV_PATH_KEY = "AI_AGENT_ENV_PATH"

# Suffix appended to the settings file when backing up an unparseable file.
BACKUP_SUFFIX = ".bak"

# Hook event name -> (script filename, optional PreToolUse-style matcher).
# build_hooks() renders each into a settings entry whose command embeds the
# ABSOLUTE hook script path (no environment-variable expansion), so hooks resolve
# without AI_AGENT_ENV_PATH ever being read at runtime.
HOOK_DEFINITIONS: dict[str, tuple[str, str | None]] = {
    "PreToolUse": ("pre_tool_use.py", "Bash|Read|Write|Edit"),
    "PermissionRequest": ("permission_request.py", None),
    "PostToolUseFailure": ("post_tool_use_failure.py", None),
    "SubagentStop": ("subagent_stop.py", None),
    "SubagentStart": ("subagent_start.py", None),
    "Stop": ("session_stop.py", None),
    "SessionStart": ("session_start.py", None),
}


def build_hooks(repo_root: Path) -> dict:
    """Build the settings 'hooks' block with absolute command paths.

    Each command embeds the absolute path to the hook script under
    <repo_root>/hooks/ so it works from any project directory and contains no
    '$' / environment-variable expansion.

    Args:
        repo_root: Absolute path to the repo root whose hooks/ directory holds the
            hook scripts.

    Returns:
        A settings 'hooks' dictionary mapping each event name to its matcher/hook
        group.
    """
    hooks: dict = {}
    for event_name, (script_name, matcher) in HOOK_DEFINITIONS.items():
        script_path = repo_root / "hooks" / script_name
        entry: dict = {
            "hooks": [{"type": "command", "command": f'python3 "{script_path}"'}]
        }
        if matcher is not None:
            # Preserve matcher-first key order to match the historical layout.
            entry = {"matcher": matcher, **entry}
        hooks[event_name] = [entry]
    return hooks


# Rendered hooks block for this repo. Kept module-level so main() and tests share
# one canonical value; commands hold absolute paths resolved from REPO_ROOT.
HOOKS = build_hooks(REPO_ROOT)


def load_settings(settings_path: Path) -> dict:
    """Load the existing settings file, returning an empty dict if it is absent.

    Unlike a silent fallback, a corrupt or unreadable existing file is treated as
    a hard error: the user's real configuration (theme, tui, env, statusLine) must
    never be silently discarded and rebuilt as hooks-only.

    Args:
        settings_path: Path to the settings.json file to read.

    Returns:
        The parsed settings dictionary, or an empty dict if the file does not exist.

    Raises:
        SystemExit: If the file exists but cannot be read (OSError) or parsed
            (json.JSONDecodeError). On a parse error the original bytes are first
            backed up to '<settings_path><BACKUP_SUFFIX>' so nothing is lost, then
            the process exits non-zero so an installer running under 'set -e' stops
            and the user notices instead of losing their configuration.
    """
    if not settings_path.is_file():
        return {}

    try:
        raw = settings_path.read_text()
    except OSError as read_error:
        print(f"  ERROR: could not read {settings_path}: {read_error}", file=sys.stderr)
        raise SystemExit(1) from read_error

    try:
        return json.loads(raw)
    except json.JSONDecodeError as parse_error:
        backup_path = settings_path.with_name(settings_path.name + BACKUP_SUFFIX)
        try:
            backup_path.write_text(raw)
            print(
                f"  ERROR: {settings_path} is not valid JSON: {parse_error}",
                file=sys.stderr,
            )
            print(
                f"  Backed up the existing file to {backup_path} and aborted so no "
                "configuration is lost. Fix or remove the file, then re-run.",
                file=sys.stderr,
            )
        except OSError as backup_error:
            print(
                f"  ERROR: {settings_path} is not valid JSON and the backup to "
                f"{backup_path} also failed: {backup_error}",
                file=sys.stderr,
            )
        raise SystemExit(1) from parse_error


def main(settings_path: Path = SETTINGS_PATH) -> None:
    """Merge hook definitions and the AI_AGENT_ENV_PATH pin into settings.json.

    Args:
        settings_path: Path to the settings.json file to update. Defaults to the
            user's ~/.claude/settings.json; overridable for testing.

    Returns:
        None

    Raises:
        SystemExit: Propagated from load_settings when the existing file cannot be
            read or parsed.
    """
    settings = load_settings(settings_path)

    # Replace the hooks key wholesale so re-runs are idempotent (no duplicates).
    settings["hooks"] = HOOKS

    # Pin AI_AGENT_ENV_PATH to this repo's absolute path so hook commands resolve
    # even when the variable is absent from the Claude Code process environment.
    # setdefault preserves any other pre-existing keys inside the env block.
    settings.setdefault("env", {})[AI_AGENT_ENV_PATH_KEY] = str(REPO_ROOT)

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    print(f"  Merged hooks into {settings_path}")


if __name__ == "__main__":
    main()

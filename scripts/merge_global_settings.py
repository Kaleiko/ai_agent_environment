#!/usr/bin/env python3
"""Merge hook definitions into ~/.claude/settings.json.

Reads the existing settings file, sets/replaces the 'hooks' key with all
hook definitions (pointing to $AI_AGENT_ENV_PATH/hooks/), and writes back
without touching other keys (statusLine, alwaysThinkingEnabled, etc.).
"""

import json
import os
import sys
from pathlib import Path

SETTINGS_PATH = Path.home() / ".claude" / "settings.json"

# All hook definitions — commands reference $AI_AGENT_ENV_PATH so they
# work from any project directory without per-project copies.
HOOKS = {
    "PreToolUse": [
        {
            "matcher": "Bash|Read|Write|Edit",
            "hooks": [
                {
                    "type": "command",
                    "command": 'python3 "$AI_AGENT_ENV_PATH/hooks/pre_tool_use.py"',
                }
            ],
        }
    ],
    "PermissionRequest": [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": 'python3 "$AI_AGENT_ENV_PATH/hooks/permission_request.py"',
                }
            ],
        }
    ],
    "PostToolUseFailure": [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": 'python3 "$AI_AGENT_ENV_PATH/hooks/post_tool_use_failure.py"',
                }
            ],
        }
    ],
    "SubagentStop": [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": 'python3 "$AI_AGENT_ENV_PATH/hooks/subagent_stop.py"',
                }
            ],
        }
    ],
    "SubagentStart": [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": 'python3 "$AI_AGENT_ENV_PATH/hooks/subagent_start.py"',
                }
            ],
        }
    ],
    "Stop": [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": 'python3 "$AI_AGENT_ENV_PATH/hooks/session_stop.py"',
                }
            ],
        }
    ],
    "SessionStart": [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": 'python3 "$AI_AGENT_ENV_PATH/hooks/session_start.py"',
                }
            ],
        }
    ],
}


def main() -> None:
    # Read existing settings
    settings: dict = {}
    if SETTINGS_PATH.is_file():
        try:
            settings = json.loads(SETTINGS_PATH.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"  Warning: could not parse {SETTINGS_PATH}: {e}", file=sys.stderr)
            print("  Creating fresh settings with hooks only.", file=sys.stderr)
            settings = {}

    # Replace hooks key, preserve everything else
    settings["hooks"] = HOOKS

    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2) + "\n")
    print(f"  Merged hooks into {SETTINGS_PATH}")


if __name__ == "__main__":
    main()

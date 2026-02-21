#!/usr/bin/env python3
"""Subagent-stop hook.

Captures subagent transcripts into per-agent log directories when agents finish.
Logs to .claude/logs/agent-{agent_id}/
"""

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return

    agent_id = payload.get("agent_id", "unknown")
    agent_type = payload.get("agent_type", "unknown")
    transcript_path = payload.get("agent_transcript_path", "")
    cwd = payload.get("cwd", os.getcwd())

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")

    # Create per-agent log directory
    log_dir = Path(cwd) / ".claude" / "logs" / f"agent-{agent_id}"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Copy transcript if it exists
    if transcript_path and os.path.isfile(transcript_path):
        dest = log_dir / f"{timestamp}.jsonl"
        shutil.copy2(transcript_path, dest)

    # Write summary entry
    summary_file = log_dir / "summary.log"
    ts_display = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry = f"[{ts_display}] Agent {agent_id} ({agent_type}) completed\n"
    with open(summary_file, "a") as f:
        f.write(entry)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Subagent-stop hook.

Captures subagent transcripts into per-agent log directories when agents finish.
Logs to .claude/logs/agents/{agent_type}-{N}/
Uses .agent_map.json to map agent_id → directory name (shared with subagent_start).
"""

import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def get_agent_map(agents_dir: Path) -> dict:
    """Load the agent_id → directory name mapping."""
    map_file = agents_dir / ".agent_map.json"
    if map_file.is_file():
        try:
            return json.loads(map_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_agent_map(agents_dir: Path, agent_map: dict) -> None:
    """Save the agent_id → directory name mapping."""
    agents_dir.mkdir(parents=True, exist_ok=True)
    map_file = agents_dir / ".agent_map.json"
    map_file.write_text(json.dumps(agent_map, indent=2) + "\n")


def next_agent_number(agents_dir: Path, agent_type: str, agent_map: dict) -> int:
    """Find the next available number for this agent type (checks map + dirs)."""
    pattern = re.compile(rf"^{re.escape(agent_type)}-(\d+)$")
    max_num = 0
    # Check existing map entries (dirs may not exist yet)
    for dir_name in agent_map.values():
        m = pattern.match(dir_name)
        if m:
            max_num = max(max_num, int(m.group(1)))
    # Also check actual directories (in case map was lost/reset)
    if agents_dir.is_dir():
        for entry in agents_dir.iterdir():
            if entry.is_dir():
                m = pattern.match(entry.name)
                if m:
                    max_num = max(max_num, int(m.group(1)))
    return max_num + 1


def resolve_agent_dir(agents_dir: Path, agent_id: str, agent_type: str) -> Path:
    """Get or create the directory for this agent, using the map for consistency."""
    agent_map = get_agent_map(agents_dir)

    if agent_id in agent_map:
        return agents_dir / agent_map[agent_id]

    # Assign next number
    num = next_agent_number(agents_dir, agent_type, agent_map)
    dir_name = f"{agent_type}-{num}"
    agent_map[agent_id] = dir_name
    save_agent_map(agents_dir, agent_map)
    return agents_dir / dir_name


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return

    agent_id = payload.get("agent_id", "unknown")
    agent_type = payload.get("agent_type", "unknown")
    transcript_path = payload.get("agent_transcript_path", "")
    cwd = payload.get("cwd", os.getcwd())

    agents_dir = Path(cwd) / ".claude" / "logs" / "agents"
    log_dir = resolve_agent_dir(agents_dir, agent_id, agent_type)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Append transcript to continuous log
    if transcript_path and os.path.isfile(transcript_path):
        transcript_file = log_dir / "transcript.jsonl"
        with open(transcript_path, "r") as src, open(transcript_file, "a") as dst:
            dst.write(src.read())

    # Append structured summary entry
    summary_file = log_dir / "summary.jsonl"
    entry = {
        "_timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id,
        "agent_type": agent_type,
        "event": "completed",
    }
    with open(summary_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Subagent-stop hook.

Captures subagent transcripts into per-agent log directories when agents finish.
Logs to .claude/logs/agents/{agent_type}-{N}/
Uses .agent_map.json to map agent_id → directory name (shared with subagent_start).

This hook is what actually creates the directory, so the agent type -- which
arrives in the payload -- is sanitised before it becomes a path component. The
derivation lives in hook_paths so subagent_start computes the identical name.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from hook_paths import agent_dir_prefix, derive_agent_dir_name, get_project_root


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


def resolve_agent_dir(agents_dir: Path, agent_id: str, agent_type: str) -> Path:
    """Get or create the directory for this agent, using the map for consistency.

    An agent already in the map keeps the directory it was given, so existing
    directories -- including the "-18" style names an empty type used to produce
    -- keep resolving exactly as before.

    Args:
        agents_dir: The ``.claude/logs/agents`` directory.
        agent_id: The finishing agent's id.
        agent_type: The agent type from the payload, possibly empty or unsafe.

    Returns:
        The directory this agent's logs belong in, always inside ``agents_dir``.
    """
    agent_map = get_agent_map(agents_dir)

    if agent_id in agent_map:
        return agents_dir / str(agent_map[agent_id])

    dir_name = derive_agent_dir_name(agents_dir, agent_type, agent_map)
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
    # Anchor logs to the stable project root, not the tool's live cwd.
    project_root = get_project_root(payload)

    agents_dir = Path(project_root) / ".claude" / "logs" / "agents"
    log_dir = resolve_agent_dir(agents_dir, agent_id, agent_type)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Append transcript to continuous log
    if transcript_path and os.path.isfile(transcript_path):
        transcript_file = log_dir / "transcript.jsonl"
        with open(transcript_path, "r") as src, open(transcript_file, "a") as dst:
            dst.write(src.read())

    # Append structured summary entry. The raw agent_type is recorded whatever it
    # was; the directory name is named only when sanitising had to change it, so
    # the original value is never lost to the substitution.
    summary_file = log_dir / "summary.jsonl"
    entry = {
        "_timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id,
        "agent_type": agent_type,
    }
    if agent_dir_prefix(agent_type) != agent_type:
        entry["agent_dir"] = log_dir.name
    entry["event"] = "completed"
    with open(summary_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    main()

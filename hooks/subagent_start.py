#!/usr/bin/env python3
"""Subagent-start hook.

Injects skill file contents as additionalContext when mapped subagents spawn.
Two-tier skill lookup: project .claude/skills/ first, then $AI_AGENT_ENV_PATH/skills/.
Logs to .claude/logs/audit/subagent_start.jsonl.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MB

# Map agent types to skill files in .claude/skills/
AGENT_SKILLS = {
    "python-developer": ["python-conventions.md"],
    "next-developer": ["next-conventions.md"],
}


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


def register_agent(cwd: str, agent_id: str, agent_type: str) -> None:
    """Register agent_id → directory mapping so subagent_stop uses the same dir."""
    agents_dir = Path(cwd) / ".claude" / "logs" / "agents"
    agent_map = get_agent_map(agents_dir)
    if agent_id not in agent_map:
        num = next_agent_number(agents_dir, agent_type, agent_map)
        agent_map[agent_id] = f"{agent_type}-{num}"
        save_agent_map(agents_dir, agent_map)


def log_audit(
    cwd: str, agent_id: str, agent_type: str, skills_injected: list[str]
) -> None:
    """Log start event to audit file."""
    audit_dir = Path(cwd) / ".claude" / "logs" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_file = audit_dir / "subagent_start.jsonl"

    entry = {
        "agent_id": agent_id,
        "agent_type": agent_type,
        "skills_injected": skills_injected,
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

    agent_type = payload.get("agent_type", "")
    agent_id = payload.get("agent_id", "unknown")
    cwd = payload.get("cwd", os.getcwd())

    # Register agent in map for consistent directory naming with subagent_stop
    if agent_type:
        register_agent(cwd, agent_id, agent_type)

    # Only inject for mapped agent types
    skill_files = AGENT_SKILLS.get(agent_type)
    if not skill_files:
        return

    skill_files = list(skill_files)

    # Read each skill file — two-tier lookup:
    # 1. Project override: {cwd}/.claude/skills/{filename}
    # 2. Repo default:     $AI_AGENT_ENV_PATH/skills/{filename}
    project_skills_dir = Path(cwd) / ".claude" / "skills"
    repo_skills_dir = None
    env_path = os.environ.get("AI_AGENT_ENV_PATH")
    if env_path:
        repo_skills_dir = Path(env_path) / "skills"

    contents = []
    loaded = []

    for filename in skill_files:
        skill_path = project_skills_dir / filename
        if not skill_path.is_file() and repo_skills_dir:
            skill_path = repo_skills_dir / filename
        if not skill_path.is_file():
            continue
        text = skill_path.read_text().strip()
        if text:
            contents.append(text)
            loaded.append(f"{filename} ({skill_path.parent})")

    if not contents:
        log_audit(cwd, agent_id, agent_type, [])
        return

    # Return as additionalContext
    combined = "\n\n---\n\n".join(contents)
    result = {
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": f"## Injected Skills\n\n{combined}",
        }
    }
    print(json.dumps(result))

    log_audit(cwd, agent_id, agent_type, loaded)


if __name__ == "__main__":
    main()

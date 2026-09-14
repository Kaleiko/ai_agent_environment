#!/usr/bin/env python3
"""Shared path helpers for Claude Code hooks.

Single source of truth for two things: the stable project root that hook log
directories are anchored to, and the name of the per-agent log directory that
``subagent_start`` and ``subagent_stop`` must agree on. Hooks are invoked as
standalone scripts, and Python places the script's own directory on
``sys.path``, so sibling hook modules can ``import hook_paths`` directly.

The agent directory name lives here because the two hooks share
``.agent_map.json``: ``subagent_start`` records the name and ``subagent_stop``
creates the directory. If they derived it differently they would compute
different names for the same agent and the mapping would silently break, so
they derive it from one implementation.

Anchoring log directories to the project root (rather than the payload's live
``cwd``) prevents logs from being scattered into subdirectories when a tool
changes the working directory mid-session -- e.g. a ``cd hooks`` inside a Bash
command previously caused a brand-new ``hooks/.claude/logs/`` tree to be
created and subsequent entries to land there.
"""

import os
import re
from pathlib import Path

CLAUDE_PROJECT_DIR_ENV = "CLAUDE_PROJECT_DIR"

# A name safe to use as a single path component: no separators, no traversal,
# no leading dot. Deliberately permissive enough that every agent type already
# on disk (python-developer, claude-code-guide, general-purpose, Plan) passes
# through unchanged, so existing log directories keep resolving.
SAFE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

# Stands in for an agent type that cannot be used as a path component, the empty
# string included. An empty type previously produced directories named "-18",
# "-19", "-20"; those stay where they are, but new ones read as "unknown-1".
UNKNOWN_AGENT_DIR_PREFIX = "unknown"


def get_project_root(payload: dict) -> str:
    """Resolve the stable project root for anchoring hook log directories.

    Resolution order:
        1. The ``CLAUDE_PROJECT_DIR`` environment variable, if set and
           non-empty. Claude Code guarantees this is present for hook
           subprocesses and it stays stable for the whole session regardless of
           the tool's current working directory.
        2. The payload's ``cwd`` field, if present and non-empty.
        3. The process's current working directory, as a last resort.

    This MUST be used only to decide WHERE to write logs. It MUST NOT be used
    for the security checks that compare tool file paths against the real
    working directory -- those legitimately need the live ``cwd``.

    Args:
        payload: The hook's JSON payload decoded from stdin.

    Returns:
        A directory path to anchor ``.claude/`` log directories to.
    """
    project_dir = os.environ.get(CLAUDE_PROJECT_DIR_ENV, "").strip()
    if project_dir:
        return project_dir
    cwd = payload.get("cwd", "")
    if cwd:
        return cwd
    return os.getcwd()


def is_safe_name(name: str) -> bool:
    """Report whether a name may be joined onto a directory as one component.

    Args:
        name: A candidate file, directory, or agent-type name.

    Returns:
        ``True`` when the name cannot traverse out of its parent directory.
    """
    return bool(SAFE_NAME_PATTERN.fullmatch(name)) and ".." not in name


def agent_dir_prefix(agent_type: str) -> str:
    """Reduce an agent type to a prefix safe to use as a directory name.

    The agent type arrives in the hook payload, so it must never be able to
    steer directory creation outside the agents log directory. A safe type is
    returned untouched, which keeps every existing directory name stable.

    Args:
        agent_type: The agent type from the payload, possibly empty or unsafe.

    Returns:
        The agent type itself, or ``UNKNOWN_AGENT_DIR_PREFIX``.
    """
    return agent_type if is_safe_name(agent_type) else UNKNOWN_AGENT_DIR_PREFIX


def next_agent_number(agents_dir: Path, prefix: str, agent_map: dict) -> int:
    """Find the next free number for a directory prefix.

    Checks the map (directories may not exist yet) and the directories
    themselves (in case the map was lost or reset).

    Args:
        agents_dir: The ``.claude/logs/agents`` directory.
        prefix: A sanitised directory prefix from ``agent_dir_prefix``.
        agent_map: The decoded ``.agent_map.json`` contents.

    Returns:
        One past the highest number already in use for this prefix.
    """
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    max_num = 0
    for dir_name in agent_map.values():
        match = pattern.match(str(dir_name))
        if match:
            max_num = max(max_num, int(match.group(1)))
    if agents_dir.is_dir():
        for entry in agents_dir.iterdir():
            if entry.is_dir():
                match = pattern.match(entry.name)
                if match:
                    max_num = max(max_num, int(match.group(1)))
    return max_num + 1


def derive_agent_dir_name(agents_dir: Path, agent_type: str, agent_map: dict) -> str:
    """Derive the log directory name for a newly seen agent.

    Both subagent hooks call this so they can never disagree on the name.

    Args:
        agents_dir: The ``.claude/logs/agents`` directory.
        agent_type: The agent type from the payload, possibly empty or unsafe.
        agent_map: The decoded ``.agent_map.json`` contents.

    Returns:
        A directory name of the form ``{safe_prefix}-{number}``.
    """
    prefix = agent_dir_prefix(agent_type)
    return f"{prefix}-{next_agent_number(agents_dir, prefix, agent_map)}"

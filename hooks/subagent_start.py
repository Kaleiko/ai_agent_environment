#!/usr/bin/env python3
"""Subagent-start hook.

Injects skill file contents as additionalContext when mapped subagents spawn.
Two-tier skill lookup: project .claude/skills/ first, then the repo's own
skills/ directory (resolved from this hook's location — no environment variable).

Every invocation writes an audit record to .claude/logs/audit/subagent_start.jsonl,
including invocations that inject nothing. A payload whose agent-type field is
renamed or blanked out by a Claude Code update must never again turn this hook
into a silent no-op: it now records the payload's shape and tells the spawning
agent to read the conventions itself.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from hook_paths import (
    agent_dir_prefix,
    derive_agent_dir_name,
    get_project_root,
    is_safe_name,
)

MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MB

# Repo root derived from THIS hook's own location so skill lookup and placeholder
# substitution need no environment variable and survive the repo being moved.
# This file lives at <repo>/hooks/subagent_start.py, so repo root is parent.parent.
REPO_ROOT = Path(__file__).resolve().parent.parent

# Placeholder used inside injected skill markdown in place of a hard-coded repo
# path (e.g. skills/python-conventions.md references it for template paths). It is
# substituted with the absolute repo root at injection time.
SKILL_PATH_PLACEHOLDER = "{{AI_AGENT_ENV_PATH}}"

# Fallback map of agent type to skill files, used ONLY when an agent definition
# file cannot be found or carries no frontmatter. The `skills:` frontmatter in
# agents/<type>.md is the source of truth; this exists so a missing or malformed
# definition degrades to the historical behaviour instead of silently injecting
# nothing. Any disagreement between the two is recorded in the audit log.
AGENT_SKILLS = {
    "python-developer": ["python-conventions.md"],
    "next-developer": ["next-conventions.md"],
    "e2e-developer": ["playwright-conventions.md"],
}

# Extension shared by skill files and agent definition files.
MARKDOWN_SUFFIX = ".md"

# Where a skill list came from, recorded in the audit log so the dict and the
# frontmatter can never disagree unnoticed.
SKILLS_SOURCE_FRONTMATTER = "agent_frontmatter"
SKILLS_SOURCE_NO_SKILLS_KEY = "agent_frontmatter_no_skills"
SKILLS_SOURCE_FALLBACK_DICT = "agent_skills_fallback"

# The agent type arrives in the payload and skill names come from a file a project
# can override, so neither may be allowed to traverse out of the directory it is
# resolved against. The check itself lives in hook_paths, shared with
# subagent_stop, which derives the same directory names.

# Payload keys that may carry the spawning agent's type. Claude Code has changed
# the shape of this payload before, so every plausible spelling is tried in order
# and the first non-empty value wins. An empty string is treated as absent, which
# is the exact failure this ordering exists to survive.
AGENT_TYPE_KEYS = (
    "agent_type",
    "subagent_type",
    "agentType",
    "subagentType",
    "agent_name",
    "agentName",
    "name",
    "type",
)

# Nested payload objects that may themselves contain one of AGENT_TYPE_KEYS.
# Checked only after every top-level key has come up empty.
NESTED_PAYLOAD_KEYS = (
    "agent",
    "subagent",
    "tool_input",
    "toolInput",
    "params",
    "input",
)

# Payload keys that may carry the spawning agent's id.
AGENT_ID_KEYS = ("agent_id", "agentId", "id")

# Diagnostic capture limits. An unresolved payload is written into the audit
# record so the next real spawn reveals what the agent-type field is now called,
# but transcripts and file contents must never be copied into the log.
MAX_CAPTURED_PAYLOAD_BYTES = 4096
MAX_CAPTURED_VALUE_CHARS = 200
MAX_CAPTURED_LIST_ITEMS = 10
REDACTED_MARKER = "<redacted>"
TRUNCATED_SUFFIX = "...<truncated>"

# Substrings marking a key whose value is bulk text (a transcript, a prompt, a
# file body) that must be redacted rather than copied into the audit record.
REDACTED_KEY_MARKERS = (
    "transcript",
    "content",
    "prompt",
    "message",
    "text",
    "body",
    "context",
    "instruction",
    "history",
    "token",
    "secret",
    "key",
)

# Audit notes distinguishing the non-injecting outcomes from one another.
NOTE_UNDECODABLE_PAYLOAD = "payload_not_decodable"
NOTE_UNMAPPED_AGENT_TYPE = "unmapped_agent_type"
NOTE_NO_SKILLS_DECLARED = "no_skills_declared"
NOTE_UNRESOLVED_AGENT_TYPE = "agent_type_unresolved"

FRONTMATTER_DELIMITER = "---"

# Emitted in place of a skill body when the agent type cannot be resolved.
# Guessing would be wrong roughly half the time — python-conventions and
# playwright-conventions both claim **/*.py — so the agent is told to choose.
UNRESOLVED_CONTEXT_TEMPLATE = """## Conventions NOT Injected — You MUST Read Them Yourself

The SubagentStart hook could not determine which agent type is spawning, so no
convention skill was injected into your context automatically. Do not treat this
as permission to skip conventions.

**Before you write or edit ANY code, you MUST read the convention file matching
the code you are about to write.** Read it from the absolute path below with the
Read tool. Do not work from memory, and do not start coding first.

Available convention files:

{skill_list}

More than one file can claim the same extension, so choose by what the project
actually is. Python code in a Playwright end-to-end test repository (a `pages/`
directory at the project root, or `playwright` in `pyproject.toml` /
`requirements.txt`) follows `playwright-conventions.md`; Python code in any other
project follows `python-conventions.md`."""


def substitute_repo_path(text: str, repo_root: Path) -> str:
    """Replace the AI_AGENT_ENV_PATH placeholder with the absolute repo root.

    Skills are injected as text into subagent context, so any repo-relative path
    reference in the markdown must be resolved to a concrete absolute path before
    injection rather than relying on the reader's environment.

    Args:
        text: Skill file contents that may contain SKILL_PATH_PLACEHOLDER.
        repo_root: Absolute path to the repo root to substitute in.

    Returns:
        The text with every placeholder occurrence replaced by the repo root.
    """
    return text.replace(SKILL_PATH_PLACEHOLDER, str(repo_root))


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


def first_non_empty_string(source: dict, keys: tuple[str, ...]) -> tuple[str, str]:
    """Return the first non-empty string value among the given keys.

    An empty or whitespace-only string counts as absent, so a payload that
    supplies the key with a blank value is treated the same as one that omits it.

    Args:
        source: Mapping to read values from.
        keys: Candidate keys, in priority order.

    Returns:
        A ``(value, key)`` pair, or ``("", "")`` when no key holds a non-empty string.
    """
    for key in keys:
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip(), key
    return "", ""


def resolve_agent_type(payload: dict) -> tuple[str, str]:
    """Resolve the spawning agent's type from any key the payload might use.

    Top-level keys are tried first in AGENT_TYPE_KEYS order, then the same keys
    inside each nested container in NESTED_PAYLOAD_KEYS.

    Args:
        payload: The hook's JSON payload decoded from stdin.

    Returns:
        A ``(agent_type, source_key)`` pair, where ``source_key`` is dotted for a
        nested hit (e.g. ``"agent.name"``). ``("", "")`` when nothing resolves.
    """
    agent_type, source_key = first_non_empty_string(payload, AGENT_TYPE_KEYS)
    if agent_type:
        return agent_type, source_key

    for container_key in NESTED_PAYLOAD_KEYS:
        nested = payload.get(container_key)
        if not isinstance(nested, dict):
            continue
        agent_type, source_key = first_non_empty_string(nested, AGENT_TYPE_KEYS)
        if agent_type:
            return agent_type, f"{container_key}.{source_key}"

    return "", ""


def resolve_agent_id(payload: dict) -> str:
    """Resolve the spawning agent's id, falling back to ``"unknown"``.

    Args:
        payload: The hook's JSON payload decoded from stdin.

    Returns:
        The agent id, or ``"unknown"`` when no candidate key holds a value.
    """
    agent_id, _ = first_non_empty_string(payload, AGENT_ID_KEYS)
    return agent_id or "unknown"


def redact_payload_value(key: str, value: object) -> object:
    """Redact or truncate one payload value so bulk text never reaches the log.

    Values under a key naming bulk text (a transcript, a prompt, a file body) are
    replaced wholesale; any other over-long string is truncated. Containers are
    walked recursively and lists are capped.

    Args:
        key: The key the value was stored under, used to spot bulk-text fields.
        value: The value to redact.

    Returns:
        A JSON-serialisable value safe to write into the audit record.
    """
    lowered = key.lower()
    if any(marker in lowered for marker in REDACTED_KEY_MARKERS):
        return REDACTED_MARKER
    if isinstance(value, str):
        if len(value) > MAX_CAPTURED_VALUE_CHARS:
            return value[:MAX_CAPTURED_VALUE_CHARS] + TRUNCATED_SUFFIX
        return value
    if isinstance(value, dict):
        return {k: redact_payload_value(str(k), v) for k, v in value.items()}
    if isinstance(value, list):
        return [
            redact_payload_value(key, item) for item in value[:MAX_CAPTURED_LIST_ITEMS]
        ]
    return value


def capture_payload(payload: dict) -> dict | None:
    """Build a redacted copy of the payload small enough to store in the audit log.

    Args:
        payload: The hook's JSON payload decoded from stdin.

    Returns:
        The redacted payload, or ``None`` when it is still too large to store or
        cannot be serialised.
    """
    redacted = {str(k): redact_payload_value(str(k), v) for k, v in payload.items()}
    try:
        serialized = json.dumps(redacted)
    except (TypeError, ValueError):
        return None
    if len(serialized.encode("utf-8")) > MAX_CAPTURED_PAYLOAD_BYTES:
        return None
    return redacted


def parse_frontmatter(text: str) -> dict[str, str | list[str]]:
    """Extract top-level fields from a markdown file's YAML frontmatter.

    Handles the two shapes the skill and agent files actually use: a scalar
    ``key: value`` line, and a block sequence such as the ``skills:`` list in an
    agent definition. Anything more elaborate is out of scope on purpose -- this
    hook must never fail to start, so it takes no YAML dependency.

    A key whose value is empty yields a list, which stays empty when no ``- item``
    lines follow it.

    Args:
        text: Full file contents.

    Returns:
        A mapping of frontmatter key to either its raw string value or the list of
        its block-sequence items. Empty when the file has no frontmatter block.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_DELIMITER:
        return {}

    fields: dict[str, str | list[str]] = {}
    open_list_key = ""

    for line in lines[1:]:
        if line.strip() == FRONTMATTER_DELIMITER:
            break

        item_match = re.match(r"^\s*-\s+(.*)$", line)
        if item_match and open_list_key:
            item = item_match.group(1).strip().strip('"').strip("'")
            if item:
                fields[open_list_key].append(item)  # type: ignore[union-attr]
            continue

        key_match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not key_match:
            open_list_key = ""
            continue

        key = key_match.group(1)
        raw_value = key_match.group(2).strip()
        if raw_value:
            fields[key] = raw_value.strip('"').strip("'")
            open_list_key = ""
        else:
            # An empty value opens a possible block sequence, e.g. "skills:".
            fields[key] = []
            open_list_key = key

    return fields


def parse_inline_list(value: str) -> list[str]:
    """Split a scalar frontmatter value into list items.

    Accepts a YAML flow sequence (``[a, b]``) or a bare scalar, so a ``skills:``
    key written on one line is honoured as readily as a block sequence.

    Args:
        value: The raw scalar value read from the frontmatter.

    Returns:
        The items, in order, with empties dropped.
    """
    text = value.strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
        return [
            item.strip().strip('"').strip("'")
            for item in text.split(",")
            if item.strip()
        ]
    return [text] if text else []


def normalize_skill_filename(skill_name: str) -> str:
    """Turn a declared skill name into the file name to look up.

    Frontmatter lists skill names (``python-conventions``), but a user may
    reasonably write the file name instead, so both spellings are accepted.

    Args:
        skill_name: The name as declared in an agent definition's ``skills:`` list.

    Returns:
        The skill file name, or ``""`` when the name is empty or unsafe.
    """
    name = skill_name.strip().strip('"').strip("'")
    if not name:
        return ""
    if not name.endswith(MARKDOWN_SUFFIX):
        name = f"{name}{MARKDOWN_SUFFIX}"
    return name if is_safe_name(name) else ""


def resolve_skill_path(cwd: str, filename: str) -> Path | None:
    """Locate a skill file using the two-tier lookup.

    Args:
        cwd: Project root whose ``.claude/skills/`` may override the repo default.
        filename: Skill file name, e.g. ``"python-conventions.md"``.

    Returns:
        The project override if present, else the repo default, else ``None``.
    """
    project_path = Path(cwd) / ".claude" / "skills" / filename
    if project_path.is_file():
        return project_path
    repo_path = REPO_ROOT / "skills" / filename
    if repo_path.is_file():
        return repo_path
    return None


def resolve_agent_definition_path(cwd: str, agent_type: str) -> Path | None:
    """Locate an agent definition file using the same two-tier lookup as skills.

    Args:
        cwd: Project root whose ``.claude/agents/`` may override the repo default.
        agent_type: The resolved agent type, e.g. ``"python-developer"``.

    Returns:
        The project override if present, else the repo default, else ``None``
        (which also covers an agent type unsafe to use as a file name).
    """
    if not is_safe_name(agent_type):
        return None
    filename = f"{agent_type}{MARKDOWN_SUFFIX}"
    project_path = Path(cwd) / ".claude" / "agents" / filename
    if project_path.is_file():
        return project_path
    repo_path = REPO_ROOT / "agents" / filename
    if repo_path.is_file():
        return repo_path
    return None


def resolve_agent_skill_files(
    cwd: str, agent_type: str
) -> tuple[list[str], str, Path | None]:
    """Resolve which skill files an agent type should be injected with.

    The agent definition's ``skills:`` frontmatter is authoritative. An agent that
    declares no ``skills:`` key injects nothing -- that is a deliberate choice the
    plan-* agents rely on, not a reason to fall back. AGENT_SKILLS is consulted
    only when there is no usable definition file at all, so a missing or
    frontmatter-less file degrades to the historical behaviour.

    Args:
        cwd: Project root used for the two-tier agent lookup.
        agent_type: The resolved agent type.

    Returns:
        A ``(skill_filenames, source, agent_definition_path)`` triple, where
        ``source`` is one of the ``SKILLS_SOURCE_*`` constants.
    """
    agent_path = resolve_agent_definition_path(cwd, agent_type)
    fallback = list(AGENT_SKILLS.get(agent_type, []))

    if agent_path is None:
        return fallback, SKILLS_SOURCE_FALLBACK_DICT, None

    try:
        frontmatter = parse_frontmatter(agent_path.read_text())
    except OSError:
        frontmatter = {}

    if not frontmatter:
        # Unreadable or frontmatter-less definition: not a declaration of "no
        # skills", just an unusable file.
        return fallback, SKILLS_SOURCE_FALLBACK_DICT, agent_path

    if "skills" not in frontmatter:
        return [], SKILLS_SOURCE_NO_SKILLS_KEY, agent_path

    declared = frontmatter["skills"]
    if isinstance(declared, str):
        declared = parse_inline_list(declared)

    filenames: list[str] = []
    for entry in declared:
        filename = normalize_skill_filename(str(entry))
        if filename and filename not in filenames:
            filenames.append(filename)

    return filenames, SKILLS_SOURCE_FRONTMATTER, agent_path


def skills_source_fields(
    agent_type: str, skill_files: list[str], skills_source: str, agent_path: Path | None
) -> dict:
    """Build the audit fields naming where the skill list came from.

    Omitted only in the one case where there is nothing to notice: the frontmatter
    was authoritative AND it agrees with AGENT_SKILLS. Every divergence, every
    fallback, and every "declares no skills" outcome is therefore recorded.

    Args:
        agent_type: The resolved agent type.
        skill_files: The skill file names that were resolved.
        skills_source: One of the ``SKILLS_SOURCE_*`` constants.
        agent_path: The agent definition file used, if any.

    Returns:
        Audit fields to merge into the log record, possibly empty.
    """
    dict_files = list(AGENT_SKILLS.get(agent_type, []))
    if skills_source == SKILLS_SOURCE_FRONTMATTER and skill_files == dict_files:
        return {}

    fields: dict = {"skills_source": skills_source}
    if agent_path is not None:
        fields["agent_definition"] = str(agent_path)
    if skills_source == SKILLS_SOURCE_FRONTMATTER:
        fields["skills_divergence"] = {
            "frontmatter": skill_files,
            "agent_skills": dict_files,
        }
    return fields


def available_skill_filenames(cwd: str) -> list[str]:
    """List every skill file that actually exists across both lookup tiers.

    Enumerating the directories rather than AGENT_SKILLS keeps a newly added skill
    visible in the unresolved-agent fallback without anyone editing this hook.

    Args:
        cwd: Project root whose ``.claude/skills/`` may add or override skills.

    Returns:
        Sorted, de-duplicated skill file names.
    """
    filenames = set()
    for directory in (Path(cwd) / ".claude" / "skills", REPO_ROOT / "skills"):
        if not directory.is_dir():
            continue
        try:
            entries = list(directory.iterdir())
        except OSError:
            continue
        for entry in entries:
            if (
                entry.is_file()
                and entry.name.endswith(MARKDOWN_SUFFIX)
                and is_safe_name(entry.name)
            ):
                filenames.add(entry.name)
    return sorted(filenames)


def build_unresolved_context(cwd: str) -> str:
    """Build the additionalContext telling an unidentified agent to read conventions.

    Args:
        cwd: Project root used for the two-tier skill lookup.

    Returns:
        The directive markdown block, or ``""`` when no skill file could be found
        and there is therefore nothing to point the agent at.
    """
    entries = []
    for filename in available_skill_filenames(cwd):
        skill_path = resolve_skill_path(cwd, filename)
        if skill_path is None:
            continue
        try:
            frontmatter = parse_frontmatter(skill_path.read_text())
        except OSError:
            frontmatter = {}
        declared_name = frontmatter.get("name")
        name = (
            declared_name
            if isinstance(declared_name, str) and declared_name
            else skill_path.stem
        )
        entry = f"- **{name}** — `{skill_path}`"
        globs = frontmatter.get("globs")
        if isinstance(globs, str) and globs:
            entry += f"\n  - Applies to: {globs}"
        description = frontmatter.get("description")
        if isinstance(description, str) and description:
            entry += f"\n  - {description}"
        entries.append(entry)

    if not entries:
        return ""
    return UNRESOLVED_CONTEXT_TEMPLATE.format(skill_list="\n".join(entries))


def emit_context(context: str) -> None:
    """Print a SubagentStart additionalContext result to stdout.

    Args:
        context: The markdown block to hand to the spawning subagent.
    """
    result = {
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": context,
        }
    }
    print(json.dumps(result))


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


def register_agent(cwd: str, agent_id: str, agent_type: str) -> str:
    """Register agent_id → directory mapping so subagent_stop uses the same dir.

    Args:
        cwd: Project root the ``.claude/logs/`` tree is anchored to.
        agent_id: The spawning agent's id.
        agent_type: The resolved agent type, sanitised before use as a path.

    Returns:
        The directory name recorded for this agent, existing or newly derived.
    """
    agents_dir = Path(cwd) / ".claude" / "logs" / "agents"
    agent_map = get_agent_map(agents_dir)
    if agent_id in agent_map:
        return str(agent_map[agent_id])
    dir_name = derive_agent_dir_name(agents_dir, agent_type, agent_map)
    agent_map[agent_id] = dir_name
    save_agent_map(agents_dir, agent_map)
    return dir_name


def log_audit(
    cwd: str,
    agent_id: str,
    agent_type: str,
    skills_injected: list[str],
    extra: dict | None = None,
) -> None:
    """Log a start event to the audit file.

    Called on every code path, including the ones that inject nothing, so that a
    no-op invocation is always visible in the audit trail.

    Args:
        cwd: Project root the ``.claude/logs/`` tree is anchored to.
        agent_id: The spawning agent's id, or ``"unknown"``.
        agent_type: The resolved agent type, or ``""`` when unresolvable.
        skills_injected: Descriptions of the skill files injected, possibly empty.
        extra: Additional diagnostic fields merged in before the timestamp.
    """
    entry = {
        "agent_id": agent_id,
        "agent_type": agent_type,
        "skills_injected": skills_injected,
    }
    if extra:
        entry.update(extra)
    entry["_timestamp"] = datetime.now(timezone.utc).isoformat()

    try:
        audit_dir = Path(cwd) / ".claude" / "logs" / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / "subagent_start.jsonl"
        with open(audit_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        enforce_max_size_text(audit_file)
    except OSError:
        # Auditing must never take the hook down and block a subagent spawn.
        return


def handle_unresolved(cwd: str, agent_id: str, payload: dict) -> None:
    """Emit the read-the-conventions fallback and record the payload's shape.

    The captured key list is the diagnostic that identifies what the agent-type
    field is actually called, so the next real spawn settles it.

    Args:
        cwd: Project root for skill lookup and log anchoring.
        agent_id: The spawning agent's id, or ``"unknown"``.
        payload: The hook's JSON payload decoded from stdin.
    """
    context = build_unresolved_context(cwd)
    if context:
        emit_context(context)

    extra = {
        "note": NOTE_UNRESOLVED_AGENT_TYPE,
        "fallback_emitted": bool(context),
        "unresolved_payload_keys": sorted(str(key) for key in payload),
    }
    captured = capture_payload(payload)
    if captured is not None:
        extra["unresolved_payload"] = captured

    log_audit(cwd, agent_id, "", [], extra)


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        payload = None

    if not isinstance(payload, dict):
        log_audit(
            get_project_root({}), "unknown", "", [], {"note": NOTE_UNDECODABLE_PAYLOAD}
        )
        return

    agent_type, resolved_from = resolve_agent_type(payload)
    agent_id = resolve_agent_id(payload)
    # Anchor logs and project skill lookup to the stable project root.
    cwd = get_project_root(payload)

    # No agent type means no safe guess: python-conventions and
    # playwright-conventions both claim **/*.py, so tell the agent to choose.
    if not agent_type:
        handle_unresolved(cwd, agent_id, payload)
        return

    # Register agent in map for consistent directory naming with subagent_stop
    agent_dir_name = register_agent(cwd, agent_id, agent_type)

    # Record which key supplied the type only when it was not the expected one,
    # so the audit line for a normal spawn stays exactly as it has always been.
    extra = (
        {} if resolved_from == AGENT_TYPE_KEYS[0] else {"resolved_from": resolved_from}
    )

    # The raw agent_type is always logged above; name the directory only when it
    # had to be sanitised, so the real type is never lost to the substitution.
    if agent_dir_prefix(agent_type) != agent_type:
        extra["agent_dir_name"] = agent_dir_name

    # The agent definition's `skills:` frontmatter decides what gets injected;
    # AGENT_SKILLS only covers a missing or unusable definition file.
    skill_files, skills_source, agent_path = resolve_agent_skill_files(cwd, agent_type)
    extra.update(
        skills_source_fields(agent_type, skill_files, skills_source, agent_path)
    )

    if not skill_files:
        # An agent that declares no skills injects nothing, by design; an agent
        # nothing knows about is a different, louder outcome.
        note = (
            NOTE_NO_SKILLS_DECLARED
            if skills_source == SKILLS_SOURCE_NO_SKILLS_KEY
            else NOTE_UNMAPPED_AGENT_TYPE
        )
        log_audit(cwd, agent_id, agent_type, [], {**extra, "note": note})
        return

    contents = []
    loaded = []

    for filename in skill_files:
        skill_path = resolve_skill_path(cwd, filename)
        if skill_path is None:
            continue
        text = substitute_repo_path(skill_path.read_text().strip(), REPO_ROOT)
        if text:
            contents.append(text)
            loaded.append(f"{filename} ({skill_path.parent})")

    if not contents:
        log_audit(cwd, agent_id, agent_type, [], extra)
        return

    # Return as additionalContext
    combined = "\n\n---\n\n".join(contents)
    emit_context(f"## Injected Skills\n\n{combined}")

    log_audit(cwd, agent_id, agent_type, loaded, extra)


if __name__ == "__main__":
    main()

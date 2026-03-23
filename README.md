# AI Agent Environment

A centralized repository for Claude Code skills, agents, hooks, and prompts. Everything is installed globally — no per-project setup required.

## Contents

- [Architecture](#architecture)
- [Setup](#setup)
- [How It Works](#how-it-works)
- [Skills](#skills)
- [Agents](#agents)
- [Hooks](#hooks)
- [Project Overrides](#project-overrides)

## Architecture

```
~/.claude/ (Global — installed by install.sh)
├── settings.json          # Hooks (merged, preserving existing keys)
├── rules/
│   ├── global_prompts.md  # Existing (imports CLAUDE.md)
│   └── delegation.md      # Agent delegation rules (always loaded)
├── agents/
│   ├── python-developer.md
│   └── next-developer.md
└── skills/
    └── ai-interaction/    # Communication guidelines
        └── SKILL.md

$AI_AGENT_ENV_PATH/ (Repo — source of truth)
├── install.sh             # Global installer
├── scripts/
│   └── merge_global_settings.py  # Safely merges hooks into settings.json
├── hooks/                 # Run directly from repo via $AI_AGENT_ENV_PATH
│   ├── pre_tool_use.py
│   ├── permission_request.py
│   ├── post_tool_use_failure.py
│   ├── subagent_stop.py
│   ├── subagent_start.py
│   ├── session_stop.py
│   └── session_start.py
├── skills/                # Convention files (read by subagent_start hook)
├── agents/                # Agent definitions (source of truth)
└── prompts/
    └── delegation.md      # Source of truth (copied to ~/.claude/rules/)

Project .claude/ (Per-project — auto-created by hooks)
├── logs/                  # Created automatically by hooks
│   ├── last_session.md
│   ├── security/
│   ├── audit/
│   └── agents/
└── skills/                # OPTIONAL: project-specific overrides
```

## Setup

```bash
git clone <repo-url> && cd ai_agent_environment
./install.sh
source ~/.zshrc  # or ~/.bashrc
```

Then restart Claude Code. That's it — no per-project setup needed.

The install script:
1. Copies `ai-interaction` skill to `~/.claude/skills/`
2. Copies `delegation.md` to `~/.claude/rules/`
3. Copies agent definitions to `~/.claude/agents/`
4. Merges hook definitions into `~/.claude/settings.json` (preserving existing keys)
5. Sets `AI_AGENT_ENV_PATH` environment variable

### Updating

Re-run the install script after pulling changes:
```bash
./install.sh
```
Then restart Claude Code.

## How It Works

1. **Hooks** run from the repo via `$AI_AGENT_ENV_PATH` — no per-project copies needed
2. **Delegation rules** in `~/.claude/rules/delegation.md` are always loaded, telling Claude when to delegate to subagents
3. **Agents** in `~/.claude/agents/` define subagent behavior (python-developer, next-developer)
4. **Skills** are injected into subagents by the `subagent_start` hook at spawn time
5. **Logs** are written to each project's `.claude/logs/` directory automatically

## Skills

| Skill | Purpose | Location |
|-------|---------|----------|
| `ai-interaction` | Communication standards, code review process | Global (`~/.claude/skills/`) |
| `python-conventions` | Code style, error handling, logging, testing | Repo (`skills/`), injected by hook |
| `next-conventions` | Next.js/TypeScript conventions | Repo (`skills/`), injected by hook |

## Agents

| Agent | Purpose |
|-------|---------|
| `python-developer` | Full workflow: understand, explore, plan, implement, verify, summarize |
| `next-developer` | Same workflow for Next.js/TypeScript projects |

Agents receive their convention skills automatically via the `subagent_start` hook.

## Hooks

Hooks provide deterministic security enforcement and logging. They are registered globally in `~/.claude/settings.json` and run from `$AI_AGENT_ENV_PATH/hooks/`.

| Hook | Event | Purpose |
|------|-------|---------|
| `pre_tool_use.py` | `PreToolUse` | Security gate: blocks destructive commands, protects `.env` files, audits all tool calls |
| `permission_request.py` | `PermissionRequest` | Auto-allows read-only operations, reducing permission prompts |
| `post_tool_use_failure.py` | `PostToolUseFailure` | Logs tool failures for debugging |
| `subagent_stop.py` | `SubagentStop` | Captures subagent transcripts to per-agent log directories |
| `subagent_start.py` | `SubagentStart` | Injects skill files as context when mapped subagents spawn |
| `session_stop.py` | `Stop` | Parses session transcript into condensed chat log |
| `session_start.py` | `SessionStart` | Injects previous session context on startup |

### Security hook (`pre_tool_use`)

- **Tier 1 — Hard block**: Catastrophic commands always blocked (`rm -rf /`, `rm -rf ~`, `mkfs`, `dd if=`, `git push --force` to main/master)
- **Tier 2 — CWD enforcement**: Destructive commands targeting paths outside the project directory are blocked
- **`.env` protection**: Access to `.env` files is blocked across all tools

### Skill injection hook (`subagent_start`)

Two-tier skill lookup:
1. **Project override**: `{cwd}/.claude/skills/{filename}` (if it exists)
2. **Repo default**: `$AI_AGENT_ENV_PATH/skills/{filename}`

This lets projects override conventions when needed while defaulting to the repo.

### Log structure

```
.claude/logs/
├── last_session.md                  # Condensed chat from previous session
├── security/
│   └── blocked.jsonl               # Blocked tool calls
├── audit/
│   ├── pre_tool_use.jsonl           # Full tool call payloads
│   ├── permission_request.jsonl     # Permission decisions
│   ├── tool_failures.jsonl          # Tool failure details
│   ├── session_stop.jsonl           # Session stop events
│   ├── session_start.jsonl          # Session start events
│   └── subagent_start.jsonl         # Subagent skill injection events
└── agents/
    ├── .agent_map.json              # agent_id → directory mapping
    └── python-developer-1/
        ├── transcript.jsonl         # Continuous transcript log
        └── summary.jsonl            # Structured stop events
```

All log files are automatically trimmed to a maximum of **10 MB**.

## Project Overrides

To override a skill for a specific project, place the file in `.claude/skills/`:

```
your-project/.claude/skills/python-conventions.md
```

The `subagent_start` hook checks this location first before falling back to the repo default.

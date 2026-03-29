# AI Agent Environment

A centralized repository for Claude Code skills, agents, hooks, and prompts. Everything is installed globally — no per-project setup required.

## Contents

- [Architecture](#architecture)
- [Setup](#setup)
- [How It Works](#how-it-works)
- [Commands](#commands)
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
│   ├── next-developer.md
│   ├── plan-explorer.md
│   ├── plan-critic.md
│   └── plan-synthesizer.md
├── commands/
│   └── complex-plan.md
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
├── commands/              # Slash command prompts (copied to ~/.claude/commands/)
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
4. Copies commands to `~/.claude/commands/`
5. Merges hook definitions into `~/.claude/settings.json` (preserving existing keys)
6. Sets `AI_AGENT_ENV_PATH` environment variable

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

## Commands

Slash commands are installed to `~/.claude/commands/` and available globally as `/<command-name>`.

| Command | Purpose |
|---------|---------|
| `/complex-plan` | Multi-agent planning pipeline for features spanning multiple codebases |

### `/complex-plan`

Use this command when a feature spans multiple codebases (e.g., frontend + backend + database) and needs coordinated planning before implementation.

**Usage:**
```
/complex-plan Add user authentication with OAuth across the React frontend and Express API
```

You can also run `/complex-plan` with no arguments — it will ask you to describe the feature interactively.

**What happens:**

The command runs a 7-phase pipeline:

1. **Gather** — Asks you clarifying questions: which codebases are involved (with paths), constraints, and success criteria.
2. **Approve Scope** — Presents a Feature Summary for your approval before any planning begins.
3. **Plan** — Spawns parallel planner agents, one per codebase. Each reads `ARCHITECTURE.md`/`README.md` first, then explores and produces a feature spec (what to build, inputs/outputs, API contracts).
4. **Critic ↔ Planner Loop** — A critic reviews ALL plans for conflicts and gaps. If issues are found, flagged planners revise and the critic re-reviews. Loops until the critic approves all plans (max 3 rounds).
5. **Synthesize** — Combines the critic-approved plans into a unified spec with implementation order, dependency graph, and cross-codebase contracts. Only runs after all plans are approved.
6. **Approve Plan** — You review and approve the final spec (or request changes).
7. **Handoff** — The approved spec is ready to hand off to implementation agents (`python-developer`, `next-developer`, etc.).

**Planning boundary:** The plan defines *what* to build (features, behavior, inputs, outputs, API contracts) — never *how* (file structure, class names, implementation patterns). Developer agents own all implementation decisions.

**When to use it:**
- Features touching 2+ codebases that need to agree on APIs, events, or shared types
- Large features where you want architecture reviewed before writing code
- Cross-team work that needs a clear, shareable implementation spec

**When NOT to use it:**
- Single-codebase changes — just ask Claude directly or use `/complex-plan` isn't needed
- Small bug fixes or minor features — overhead isn't worth it

## Skills

| Skill | Purpose | Location |
|-------|---------|----------|
| `ai-interaction` | Communication standards, code review process | Global (`~/.claude/skills/`) |
| `python-conventions` | Code style, error handling, logging, testing, pipeline architecture, README & ARCHITECTURE.md maintenance | Repo (`skills/`), injected by hook |
| `next-conventions` | Next.js/TypeScript conventions | Repo (`skills/`), injected by hook |

## Agents

| Agent | Purpose |
|-------|---------|
| `python-developer` | Full workflow: understand, explore, plan, implement, verify, summarize |
| `next-developer` | Same workflow for Next.js/TypeScript projects |
| `plan-explorer` | Explores a single codebase and produces a planning spec (used by `/complex-plan`) |
| `plan-critic` | Reviews all plans together, finds cross-codebase conflicts (used by `/complex-plan`) |
| `plan-synthesizer` | Combines plans + critic feedback into a unified implementation spec (used by `/complex-plan`) |

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

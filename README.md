# AI Agent Environment

A centralized repository for reusable Claude Code skills, agents, and prompts. Projects are initialized with their own copies, making them self-contained and portable.

## Contents

- [What This Repo Contains](#what-this-repo-contains)
- [Architecture](#architecture)
- [Setup](#setup)
- [Usage](#usage)
- [Creating New Global Skills](#creating-new-global-skills)
- [Updating](#updating)
- [Skills](#skills)
- [Agents](#agents)
- [Hooks](#hooks)

## What This Repo Contains

- **skills/** — Coding conventions and best practices
- **agents/** — Custom subagents (e.g., `python-developer`) with workflows and skill references
- **commands/** — Global commands (e.g., `ai-initialize`) for project setup
- **prompts/** — Reusable prompt templates
- **hooks/** — Security, permissions, logging, and session hooks (`pre_tool_use`, `permission_request`, `post_tool_use_failure`, `subagent_stop`, `session_stop`, `session_start`, `subagent_start`)
- **install.sh** — One-time setup script for any machine

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Global (~/.claude/skills/)                                  │
├─────────────────────────────────────────────────────────────┤
│ ai-interaction/SKILL.md  — Basic communication guidelines   │
│ ai-initialize/SKILL.md   — /ai-initialize command           │
│ ai-sync/SKILL.md         — /ai-sync command                 │
└─────────────────────────────────────────────────────────────┘
                          │
                          │  /ai-initialize
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Project (.claude/)                                          │
├─────────────────────────────────────────────────────────────┤
│ CLAUDE.md  — Delegation rules                               │
│ settings.json — Hook registration                           │
│ skills/                                                     │
│   └── python-conventions.md                                 │
│ agents/                                                     │
│   └── python-developer.md                                   │
│ hooks/                                                      │
│   ├── pre_tool_use.py — Security gate                       │
│   ├── permission_request.py — Auto-allow read-only ops      │
│   ├── post_tool_use_failure.py — Tool failure logging        │
│   ├── subagent_stop.py — Agent transcript logging           │
│   ├── session_stop.py — Session chat log capture            │
│   ├── subagent_start.py — Skill injection for subagents     │
│   └── session_start.py — Previous session context injection │
│ logs/                                                       │
│   ├── last_session.md    — Condensed previous session chat  │
│   ├── security/          — Security decisions               │
│   ├── audit/             — Full tool call audit trail        │
│   └── agents/            — Per-agent transcripts & summaries│
└─────────────────────────────────────────────────────────────┘
```

## Setup

```bash
git clone <repo-url> && cd ai_agent_environment
./install.sh
source ~/.zshrc  # or ~/.bashrc
```

The install script:
1. Copies `ai-interaction`, `ai-initialize`, and `ai-sync` to `~/.claude/skills/`
2. Adds `export AI_AGENT_ENV_PATH="<repo-path>"` to your shell profile

## Usage

### Initialize a new project

In Claude Code, run:
```
/ai-initialize          # Python skills + agent (default)
/ai-initialize python   # Same as above
/ai-initialize all      # All skills, agents, and prompts
```

This copies skills and agents to `.claude/` in your project and generates a project-level `CLAUDE.md` with delegation rules.

### Sync updates to a project

After updating skills or agents in this repo, sync changes to an active project:
```
/ai-sync
```

This re-copies only the files that already exist in the project's `.claude/` directory from the repo. Project-specific files are left untouched.

### What gets copied

**Python (default):**
- `python-conventions.md` — All Python rules: code style, error handling, logging, testing, project structure, code review
- `python-developer.md` — Agent with full workflow

**All:**
- Everything above plus any additional skills, agents, and prompts

## Creating New Global Skills

To create a new invocable skill (slash command):

1. Create a folder in `skills/` named after your skill
2. Add a `SKILL.md` file inside it with frontmatter and prompt content
3. Run `./install.sh` to copy it to `~/.claude/skills/`

```
skills/
└── my-skill/
    └── SKILL.md
```

**SKILL.md format:**

```markdown
---
name: my-skill
description: Short description shown in skill list
user-invocable: true
disable-model-invocation: true
---

Your prompt instructions here. Use $ARGUMENTS for user input.
```

**Frontmatter options:**

| Field | Effect |
|-------|--------|
| `user-invocable: true` | Makes it a `/slash-command` the user can call |
| `disable-model-invocation: true` | Only runs when explicitly invoked, not auto-triggered |
| `globs: ["**/*"]` | Model auto-invokes it when matching files are relevant |

After running `install.sh`, restart Claude Code and the skill will be available as `/my-skill`.

## Updating

Re-run the install script to update global skills:
```bash
./install.sh
```

To update a project's skills/agents, run `/ai-sync` in that project.

## Skills

| Skill | Purpose | Scope |
|-------|---------|-------|
| `ai-interaction` | Communication standards, code review process | Global |
| `python-conventions` | Code style, error handling, logging, testing, project structure, code review | Per-project |

## Agents

| Agent | Purpose |
|-------|---------|
| `python-developer` | Full workflow: understand, explore, plan, implement, verify, summarize |

The `python-developer` agent uses the `skills:` field to load `python-conventions`, keeping the agent file lean while having full access to all conventions.

## Hooks

Hooks provide deterministic security enforcement and per-agent logging. They are copied to each project by `/ai-initialize` and registered in `.claude/settings.json`.

| Hook | Event | Purpose |
|------|-------|---------|
| `pre_tool_use.py` | `PreToolUse` | Security gate: blocks destructive commands, protects `.env` files, audits all tool calls |
| `permission_request.py` | `PermissionRequest` | Auto-allows read-only operations (`Read`, `Glob`, `Grep`, safe Bash), reducing permission prompts |
| `post_tool_use_failure.py` | `PostToolUseFailure` | Logs tool failures for pattern detection and debugging |
| `subagent_stop.py` | `SubagentStop` | Captures subagent transcripts into per-agent log directories |
| `session_stop.py` | `Stop` | Parses session transcript into condensed chat log for cross-session context |
| `subagent_start.py` | `SubagentStart` | Injects skill files as context when mapped subagents spawn |
| `session_start.py` | `SessionStart` | Injects previous session chat log as context on fresh startup |

### Security hook (`pre_tool_use`)

The security hook enforces three layers of protection:

- **Tier 1 — Hard block**: Catastrophic commands are always blocked regardless of CWD (`rm -rf /`, `rm -rf ~`, `mkfs`, `dd if=`, `git push --force` to main/master)
- **Tier 2 — CWD enforcement**: Destructive commands (`rm`, `mv`, `chmod`, `chown`) targeting paths outside the project directory are blocked. File-path tools (`Read`, `Write`, `Edit`, `MultiEdit`) are also checked.
- **`.env` protection**: Access to `.env` files is blocked across all tools (Bash, Read, Write, Edit, MultiEdit). Safe templates (`.env.sample`, `.env.example`, `.env.template`, `.env.test`) are allowed.

Security decisions are logged to `.claude/logs/security/blocked.jsonl`. Every tool call payload is captured in `.claude/logs/audit/pre_tool_use.jsonl` for full audit trail.

### Permission hook (`permission_request`)

The permission hook auto-allows read-only operations to reduce permission prompt fatigue:

- **Always allowed**: `Read`, `Glob`, `Grep` tools
- **Safe Bash commands**: `ls`, `pwd`, `cat` (no redirection), `head`, `tail`, `wc`, `which`, `file`, `stat`
- **Safe git**: `git status/log/diff/show/branch/tag`, `git remote -v`
- **Safe package managers**: `npm list/ls/outdated/view`, `pip list/show/freeze`
- **Version checks**: `python --version`, `node --version`

All other tools and commands pass through to the normal user permission prompt. Every request is logged to `.claude/logs/audit/permission_request.jsonl`.

### Failure tracking hook (`post_tool_use_failure`)

When any tool call fails, the error details are logged to `.claude/logs/audit/tool_failures.jsonl` — tool name, input, error, and session ID. Useful for spotting recurring failures (e.g., repeated bad Edit matches, failing Bash commands).

### Agent logging hook (`subagent_stop`)

When a subagent finishes, its transcript is appended to `.claude/logs/agents/{agent_type}-{N}/transcript.jsonl` as a continuous log. Directories are numbered sequentially per agent type (e.g., `python-developer-1`, `python-developer-2`). A structured summary entry is appended to `summary.jsonl` in the same directory. The `subagent_start` hook registers the agent_id → directory mapping when the agent spawns, ensuring consistent naming between start and stop.

### Session chat log hook (`session_stop`)

When a session ends, the stop hook reads the full session transcript and extracts only the user messages and assistant text responses (skipping tool calls, thinking, progress events). The result is written to `.claude/logs/last_session.md` as a condensed markdown chat log, capped at 4000 characters (trimmed from the top to keep recent messages). Stop events are logged to `.claude/logs/audit/session_stop.jsonl`.

### Skill injection hook (`subagent_start`)

When a mapped subagent spawns, the start hook reads the corresponding skill files from `.claude/skills/` and injects their contents as `additionalContext`. This guarantees skills are loaded regardless of whether the model honors the `skills:` field in agent frontmatter. The mapping is defined in the hook:

- `python-developer` → `python-conventions.md`
- `next-developer` → `next-conventions.md`

Unmapped agents (Bash, Explore, Plan, etc.) pass through silently. If a skill file is missing, the hook logs and continues without breaking the agent spawn. Events are logged to `.claude/logs/audit/subagent_start.jsonl`.

### Session context hook (`session_start`)

On fresh startup (`source: "startup"`), the start hook reads `.claude/logs/last_session.md` and injects it as `additionalContext` so Claude has awareness of the previous session's conversation. This is skipped on resume, clear, and compact events (which already have context). Start events are logged to `.claude/logs/audit/session_start.jsonl`.

### Log structure

```
.claude/logs/
├── last_session.md                  # Condensed chat from previous session
├── security/
│   └── blocked.jsonl               # Blocked tool calls with full detail
├── audit/
│   ├── pre_tool_use.jsonl           # Full tool call payloads (one JSON per line)
│   ├── permission_request.jsonl     # Permission decisions (allow/pass_through)
│   ├── tool_failures.jsonl          # Tool failure details (error, input, tool name)
│   ├── session_stop.jsonl           # Session stop events
│   ├── session_start.jsonl          # Session start events
│   └── subagent_start.jsonl         # Subagent skill injection events
├── agents/
│   ├── .agent_map.json              # agent_id → directory name mapping
│   ├── python-developer-1/
│   │   ├── transcript.jsonl         # Continuous transcript log
│   │   └── summary.jsonl            # Structured stop events
│   └── python-developer-2/
│       ├── transcript.jsonl
│       └── summary.jsonl
```

All log files are automatically trimmed to a maximum of **10 MB** by removing the oldest entries.

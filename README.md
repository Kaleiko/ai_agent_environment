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
- **hooks/** — Security and logging hooks (`pre_tool_use`, `subagent_stop`)
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
│   └── subagent_stop.py — Agent transcript logging           │
│ logs/                                                       │
│   ├── security/          — Security decisions               │
│   ├── audit/             — Full tool call audit trail        │
│   └── agent-{id}/        — Per-agent transcripts            │
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
| `subagent_stop.py` | `SubagentStop` | Captures subagent transcripts into per-agent log directories |

### Security hook (`pre_tool_use`)

The security hook enforces three layers of protection:

- **Tier 1 — Hard block**: Catastrophic commands are always blocked regardless of CWD (`rm -rf /`, `rm -rf ~`, `mkfs`, `dd if=`, `git push --force` to main/master)
- **Tier 2 — CWD enforcement**: Destructive commands (`rm`, `mv`, `chmod`, `chown`) targeting paths outside the project directory are blocked. File-path tools (`Read`, `Write`, `Edit`, `MultiEdit`) are also checked.
- **`.env` protection**: Access to `.env` files is blocked across all tools (Bash, Read, Write, Edit, MultiEdit). Safe templates (`.env.sample`, `.env.example`, `.env.template`, `.env.test`) are allowed.

Security decisions are logged to `.claude/logs/security/pre_tool_use.log`. Every tool call payload is captured in `.claude/logs/audit/pre_tool_use.json` for full audit trail.

### Agent logging hook (`subagent_stop`)

When a subagent finishes, its transcript is copied to `.claude/logs/agent-{id}/` with a timestamped filename. A summary entry is appended to `summary.log` in the same directory.

### Log structure

```
.claude/logs/
├── security/
│   └── blocked.jsonl               # Blocked tool calls with full detail
├── audit/
│   └── pre_tool_use.jsonl           # Full tool call payloads (one JSON per line)
├── agent-abc123/
│   ├── 2026-02-09_14-30-25.jsonl   # Transcript copy
│   └── summary.log                 # Session summaries
└── agent-def456/
    ├── 2026-02-09_14-35-10.jsonl
    └── summary.log
```

All log files are automatically trimmed to a maximum of **10 MB** by removing the oldest entries.

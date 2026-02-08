# AI Agent Environment

A centralized repository for reusable Claude Code skills, agents, and prompts. Projects are initialized with their own copies, making them self-contained and portable.

## What This Repo Contains

- **skills/** — Coding conventions and best practices
- **agents/** — Custom subagents (e.g., `python-developer`) with workflows and skill references
- **commands/** — Global commands (e.g., `ai-initialize`) for project setup
- **prompts/** — Reusable prompt templates
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
│ skills/                                                     │
│   └── python-conventions.md                                 │
│ agents/                                                     │
│   └── python-developer.md                                   │
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

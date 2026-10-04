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
│   ├── e2e-developer.md
│   ├── plan-explorer.md
│   ├── plan-critic.md
│   └── plan-synthesizer.md
├── commands/
│   └── complex-plan.md
└── skills/                # Only skills marked `scope: global`
    └── ai-interaction/
        └── SKILL.md

$AI_AGENT_ENV_PATH/ (Repo — source of truth)
├── install.sh             # Global installer
├── scripts/
│   └── merge_global_settings.py  # Safely merges hooks into settings.json
├── hooks/                 # Run directly from repo via $AI_AGENT_ENV_PATH
│   ├── hook_paths.py       # Shared helper: resolves the stable project root for logs
│   ├── pre_tool_use.py
│   ├── permission_request.py
│   ├── post_tool_use_failure.py
│   ├── subagent_stop.py
│   ├── subagent_start.py
│   ├── session_stop.py
│   └── session_start.py
├── skills/                # All skills; `scope:` frontmatter decides global vs injected
├── agents/                # Agent definitions (source of truth)
├── commands/              # Slash command prompts (copied to ~/.claude/commands/)
└── prompts/
    └── delegation.md      # Source of truth (copied to ~/.claude/rules/)

Project .claude/ (Per-project — auto-created by hooks)
├── logs/                  # Created automatically by hooks
│   ├── last_session.md
│   ├── full_log.md        # Append-only full conversation log (FULL_LOG=1)
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
1. Copies skills marked `scope: global` to `~/.claude/skills/`
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

| Skill | Purpose | `scope:` |
|-------|---------|----------|
| `ai-interaction` | Communication standards, code review process | `global` — installed to `~/.claude/skills/`, in every session's registry |
| `self-improvement` | Diagnose and durably fix the cause when the user corrects you | `global` |
| `python-conventions` | Code style, error handling, logging, testing, pipeline architecture, README & ARCHITECTURE.md maintenance | `injected` — stays in repo, injected into matching agents |
| `next-conventions` | Next.js/TypeScript conventions | `injected` |
| `playwright-conventions` | Mandatory conventions for Playwright E2E tests in Python | `injected` |

### Adding a new skill

A skill's own frontmatter decides how it loads. There is no list to keep in sync.

```yaml
---
name: my-skill
scope: global      # or: injected  (omit entirely and it defaults to injected)
description: "..."
---
```

- **`scope: global`** — `install.sh` copies it to `~/.claude/skills/<name>/SKILL.md`. Its name and
  description then sit in **every** session's registry, and the model may invoke it anywhere.
  Use for discretionary capabilities you want available across all projects.
- **`scope: injected`** (the default) — the file stays in `skills/`. It reaches an agent only when
  that agent's definition names it under `skills:`, and the `subagent_start` hook injects the full
  body at spawn. Costs nothing in sessions that never spawn the agent. Use for conventions that are
  **mandatory** for a specific agent — injection is unconditional, whereas registration only makes a
  skill available for the model to choose.

Omitting `scope:` is deliberately the safe default: a new skill can never become globally registered
by accident.

## Agents

| Agent | Routed to when | Purpose |
|-------|----------------|---------|
| `python-developer` | `.py` edits, non-Playwright project | Full workflow: understand, explore, plan, implement, verify, document, summarize |
| `e2e-developer` | `.py` edits, Playwright E2E repo (takes priority) | Same workflow for Playwright tests |
| `next-developer` | `.ts`/`.tsx`/`.jsx` edits, Next.js project only | Same workflow for Next.js/TypeScript |
| `plan-explorer` | Spawned by `/complex-plan`, one per codebase, in parallel | Explores a codebase, produces a planning spec (read-only) |
| `plan-critic` | Spawned by `/complex-plan` after the explorers | Reviews all plans together, finds cross-codebase conflicts (read-only) |
| `plan-synthesizer` | Spawned by `/complex-plan` once the critic approves | Combines plans + feedback into a unified spec (read-only) |

Agents receive their convention skills automatically via the `subagent_start` hook, based on the
`skills:` list in each agent's frontmatter.

Each agent's `description` field carries its full routing trigger — the Agent tool surfaces those
descriptions to the model, so routing holds even independently of `delegation.md`.

## Hooks

Hooks provide deterministic security enforcement and logging. They are registered globally in `~/.claude/settings.json` and run from `$AI_AGENT_ENV_PATH/hooks/`.

| Hook | Event | Purpose |
|------|-------|---------|
| `pre_tool_use.py` | `PreToolUse` | Security gate: blocks destructive commands, protects `.env` files, audits all tool calls |
| `permission_request.py` | `PermissionRequest` | Auto-allows read-only operations, reducing permission prompts |
| `post_tool_use_failure.py` | `PostToolUseFailure` | Logs tool failures for debugging |
| `subagent_stop.py` | `SubagentStop` | Captures subagent transcripts to per-agent log directories |
| `hook_paths.py` | *(shared module)* | Project-root resolution and per-agent log directory naming |
| `subagent_start.py` | `SubagentStart` | Injects skill files as context when mapped subagents spawn |
| `session_stop.py` | `Stop` | Parses session transcript into condensed chat log (20K char limit); optionally appends full log |
| `session_start.py` | `SessionStart` | Archives previous session, injects up to 2 sessions of context + active plans |

### Security hook (`pre_tool_use`)

- **Tier 1 — Hard block**: Catastrophic commands always blocked (`rm -rf /`, `rm -rf ~`, `mkfs`, `dd if=`, `git push --force` to main/master)
- **Tier 2 — CWD enforcement**: Destructive commands targeting paths outside the project directory are blocked
- **`.env` protection**: Access to `.env` files is blocked across all tools
- **`full_log.md` protection**: Claude is blocked from reading `.claude/logs/full_log.md` to prevent self-referential loops
- **Fail closed**: Security checks run before any logging, and a crash in the check logic (or an unwritable log directory) blocks the call rather than silently allowing it

### Agent log directory naming

`subagent_start` records an agent's log directory name in `.agent_map.json` and
`subagent_stop` creates the directory, so both derive the name from one implementation
in `hook_paths.derive_agent_dir_name()` — if they disagreed, the mapping would silently
break. The name is `{agent_type}-{N}`, where `N` continues from the highest number
already present in the map or on disk.

The agent type comes from the hook payload, so it is checked against a safe-name pattern
before becoming a path component. An empty or unsafe type (`""`, `../../etc/passwd`)
becomes `unknown-{N}` rather than steering directory creation; an empty type previously
produced directories literally named `-18`, `-19`, and so on. Existing directories and
map entries are untouched — an agent already in the map keeps the directory it has,
legacy `-NN` names included — and safe types are passed through unchanged, so normal
names and numbering are exactly as before.

Sanitising only affects the path. The raw payload value is still recorded as `agent_type`
in both `subagent_start.jsonl` and `summary.jsonl`; when substitution changed the name,
the record also carries `agent_dir_name` (start) or `agent_dir` (stop) so the two can be
matched up.

All hooks anchor their log directories to a stable project root resolved by `hook_paths.get_project_root()` — `CLAUDE_PROJECT_DIR` if set, else the payload `cwd`, else the process cwd. This keeps logs under `<project>/.claude/logs/` even when a tool changes the working directory mid-session (e.g. a `cd` inside a Bash command). The security checks themselves still use the tool's live working directory.

### Skill injection hook (`subagent_start`)

Two-tier lookup, used for both skill files and agent definitions:
1. **Project override**: `{cwd}/.claude/skills/{filename}` — or `{cwd}/.claude/agents/{type}.md`
2. **Repo default**: `$AI_AGENT_ENV_PATH/skills/{filename}` — or `$AI_AGENT_ENV_PATH/agents/{type}.md`

This lets projects override conventions, and the agent definitions that select them,
while defaulting to the repo.

**The `skills:` frontmatter in `agents/<type>.md` is the source of truth** for which
skills an agent gets. Adding a skill there takes effect with no change to the hook.
Names may be written with or without the `.md` suffix, as a block sequence or as a
one-line `skills: [a, b]`. Resolution order:

1. Agent definition found with a `skills:` key → inject exactly those skills
2. Agent definition found with **no** `skills:` key → inject nothing (this is what
   `plan-critic`, `plan-explorer`, and `plan-synthesizer` rely on)
3. Agent definition missing, unreadable, or without a frontmatter block → fall back to
   the `AGENT_SKILLS` dict in the hook, so a broken file degrades to the old behaviour
   rather than silently injecting nothing

The audit record names the source in `skills_source` (`agent_frontmatter`,
`agent_frontmatter_no_skills`, or `agent_skills_fallback`) together with the
`agent_definition` path used. These fields are omitted in exactly one case — the
frontmatter was authoritative **and** it agrees with `AGENT_SKILLS` — so any
disagreement between the two is always visible. A divergence also logs
`skills_divergence` with both lists.

The agent type comes from the payload and skill names come from a file a project can
override, so both are checked against a safe-name pattern before being joined onto a
lookup directory.

**Agent type resolution** — the spawning agent's type is read from `agent_type`, falling
back through `subagent_type`, `agentType`, `subagentType`, `agent_name`, `agentName`,
`name`, and `type`, then the same keys nested inside `agent`, `subagent`, `tool_input`,
`toolInput`, `params`, or `input`. An empty string counts as absent. When the type comes
from anything other than `agent_type`, the audit record names the key in `resolved_from`.

**Never fails silently** — every invocation writes a line to `subagent_start.jsonl`,
including the ones that inject nothing. Non-injecting outcomes carry a `note`:

| `note` | Meaning |
|--------|---------|
| *(absent)* | Normal injection, or a mapped type whose skill files were missing |
| `unmapped_agent_type` | Type resolved but has no entry in `AGENT_SKILLS` |
| `no_skills_declared` | Agent definition found, but it declares no `skills:` |
| `agent_type_unresolved` | No key carried a type — see `unresolved_payload_keys` |
| `payload_not_decodable` | stdin was not a JSON object |

**Unresolved fallback** — when no agent type can be resolved the hook does not guess a
skill (`python-conventions` and `playwright-conventions` both claim `**/*.py`). It emits
`additionalContext` instructing the agent to read the right conventions file itself,
listing each one's absolute path, `globs`, and `description`. That listing enumerates
the skills directories themselves, so a skill no agent maps to is still offered. The audit record captures
`unresolved_payload_keys` and a size-capped `unresolved_payload` with transcript-, prompt-,
and content-like values redacted, so the next spawn reveals what the field is now called.

### Session continuity

On session stop, the current conversation is saved to `last_session.md` (up to 20K chars). On next startup:

1. `last_session.md` is archived to `.claude/logs/sessions/{timestamp}_session.md`
2. The 2 most recent session files are injected as context (15K for recent, 5K for older)
3. Any plan files in `.claude/plans/` are listed
4. Sessions older than the 2 most recent are deleted

This gives the agent 2 sessions of context to recover from, even if a session was closed early.

### Full log mode

When the `FULL_LOG` environment variable is set, the `session_stop` hook appends all conversation messages to `.claude/logs/full_log.md` in addition to the normal `last_session.md` behavior.

```bash
FULL_LOG=1 claude --dangerously-skip-permissions
```

Key differences from `last_session.md`:

- **Append-only** — content accumulates across sessions, separated by session headers
- **No size cap** — unlike `last_session.md` (20K char limit), `full_log.md` grows without truncation
- **Deduplicated** — a state file (`.claude/logs/.full_log_state.json`) tracks the line offset so reprocessing the same session does not duplicate content
- **Protected** — Claude is blocked from reading `full_log.md` (enforced by `pre_tool_use.py`) to prevent self-referential behavior

This is useful for maintaining a complete audit trail of all conversations within a project.

### Log structure

```
.claude/
├── logs/
│   ├── last_session.md                  # Current/most recent session chat log
│   ├── full_log.md                      # Append-only full log (when FULL_LOG is set)
│   ├── .full_log_state.json             # Line offset tracker for full_log dedup
│   ├── sessions/                        # Archived previous sessions (max 2 kept)
│   │   ├── 2026-03-29T14-30-00_session.md
│   │   └── 2026-03-30T10-15-00_session.md
│   ├── security/
│   │   └── blocked.jsonl               # Blocked tool calls
│   ├── audit/
│   │   ├── pre_tool_use.jsonl           # Full tool call payloads
│   │   ├── permission_request.jsonl     # Permission decisions
│   │   ├── tool_failures.jsonl          # Tool failure details
│   │   ├── session_stop.jsonl           # Session stop events
│   │   ├── session_start.jsonl          # Session start events
│   │   └── subagent_start.jsonl         # Subagent skill injection events
│   └── agents/
│       ├── .agent_map.json              # agent_id → directory mapping (shared by both subagent hooks)
│       └── python-developer-1/
│           ├── transcript.jsonl         # Continuous transcript log
│           └── summary.jsonl            # Structured stop events
├── plans/                               # Implementation & architecture plans
│   ├── ARCHITECTURE_PLAN.md
│   └── PHASE1_IMPLEMENTATION_PLAN.md
```

All log files are automatically trimmed to a maximum of **10 MB**.

## Project Overrides

To override a skill for a specific project, place the file in `.claude/skills/`:

```
your-project/.claude/skills/python-conventions.md
```

The `subagent_start` hook checks this location first before falling back to the repo default.

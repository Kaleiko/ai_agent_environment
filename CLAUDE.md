# AI Agent Environment

This repository contains reusable skills, agents, hooks, and prompts for Claude Code — all installed globally via `install.sh`.

## Architecture

- **Global** (`~/.claude/`) — Hooks (in settings.json), delegation rules (in rules/), agents (in agents/), ai-interaction skill (in skills/)
- **Repo** (`$AI_AGENT_ENV_PATH/`) — Source of truth for all hooks, skills, agents, and prompts
- **Per-project** (`.claude/`) — Only logs (auto-created by hooks) and optional skill overrides

## MANDATORY: Agent Delegation

Delegation rules are loaded globally from `~/.claude/rules/delegation.md`. They define when and how to delegate tasks to subagents. You MUST follow them.

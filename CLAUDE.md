# AI Agent Environment

This repository contains reusable skills, commands, prompts, and agent configurations.

## Architecture

- **Global** (`~/.claude/skills/`) — `ai-interaction` (communication guidelines), `ai-initialize` (project setup), `ai-sync` (update project from repo)
- **Per-project** (`.claude/`) — Skills, agents, and prompts are copied to each project via `/ai-initialize`, updated via `/ai-sync`

## MANDATORY: Agent Delegation

If this project has a `.claude/prompts/delegation.md` file, you MUST read it and follow ALL rules within it. It defines when and how to delegate tasks to subagents.

If no `.claude/prompts/delegation.md` exists and the user asks for Python work, suggest running `/ai-initialize` to set up the project.

---
name: ai-sync
description: Sync project skills and agents with latest from ai_agent_environment repo
user-invocable: true
disable-model-invocation: true
---

# AI Sync

Re-copy the latest skills and agents from the ai_agent_environment repository into the current project's `.claude/` directory.

## CRITICAL RULES

- MUST ONLY update files that exist in BOTH the project AND the repo
- MUST NEVER delete any file from the project's `.claude/` directory
- MUST NEVER overwrite or modify project-specific files that do not exist in the repo
- MUST NEVER remove directories or restructure the project's `.claude/` layout
- If a file exists in the project but NOT in the repo, it is project-specific — leave it completely untouched

## Prerequisites

The environment variable `$AI_AGENT_ENV_PATH` must be set.

**First, verify it is set:**

```bash
echo "$AI_AGENT_ENV_PATH"
```

If empty, stop and tell the user to add this to their shell profile (`~/.zshrc` or `~/.bashrc`):
```bash
export AI_AGENT_ENV_PATH="/path/to/ai_agent_environment"
```

## Steps

### 1. Verify project is initialized

Check that `.claude/skills/` and `.claude/agents/` exist. If they do NOT exist, stop and tell the user to run `/ai-initialize` first.

### 2. Sync skills

For each `.md` file in `.claude/skills/`, check if a matching file exists in the repo. ONLY copy if it exists in the repo. NEVER touch files that are project-specific:

```bash
for f in .claude/skills/*.md; do
  name=$(basename "$f")
  if [ -f "$AI_AGENT_ENV_PATH/skills/$name" ]; then
    cp "$AI_AGENT_ENV_PATH/skills/$name" ".claude/skills/$name"
  fi
done
```

### 3. Sync agents

For each `.md` file in `.claude/agents/`, check if a matching file exists in the repo. ONLY copy if it exists in the repo. NEVER touch files that are project-specific:

```bash
for f in .claude/agents/*.md; do
  name=$(basename "$f")
  if [ -f "$AI_AGENT_ENV_PATH/agents/$name" ]; then
    cp "$AI_AGENT_ENV_PATH/agents/$name" ".claude/agents/$name"
  fi
done
```

### 4. Confirm

Report in three categories:
- **Updated from repo**: Files that were re-copied with latest versions
- **Project-specific (untouched)**: Files that exist in the project but NOT in the repo — confirm these were left alone
- **Not synced**: Any files in the repo that are NOT in the project (inform user they can run `/ai-initialize` to add new files)

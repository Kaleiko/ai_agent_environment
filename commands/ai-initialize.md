---
name: ai-initialize
description: Initialize a project with AI skills, agents, and prompts
user-invocable: true
disable-model-invocation: true
---

# AI Project Initialization

Initialize the current project with AI configuration from the ai_agent_environment repository.

## Prerequisites

The environment variable `$AI_AGENT_ENV_PATH` must be set to the path of the ai_agent_environment repository.

**First, verify it is set:**

```bash
echo "$AI_AGENT_ENV_PATH"
```

If empty, stop and tell the user to add this to their shell profile (`~/.zshrc` or `~/.bashrc`):
```bash
export AI_AGENT_ENV_PATH="/path/to/ai_agent_environment"
```

## Steps

### 1. Create project structure

```bash
mkdir -p .claude/skills .claude/agents .claude/prompts .claude/ai_docs .claude/specs .claude/hooks .claude/logs/security
```

### 2. Copy all files

```bash
# Copy all skills EXCEPT ai-interaction (already global)
for f in "$AI_AGENT_ENV_PATH/skills/"*.md; do
  name=$(basename "$f")
  if [ "$name" != "ai-interaction.md" ]; then
    cp "$f" .claude/skills/
  fi
done

# Copy all agents
cp "$AI_AGENT_ENV_PATH/agents/"*.md .claude/agents/ 2>/dev/null

# Copy all prompts
cp "$AI_AGENT_ENV_PATH/prompts/"*.md .claude/prompts/ 2>/dev/null

# Copy hooks
cp "$AI_AGENT_ENV_PATH/hooks/"*.py .claude/hooks/ 2>/dev/null
```

### 3. Generate settings.json with hook registration

Create `.claude/settings.json` in the project. If it already exists, merge the `hooks` key into it (preserve any existing settings).

If `.claude/settings.json` does not exist, create it with this content:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Read|Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/pre_tool_use.py\""
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/subagent_stop.py\""
          }
        ]
      }
    ]
  }
}
```

If `.claude/settings.json` already exists, read it and add the `hooks` key if not already present. If `hooks` already exists, ensure both `PreToolUse` and `SubagentStop` entries are present.

### 4. Generate project CLAUDE.md

Create `.claude/CLAUDE.md` with delegation rules. Do NOT overwrite if it already exists — instead append a section.

If `.claude/CLAUDE.md` does not exist, create it with this content:

```markdown
# Project AI Configuration

Initialized with `/ai-initialize`.

@.claude/prompts/delegation.md
```

If `.claude/CLAUDE.md` already exists, check if it already contains the `@.claude/prompts/delegation.md` import. If not, append it.

### 5. Confirm

Report:
- Which skills were copied
- Which agents were copied
- Which prompts were copied
- Which hooks were copied
- Whether settings.json was created or updated
- Whether CLAUDE.md was created or updated
- The project is ready to use

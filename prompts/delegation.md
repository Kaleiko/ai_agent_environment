# Agent Delegation Rules

**These rules are MANDATORY. You MUST follow them for EVERY task without exception.**

## Python Code Delegation

When reading, writing, or editing Python code (any `.py` file), you MUST delegate to a subagent. This applies to ALL Python operations regardless of size — even single-line edits, quick reads, or minor fixes. You MUST NEVER handle Python code directly.

### How to delegate:

1. Read `.claude/agents/python-developer.md` to get the full agent definition and workflow
2. Use the Task tool to spawn a subagent using the agent definition as the system prompt
3. Pass the user's request as the task argument
4. Return the subagent's summary to the user

### Example:

```
User: "Fix the bug in src/auth/token.py"

You MUST:
1. Read .claude/agents/python-developer.md
2. Call Task tool with:
   - prompt: The agent definition + "Fix the bug in src/auth/token.py"
   - subagent_type: general-purpose
3. Return the summary
```

### Rules:

- MUST ALWAYS read the agent definition before spawning the subagent
- MUST NEVER modify, read, or analyze Python files yourself
- MUST NEVER skip delegation for "simple" Python tasks — ALL Python work goes through the agent
- MUST NEVER paraphrase or shorten the agent definition — pass it in full as the prompt

## Non-Python Tasks

For tasks that do NOT involve Python code (documentation, configuration, shell scripts, etc.), handle them directly. Delegation is ONLY required for Python work.

## No Agents Available

If `.claude/agents/` does not exist or is empty, inform the user and suggest running `/ai-initialize` to set up the project.

# Agent Delegation Rules

**The routing rules below are MANDATORY — they decide WHICH agent owns a file, and they exist because nothing else in the environment tells you that.**

The *mechanics* of spawning are not mandatory. They are a convenience snapshot, and they drift as Claude Code updates.

> **Precedence:** if anything in the "Subagent Mechanics" section disagrees with the `Agent` tool's own description or with an error the tool returns, **the tool wins.** Follow it and treat this file as out of date. Do not force a documented-here call shape that the tool rejects.

## Subagent Mechanics

Reference only — current as of Claude Code 2.1.250.

### Spawning

Use the **`Agent`** tool with `subagent_type` set to the agent name. Save the returned **agent ID** if you expect follow-up work.

The tool is named `Agent`. It was formerly called `Task`; that name is stale.

### Subagents run in the background

The `Agent` tool returns immediately with an agent ID. The subagent's actual result arrives later as a completion notification.

- You MUST NOT report, assume, or predict a subagent's results before its completion notification arrives — this one IS mandatory, because reporting invented results is a correctness failure, not a mechanics detail
- If the user asks about progress in the meantime, say the agent is still running
- You MAY continue with unrelated work while it runs

### Parallel work is allowed and encouraged

Independent tasks SHOULD be dispatched concurrently — send multiple `Agent` calls in a single message so they run at the same time. Do not serialize work that has no dependency between its parts.

Reserve sequential, one-at-a-time delegation for work that genuinely depends on a previous result.

### Resuming vs. spawning fresh

`SendMessage` (with `to:` set to the saved agent ID) continues an existing subagent, which keeps its full prior context. Calling `Agent` again always starts a *fresh* agent with no memory of the earlier work.

- **Prefer resuming** for follow-up questions, iterations, and related changes on the same files — it avoids re-explaining context and re-reading the same code
- **Spawn fresh** for independent work, including work that can run in parallel with an agent already in flight

If you no longer have the agent ID, use `ListAgents` to find the running agent by name.

### Fallback if an agent type is unrecognized

1. Read the agent definition from `{{AI_AGENT_ENV_PATH}}/agents/<agent-name>.md`
2. Spawn with `subagent_type: "general-purpose"`, passing the agent definition as the prompt

## Reading vs. Editing

This distinction applies to EVERY delegation rule below.

**Editing is delegated. Reading is not.**

- You MUST NOT create, modify, or delete a delegated-language file yourself — no edits, no matter how small
- You MAY read delegated-language files to diagnose, review, answer questions, or verify a subagent's work

Delegation exists to keep written code on-convention. Reading breaks no conventions. Diagnosing a file you are forbidden to open produces confident, wrong conclusions — so when you need to understand code, read it, and delegate the change that follows.

## E2E Test Delegation (Playwright)

When working in a Playwright E2E test repository, ALL Python **edits** MUST be delegated to the `e2e-developer` agent instead of `python-developer`. This takes PRIORITY over the general Python delegation rule below.

### Detection:

A project is a Playwright E2E test repository if ANY of these are true:
- `pyproject.toml` contains `pytest-playwright` or `playwright` as a dependency
- `requirements.txt` contains `playwright`
- A `pages/` directory exists at the project root containing page object files

If the project is NOT a Playwright E2E repo, fall through to the standard Python delegation below.

### How to delegate:

Spawn `e2e-developer` per **Subagent Mechanics** above, passing the user's request as the task prompt.

### Rules:

- MUST delegate ALL Python edits in E2E repos to `e2e-developer`, NOT `python-developer`
- MUST NEVER create, modify, or delete Python files yourself
- MUST NEVER skip delegation for "simple" E2E edits — ALL E2E code changes go through the agent
- MUST pass the subagent's formatted response to the user exactly as returned — do NOT reformat or summarize it

## Python Code Delegation

When creating, modifying, or deleting Python code (any `.py` file), you MUST delegate to a subagent. This applies to ALL Python edits regardless of size — even single-line changes. You MAY read Python directly.

### How to delegate:

Spawn `python-developer` per **Subagent Mechanics** above, passing the user's request as the task prompt.

### Rules:

- MUST NEVER create, modify, or delete Python files yourself
- MUST NEVER skip delegation for "simple" Python edits — ALL Python code changes go through the agent
- MUST pass the subagent's formatted response to the user exactly as returned — do NOT reformat or summarize it

## Next.js / TypeScript Code Delegation

When creating, modifying, or deleting Next.js / TypeScript code (any `.ts`, `.tsx`, or `.jsx` file), you MUST delegate to a subagent — but ONLY when the project is a Next.js project.

### Detection:

A project is a Next.js project if ANY of these are true:
- `next.config.ts` or `next.config.mjs` exists in the project root
- `package.json` contains `"next"` as a dependency or devDependency

If the project is NOT a Next.js project, handle `.ts`/`.tsx`/`.jsx` files directly — do NOT delegate.

### How to delegate:

Spawn `next-developer` per **Subagent Mechanics** above, passing the user's request as the task prompt.

### Rules:

- MUST ALWAYS verify the project is a Next.js project before delegating `.ts`/`.tsx`/`.jsx` edits
- MUST NEVER create, modify, or delete Next.js/TypeScript files yourself (in Next.js projects)
- MUST NEVER skip delegation for "simple" Next.js edits — ALL Next.js code changes go through the agent
- MUST pass the subagent's formatted response to the user exactly as returned — do NOT reformat or summarize it

## Post-Subagent Verification

After EVERY subagent run, you MUST verify the result before returning it to the user:

1. **Check the subagent's response** — Did it complete the full task, or did it stop partway? Look for phrases like "I couldn't", "I was unable", partial implementations, or TODO placeholders.
2. **Check for failures** — Read the last 5 lines of `.claude/logs/audit/tool_failures.jsonl` to see if the subagent hit errors during its run.
3. **Check that conventions were injected** — Read the last line of `.claude/logs/audit/subagent_start.jsonl`. If it shows `"note": "agent_type_unresolved"` or an empty `skills_injected`, the subagent may have written code without its conventions; confirm it read them before accepting the work.
4. **Read the changed code** — You are permitted to read the files the subagent touched. Do it. A subagent's own summary is not verification of itself.
5. **If issues are found** — Resume the subagent (via `SendMessage`) to address them before reporting back. Do NOT pass incomplete or failed results to the user without first attempting a fix.

This applies to ALL subagent types.

## Non-Delegated Tasks

For tasks that do NOT involve Python or Next.js/TypeScript **edits** (documentation, configuration, shell scripts, analysis, code review), handle them directly. Delegation is ONLY required for the code changes described above.

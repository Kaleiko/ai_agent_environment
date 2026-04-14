# Agent Delegation Rules

**These rules are MANDATORY. You MUST follow them for EVERY task without exception.**

## E2E Test Delegation (Playwright)

When working in a Playwright E2E test repository, ALL Python code MUST be delegated to the `e2e-developer` agent instead of `python-developer`. This takes PRIORITY over the general Python delegation rule below.

### Detection:

A project is a Playwright E2E test repository if ANY of these are true:
- `pyproject.toml` contains `pytest-playwright` or `playwright` as a dependency
- `requirements.txt` contains `playwright`
- A `pages/` directory exists at the project root containing page object files

If the project is NOT a Playwright E2E repo, fall through to the standard Python delegation below.

### How to delegate (first task):

1. Use the Task tool with `subagent_type: "e2e-developer"` to spawn the agent
2. Pass the user's request as the task prompt
3. Save the returned **agent ID** for follow-up tasks
4. Return the subagent's summary to the user

**Fallback** — if `e2e-developer` is not recognized as a subagent type:
1. Run `echo $AI_AGENT_ENV_PATH` via Bash to get the repo path
2. Read `{AI_AGENT_ENV_PATH}/agents/e2e-developer.md` to get the full agent definition
3. Use the Task tool with `subagent_type: "general-purpose"`, passing the agent definition as the prompt
4. Save the returned agent ID and return the summary

### How to resume (follow-up tasks):

Same as Python delegation — resume the existing subagent for related follow-ups.

### Rules:

- MUST delegate ALL Python files in E2E repos to `e2e-developer`, NOT `python-developer`
- MUST ALWAYS resume the existing subagent for follow-up tasks on the same work
- MUST NEVER modify, read, or analyze Python files yourself
- MUST NEVER skip delegation for "simple" E2E tasks — ALL E2E work goes through the agent
- MUST NEVER spawn a new subagent when an active one can be resumed
- MUST pass the subagent's formatted response to the user exactly as returned — do NOT reformat or summarize it

## Python Code Delegation

When reading, writing, or editing Python code (any `.py` file), you MUST delegate to a subagent. This applies to ALL Python operations regardless of size — even single-line edits, quick reads, or minor fixes. You MUST NEVER handle Python code directly.

### How to delegate (first task):

1. Use the Task tool with `subagent_type: "python-developer"` to spawn the agent
2. Pass the user's request as the task prompt
3. Save the returned **agent ID** for follow-up tasks
4. Return the subagent's summary to the user

**Fallback** — if `python-developer` is not recognized as a subagent type:
1. Run `echo $AI_AGENT_ENV_PATH` via Bash to get the repo path
2. Read `{AI_AGENT_ENV_PATH}/agents/python-developer.md` to get the full agent definition
3. Use the Task tool with `subagent_type: "general-purpose"`, passing the agent definition as the prompt
4. Save the returned agent ID and return the summary

### How to resume (follow-up tasks):

If the user's follow-up request relates to the same topic or codebase area as an active subagent, you MUST resume that subagent instead of spawning a new one.

1. Use the Task tool with the `resume` parameter, passing the saved agent ID
2. Pass the user's follow-up request as the prompt
3. The subagent retains its full previous context — no need to re-explain
4. Return the subagent's summary to the user

### When to resume vs spawn new:

- **MUST resume**: Follow-up questions, iterations, test requests, or related changes on the same work
- **Spawn new**: Completely unrelated Python task in a different area of the codebase

### Rules:

- MUST ALWAYS resume the existing subagent for follow-up tasks on the same work
- MUST NEVER modify, read, or analyze Python files yourself
- MUST NEVER skip delegation for "simple" Python tasks — ALL Python work goes through the agent
- MUST NEVER spawn a new subagent when an active one can be resumed
- MUST pass the subagent's formatted response to the user exactly as returned — do NOT reformat or summarize it

## Next.js / TypeScript Code Delegation

When reading, writing, or editing Next.js / TypeScript code (any `.ts`, `.tsx`, or `.jsx` file), you MUST delegate to a subagent — but ONLY when the project is a Next.js project. This applies to ALL Next.js code operations regardless of size.

### Detection:

A project is a Next.js project if ANY of these are true:
- `next.config.ts` or `next.config.mjs` exists in the project root
- `package.json` contains `"next"` as a dependency or devDependency

If the project is NOT a Next.js project, handle `.ts`/`.tsx`/`.jsx` files directly — do NOT delegate.

### How to delegate (first task):

1. Use the Task tool with `subagent_type: "next-developer"` to spawn the agent
2. Pass the user's request as the task prompt
3. Save the returned **agent ID** for follow-up tasks
4. Return the subagent's summary to the user

**Fallback** — if `next-developer` is not recognized as a subagent type:
1. Run `echo $AI_AGENT_ENV_PATH` via Bash to get the repo path
2. Read `{AI_AGENT_ENV_PATH}/agents/next-developer.md` to get the full agent definition
3. Use the Task tool with `subagent_type: "general-purpose"`, passing the agent definition as the prompt
4. Save the returned agent ID and return the summary

### How to resume (follow-up tasks):

Same as Python delegation — resume the existing subagent for related follow-ups.

### Rules:

- MUST ALWAYS verify the project is a Next.js project before delegating `.ts`/`.tsx`/`.jsx` files
- MUST ALWAYS resume the existing subagent for follow-up tasks on the same work
- MUST NEVER modify, read, or analyze Next.js/TypeScript files yourself (in Next.js projects)
- MUST NEVER skip delegation for "simple" Next.js tasks — ALL Next.js work goes through the agent
- MUST NEVER spawn a new subagent when an active one can be resumed
- MUST pass the subagent's formatted response to the user exactly as returned — do NOT reformat or summarize it

## Post-Subagent Verification

After EVERY subagent run, you MUST verify the result before returning it to the user:

1. **Check the subagent's response** — Did it complete the full task, or did it stop partway? Look for phrases like "I couldn't", "I was unable", partial implementations, or TODO placeholders.
2. **Check for failures** — Read the last 5 lines of `.claude/logs/audit/tool_failures.jsonl` to see if the subagent hit errors during its run.
3. **If issues are found** — Resume the subagent to address them before reporting back. Do NOT pass incomplete or failed results to the user without first attempting a fix.

This applies to ALL subagent types (Python, Next.js, or any future agents).

## Non-Delegated Tasks

For tasks that do NOT involve Python code or Next.js/TypeScript code (documentation, configuration, shell scripts, etc.), handle them directly. Delegation is ONLY required for Python and Next.js work as described above.

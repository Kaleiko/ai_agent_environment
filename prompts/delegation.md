# Agent Delegation Rules

**These rules are MANDATORY. You MUST follow them for EVERY task without exception.**

## Python Code Delegation

When reading, writing, or editing Python code (any `.py` file), you MUST delegate to a subagent. This applies to ALL Python operations regardless of size — even single-line edits, quick reads, or minor fixes. You MUST NEVER handle Python code directly.

### How to delegate (first task):

1. Read `.claude/agents/python-developer.md` to get the full agent definition and workflow
2. Use the Task tool to spawn a subagent using the agent definition as the system prompt
3. Pass the user's request as the task argument
4. Save the returned **agent ID** for follow-up tasks
5. Return the subagent's summary to the user

### How to resume (follow-up tasks):

If the user's follow-up request relates to the same topic or codebase area as an active subagent, you MUST resume that subagent instead of spawning a new one.

1. Use the Task tool with the `resume` parameter, passing the saved agent ID
2. Pass the user's follow-up request as the prompt
3. The subagent retains its full previous context — no need to re-explain
4. Return the subagent's summary to the user

### When to resume vs spawn new:

- **MUST resume**: Follow-up questions, iterations, test requests, or related changes on the same work
- **Spawn new**: Completely unrelated Python task in a different area of the codebase

### Example:

```
User: "Fix the bug in src/auth/token.py"

You MUST:
1. Read .claude/agents/python-developer.md
2. Call Task tool with:
   - prompt: The agent definition + "Fix the bug in src/auth/token.py"
   - subagent_type: general-purpose
3. Save the returned agent ID (e.g., "abc123")
4. Return the summary

User: "Also check the refresh logic"

You MUST:
1. Call Task tool with:
   - resume: "abc123"
   - prompt: "Also check the refresh logic"
2. Return the summary (subagent remembers all prior context)

User: "Run the tests"

You MUST:
1. Call Task tool with:
   - resume: "abc123"
   - prompt: "Run the tests"
2. Return the summary
```

### Rules:

- MUST ALWAYS read the agent definition before spawning a NEW subagent
- MUST ALWAYS resume the existing subagent for follow-up tasks on the same work
- MUST NEVER modify, read, or analyze Python files yourself
- MUST NEVER skip delegation for "simple" Python tasks — ALL Python work goes through the agent
- MUST NEVER paraphrase or shorten the agent definition — pass it in full as the prompt
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

1. Read `.claude/agents/next-developer.md` to get the full agent definition and workflow
2. Use the Task tool to spawn a subagent using the agent definition as the system prompt
3. Pass the user's request as the task argument
4. Save the returned **agent ID** for follow-up tasks
5. Return the subagent's summary to the user

### How to resume (follow-up tasks):

If the user's follow-up request relates to the same topic or codebase area as an active subagent, you MUST resume that subagent instead of spawning a new one.

1. Use the Task tool with the `resume` parameter, passing the saved agent ID
2. Pass the user's follow-up request as the prompt
3. The subagent retains its full previous context — no need to re-explain
4. Return the subagent's summary to the user

### When to resume vs spawn new:

- **MUST resume**: Follow-up questions, iterations, test requests, or related changes on the same work
- **Spawn new**: Completely unrelated Next.js task in a different area of the codebase

### Example:

```
User: "Add a new dashboard page with charts"

You MUST:
1. Verify this is a Next.js project (check for next.config.ts or next in package.json)
2. Read .claude/agents/next-developer.md
3. Call Task tool with:
   - prompt: The agent definition + "Add a new dashboard page with charts"
   - subagent_type: general-purpose
4. Save the returned agent ID (e.g., "xyz789")
5. Return the summary

User: "Add a loading state for that page"

You MUST:
1. Call Task tool with:
   - resume: "xyz789"
   - prompt: "Add a loading state for that page"
2. Return the summary (subagent remembers all prior context)
```

### Rules:

- MUST ALWAYS verify the project is a Next.js project before delegating `.ts`/`.tsx`/`.jsx` files
- MUST ALWAYS read the agent definition before spawning a NEW subagent
- MUST ALWAYS resume the existing subagent for follow-up tasks on the same work
- MUST NEVER modify, read, or analyze Next.js/TypeScript files yourself (in Next.js projects)
- MUST NEVER skip delegation for "simple" Next.js tasks — ALL Next.js work goes through the agent
- MUST NEVER paraphrase or shorten the agent definition — pass it in full as the prompt
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

## No Agents Available

If `.claude/agents/` does not exist or is empty, inform the user and suggest running `/ai-initialize` to set up the project.

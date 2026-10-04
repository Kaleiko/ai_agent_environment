# Agent Delegation Rules

**The routing rules below are MANDATORY — they decide WHICH agent owns a file, and they exist because nothing else in the environment enforces it.**

The *mechanics* of spawning are not mandatory. They are a convenience snapshot, and they drift as Claude Code updates.

> **Precedence:** if anything in "Subagent Mechanics" disagrees with the `Agent` tool's own description or with an error the tool returns, **the tool wins.** Follow it and treat this file as out of date.

## Subagent Mechanics

Reference only — current as of Claude Code 2.1.250.

### Spawning

Use the **`Agent`** tool with `subagent_type` set to the agent name. Save the returned **agent ID** if you expect follow-up work. (The tool was formerly called `Task`; that name is stale.)

### Subagents run in the background

The `Agent` tool returns immediately with an agent ID; the result arrives later as a completion notification.

- You MUST NOT report, assume, or predict a subagent's results before its notification arrives — this one IS mandatory, because reporting invented results is a correctness failure, not a mechanics detail
- If the user asks about progress meanwhile, say the agent is still running
- You MAY continue unrelated work while it runs

### Parallel work is allowed and encouraged

Independent tasks SHOULD be dispatched concurrently — multiple `Agent` calls in a single message. Do not serialize work that has no dependency between its parts.

### Resuming vs. spawning fresh

`SendMessage` (with `to:` set to the agent ID) continues an existing subagent with its full context. Calling `Agent` again always starts a *fresh* agent with no memory of the earlier work.

- **Prefer resuming** for follow-ups, iterations, and related changes on the same files — skills are injected once at spawn, so resuming avoids re-paying for them
- **Spawn fresh** for independent work, including work that can run in parallel with an agent already in flight

If you no longer have the agent ID, use `ListAgents` to find it by name.

### Fallback if an agent type is unrecognized

Read the definition from `{{AI_AGENT_ENV_PATH}}/agents/<agent-name>.md` and spawn with `subagent_type: "general-purpose"`, passing it as the prompt.

## Reading vs. Editing

**Editing is delegated. Reading is not.**

- You MUST NOT create, modify, or delete a delegated-language file yourself — no edits, no matter how small
- You MAY read delegated-language files to diagnose, review, answer questions, or verify a subagent's work

Delegation keeps *written* code on-convention. Reading breaks no conventions, and diagnosing a file you are forbidden to open produces confident, wrong conclusions.

## Routing

Each agent's own `description` carries its full trigger criteria — read them in the agent list and trust them. Summary:

| You are editing | In a project where | Route to |
|---|---|---|
| `.py` | `playwright`/`pytest-playwright` in `pyproject.toml` or `requirements.txt`, **or** a `pages/` dir at root | `e2e-developer` |
| `.py` | anything else | `python-developer` |
| `.ts` `.tsx` `.jsx` | `next.config.ts`/`.mjs` exists, **or** `"next"` in `package.json` deps | `next-developer` |
| `.ts` `.tsx` `.jsx` | not a Next.js project | **handle directly — do NOT delegate** |

Playwright detection takes priority: in an E2E repo, Python goes to `e2e-developer`, never `python-developer`.

### Rules

- MUST verify project type before routing — the same extension goes to different agents
- MUST NEVER create, modify, or delete a delegated-language file yourself
- MUST NEVER skip delegation because an edit is "simple" — size is irrelevant
- MUST pass the subagent's formatted response to the user exactly as returned — do NOT reformat or summarize it

## Post-Subagent Verification

After EVERY subagent run, verify before returning the result:

1. **Check the response** — did it finish, or stop partway? Look for "I couldn't", partial implementations, TODO placeholders.
2. **Check for failures** — last 5 lines of `.claude/logs/audit/tool_failures.jsonl`.
3. **Check conventions were injected** — last line of `.claude/logs/audit/subagent_start.jsonl`. A `"note": "agent_type_unresolved"` or empty `skills_injected` means it may have written code without its conventions.
4. **Read the changed code** — you are permitted to. A subagent's own summary is not verification of itself.
5. **If issues are found** — resume it via `SendMessage` before reporting back.

## Non-Delegated Tasks

For tasks that do NOT involve Python or Next.js/TypeScript **edits** (documentation, configuration, shell scripts, analysis, code review), handle them directly.

### Keep documentation current in the same turn

When a change you make directly alters behavior that is documented somewhere, update that documentation **before reporting the work done** — not as a follow-up.

Check the owning docs whenever you change:

- an installer, hook wiring, or any setup step described in `README.md`
- a convention, path, or mechanism named in `CLAUDE.md` or a skill file
- a command, flag, or file layout that a reader would otherwise follow and get wrong

Delegated code changes already carry this requirement through their conventions skill. This closes the same gap for work you handle yourself, where nothing else enforces it.

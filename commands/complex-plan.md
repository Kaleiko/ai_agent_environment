# /complex-plan — Multi-Agent Planning Pipeline

You are orchestrating a multi-agent planning pipeline for a complex feature that spans multiple codebases. Follow these 7 phases IN ORDER. Do NOT skip phases or combine them.

**User's feature description:** $ARGUMENTS

---

## Phase 1: GATHER

Ask the user clarifying questions to build a complete Feature Summary. You MUST collect:

1. **Problem Statement** — What problem does this feature solve? Who benefits?
2. **Codebases** — Which codebases are involved? Get the absolute path for each one.
3. **Constraints** — Performance requirements, backward compatibility, deadlines, tech restrictions.
4. **Success Criteria** — How will we know this feature is complete and correct?
5. **Scope Boundaries** — What is explicitly OUT of scope?

After gathering answers, produce a **Feature Summary** in this format:

```
## Feature Summary
- **Feature**: [name]
- **Problem**: [1-2 sentences]
- **Codebases**: [list with paths]
- **Constraints**: [list]
- **Success Criteria**: [list]
- **Out of Scope**: [list]
```

If `$ARGUMENTS` provides enough detail, pre-fill what you can and confirm with the user rather than asking from scratch.

---

## Phase 2: APPROVE SCOPE

Present the Feature Summary to the user and ask for explicit approval before proceeding. Use AskUserQuestion:

- **Option 1**: "Approved — proceed to planning"
- **Option 2**: "Needs changes" (then loop back to Phase 1 to revise)

Do NOT proceed to Phase 3 until the user selects "Approved."

---

## Phase 3: PLAN (Parallel Subagents)

Spawn one `plan-explorer` subagent PER codebase, all in parallel. For each, use the Task tool:

```
subagent_type: "Plan"
```

Pass this prompt to each subagent:

```
You are a codebase planner. Explore the codebase at [PATH] and produce a planning spec for this feature.

## Feature Summary
[paste the approved Feature Summary here]

## Your Task
1. Explore the codebase thoroughly — understand the architecture, patterns, and relevant code
2. Produce a spec in EXACTLY this format:

### Feature ID
[codebase-name]-[feature-short-name]

### Problem Statement
[How this codebase specifically relates to the feature]

### Current State
[What exists today that's relevant — architecture, patterns, endpoints, models, etc.]

### Design
[Architectural approach — components, data flow, integration points. Stay at the design level, NOT file-level implementation details.]

### Acceptance Criteria
[Specific, testable criteria for this codebase's part of the feature]

### Cross-Codebase Dependencies
[What this codebase needs FROM or provides TO other codebases — APIs, events, shared types, data contracts]

### Risks
[Only if genuinely warranted — don't fabricate risks. If none, write "None identified."]
```

Save the agent ID for each subagent. Collect ALL plan outputs before proceeding.

---

## Phase 4: CRITIC (Single Subagent)

Spawn a single `plan-critic` subagent using the Task tool:

```
subagent_type: "Plan"
```

Pass this prompt:

```
You are a planning critic. Review these codebase plans for a cross-codebase feature and find problems.

## Feature Summary
[paste Feature Summary]

## Plans to Review
[paste ALL plan outputs from Phase 3, clearly labeled by codebase]

## Your Task
Perform a thorough review. Output in EXACTLY this format:

### Cross-Codebase Issues
[Conflicts between plans — mismatched APIs, incompatible assumptions, missing contracts, ordering problems]

### Per-Plan Feedback
For each plan:
- **[codebase name]**: [specific feedback — what's good, what needs revision, what's missing]

### Dependency Graph Validation
[Are the cross-codebase dependencies consistent? Does Plan A's "provides" match Plan B's "needs"? Draw the dependency graph.]

### Missing Considerations
[Anything ALL plans missed — migration strategy, rollback plan, feature flags, monitoring, etc.]

### Verdict
One of:
- **APPROVE** — Plans are solid, proceed to synthesis
- **APPROVE WITH CHANGES** — Minor issues noted above, synthesizer should incorporate feedback
- **NEEDS REWORK** — Fundamental issues found, plans need revision before synthesis

You may explore any of the codebases to verify planner claims. Codebase paths:
[list paths]
```

If the critic verdict is **NEEDS REWORK**, resume the relevant plan-explorer subagents with the critic's feedback and re-run Phase 4. Loop until the verdict is APPROVE or APPROVE WITH CHANGES.

---

## Phase 5: SYNTHESIZE (Single Subagent)

Spawn a single `plan-synthesizer` subagent using the Task tool:

```
subagent_type: "Plan"
```

Pass this prompt:

```
You are a planning synthesizer. Combine these reviewed plans into a unified implementation spec.

## Feature Summary
[paste Feature Summary]

## Plans
[paste ALL plan outputs from Phase 3]

## Critic Feedback
[paste critic output from Phase 4]

## Your Task
Produce a unified spec in EXACTLY this format:

### Executive Summary
[2-3 sentences: what we're building, why, and the high-level approach]

### Implementation Order
[Ordered list of work items with parallelism noted. Format:]
1. [Item] — [codebase] (can parallel with: X, Y)
2. [Item] — [codebase] (blocked by: 1)
...

### Per-Codebase Specs
For each codebase, the REVISED spec incorporating critic feedback:
#### [Codebase Name]
- **Design**: [revised design]
- **Acceptance Criteria**: [revised criteria]
- **Key Decisions**: [any decisions made based on critic feedback]

### Cross-Codebase Contracts
[Explicit API contracts, event schemas, shared types that codebases must agree on. Be specific — include endpoint paths, payload shapes, event names.]

### Dependency Graph
[Visual or textual representation of what depends on what, both within and across codebases]

### Risks & Mitigations
[Only genuine risks with concrete mitigations]

### Open Questions
[Anything that still needs user/team input before implementation can begin. If none, write "None — ready for implementation."]
```

---

## Phase 6: APPROVE PLAN

Present the synthesizer's unified spec to the user. Use AskUserQuestion:

- **Option 1**: "Approved — ready for implementation"
- **Option 2**: "Needs changes" (describe what to revise, then loop back to the appropriate phase)

Do NOT proceed to Phase 7 until approved.

---

## Phase 7: HANDOFF

The unified spec is now the implementation plan. Tell the user:

1. The plan is approved and ready for implementation
2. Each per-codebase spec can be handed to the appropriate implementation agent (python-developer, next-developer, etc.)
3. Implementation should follow the Implementation Order from the spec
4. Cross-codebase contracts should be implemented first to unblock parallel work

---

## Rules

- NEVER skip a phase or combine phases
- ALWAYS wait for user approval at Phase 2 and Phase 6
- ALWAYS spawn plan-explorer subagents in PARALLEL (one per codebase)
- Pass subagent outputs VERBATIM to the next phase — do not summarize or rewrite them
- If a phase fails or a subagent returns an incomplete result, retry that phase before moving on
- Keep the user informed of progress between phases with brief status updates

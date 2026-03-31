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
1. Start by checking for `ARCHITECTURE.md` and `README.md` in the project root — if either exists, read them first to orient to the codebase structure, purpose, and data flow before exploring further
2. Explore the codebase thoroughly — understand the architecture, patterns, and relevant code
3. Produce a spec in EXACTLY this format:

### Feature ID
[codebase-name]-[feature-short-name]

### Problem Statement
[How this codebase specifically relates to the feature]

### Current State
[What exists today that's relevant — architecture, patterns, endpoints, models, etc.]

### Features & Expected Behavior
[List each feature or capability this codebase must provide. For each, describe:]
- What the feature does (user-facing or system-facing behavior)
- Expected inputs (parameters, query strings, request bodies, data sources)
- Expected outputs (response format, return types, side effects)

### API Contracts (if applicable)
[For any API endpoints this codebase must expose or consume, specify:]
- HTTP method and URL path (e.g., `GET /api/vehicles`)
- Query parameters or request body schema with types
- Response schema with types and example payload
- Error response format

### Acceptance Criteria
[Specific, testable criteria for this codebase's part of the feature — focused on WHAT the system should do, not HOW it should be implemented]

### Cross-Codebase Dependencies
[What this codebase needs FROM or provides TO other codebases — API contracts, event schemas, shared data formats. Be specific about the interface, not the implementation.]

### Risks
[Only if genuinely warranted — don't fabricate risks. If none, write "None identified."]

## IMPORTANT — Scope Boundaries
- NEVER specify file names, directory structures, class names, or module organization — that is the developer agent's responsibility
- NEVER dictate implementation patterns (e.g., "use a factory pattern", "create a service class") — the developer agent chooses the implementation approach
- DO specify what features to build, what inputs they accept, what outputs they produce, and what contracts they must honor
- Think of this spec as a product/architecture brief, NOT a code blueprint
```

Save the agent ID for each subagent. Collect ALL plan outputs before proceeding.

---

## Phase 4: CRITIC → PLANNER REVISION LOOP

This phase is a loop between the critic and the planners. The loop continues until the critic approves ALL plans. Do NOT proceed to Phase 5 until the critic verdict is **APPROVE**.

### Step 4a: CRITIC REVIEW

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
[paste ALL plan outputs from Phase 3 (or revised plans from Step 4b if this is a re-review), clearly labeled by codebase]

## Review Round
[Round number — e.g., "Round 1", "Round 2", etc.]

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
- **APPROVE** — All plans are solid and consistent, proceed to synthesis
- **NEEDS REVISION** — Issues found above must be addressed by the planners before proceeding

If NEEDS REVISION, clearly specify which codebase plan(s) need changes and exactly what must be fixed.

You may explore any of the codebases to verify planner claims. Codebase paths:
[list paths]
```

### Step 4b: PLANNER REVISION (only if critic verdict is NEEDS REVISION)

Resume the plan-explorer subagents whose plans were flagged by the critic. For each flagged plan, resume the subagent with:

```
The critic has reviewed your plan and found issues that must be addressed.

## Critic Feedback for Your Plan
[paste the specific Per-Plan Feedback for this codebase from Step 4a]

## Cross-Codebase Issues Affecting Your Plan
[paste any Cross-Codebase Issues relevant to this codebase]

## Missing Considerations
[paste any Missing Considerations that apply]

## Your Task
Revise your plan to address ALL of the critic's feedback. Produce a COMPLETE revised plan in the same format as your original — do not produce a partial diff. The revised plan will be sent back to the critic for re-review.
```

After ALL flagged planners have produced revised plans, go back to **Step 4a** with the updated plans. Increment the review round number.

### Loop Exit

- Exit the loop ONLY when the critic verdict is **APPROVE**
- Maximum 3 rounds — if the critic has not approved after 3 rounds, present the current state to the user and ask for guidance
- Inform the user of each round's status (e.g., "Critic round 2: requested revisions to backend plan, frontend plan approved")

---

## Phase 5: SYNTHESIZE (Single Subagent)

Spawn a single `plan-synthesizer` subagent using the Task tool. This phase runs ONLY after the critic has approved all plans.

```
subagent_type: "Plan"
```

Pass this prompt:

```
You are a planning synthesizer. Combine these critic-approved plans into a unified implementation spec.

## Feature Summary
[paste Feature Summary]

## Approved Plans
[paste ALL final approved plan outputs — these have already been reviewed and approved by the critic]

## Final Critic Review
[paste the final APPROVE critic output for reference]

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
For each codebase:
#### [Codebase Name]
- **Features & Expected Behavior**: [what to build — inputs, outputs, behavior]
- **API Contracts**: [endpoints, parameters, response schemas — if applicable]
- **Acceptance Criteria**: [testable criteria]
- **Key Decisions**: [any decisions made during the planning/review process]

IMPORTANT: Per-codebase specs MUST define WHAT to build and the contracts to honor. NEVER specify file structures, class names, directory layouts, or implementation patterns — those decisions belong to the developer agent.

### Cross-Codebase Contracts
[Explicit API contracts, event schemas, shared data formats that codebases must agree on. Be specific — include endpoint paths, query parameters, request/response payload shapes with types, event names. These contracts are the handshake between developer agents.]

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

1. Save the approved unified spec to `.claude/plans/` in each relevant codebase directory (e.g., `.claude/plans/ARCHITECTURE_PLAN.md` or `.claude/plans/{feature-name}_PLAN.md`)
2. Tell the user:
   - The plan is approved and saved
   - Each per-codebase spec can be handed to the appropriate implementation agent (python-developer, next-developer, etc.)
   - Implementation should follow the Implementation Order from the spec
   - Cross-codebase contracts should be implemented first to unblock parallel work

---

## Rules

- NEVER skip a phase or combine phases
- ALWAYS wait for user approval at Phase 2 and Phase 6
- ALWAYS spawn plan-explorer subagents in PARALLEL (one per codebase)
- Pass subagent outputs VERBATIM to the next phase — do not summarize or rewrite them
- If a phase fails or a subagent returns an incomplete result, retry that phase before moving on
- Keep the user informed of progress between phases with brief status updates
- Phase 4 is a LOOP — the critic and planners go back and forth until the critic approves. NEVER skip the revision step when the critic finds issues. NEVER send unapproved plans to the synthesizer
- Maximum 3 critic rounds — escalate to the user if not resolved

### Planning Boundary — MANDATORY
- The plan defines WHAT to build, not HOW to build it
- NEVER specify file names, directory structures, class names, module organization, or implementation patterns
- MUST specify: features, expected behavior, input parameters, output formats, API contracts (URLs, methods, request/response schemas), acceptance criteria
- Developer agents (python-developer, next-developer) own ALL implementation decisions — file layout, code architecture, design patterns, naming
- Cross-codebase contracts (API endpoints, event schemas, shared data formats) are the primary deliverable — they are what allow independent developer agents to build compatible systems

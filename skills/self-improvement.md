---
name: self-improvement
scope: global
description: "Diagnose and durably fix the cause when the user corrects you, reminds you of something you should have done, repeats an instruction, or points out a missed step. Use the moment a correction lands — a correction is evidence that an instruction is missing, stale, or ineffective."
globs: ["**/*"]
---

# Self-Improvement

**A correction is a defect report about your instructions, not just about this turn.**

Fixing only the immediate mistake guarantees it recurs. The job is to find the instruction
that should have prevented it and repair that — or to correctly decide no instruction was
missing, which is just as often the right answer.

---

## 1. Recognize the signal

Trigger on any of:

- The user tells you to do something you should already have done ("did you update the docs?")
- The user repeats an instruction they already gave
- The user corrects an approach, format, or level of detail
- The user expresses frustration at having to ask
- You notice mid-task that you skipped a step a rule required

**Not a trigger:**

- A new requirement that was never stated ("also add dark mode") — that's scope, not correction
- The user changing their mind
- A judgment call where your choice was defensible and they simply preferred the other
- A one-off tweak with no general principle behind it ("make this one blue")

Misreading new scope as correction produces spurious rules. When genuinely unsure, do nothing —
a missed lesson costs less than a bad rule, because a bad rule misfires on every future session.

---

## 2. Diagnose before writing anything

Ask, in order:

1. **Did a rule already cover this?**
   - *Yes, and you missed it* → the rule is ineffective. Is it buried, ambiguous, or contradicted
     elsewhere? Fix its clarity or placement. **Do not add a second rule saying the same thing.**
   - *Yes, but it was wrong or outdated* → fix the rule itself. A stale mandatory rule is worse
     than no rule, because it overrides correct default behavior.
   - *No rule covered it* → continue.

2. **Will this recur?** If this exact situation is unlikely to arise again, stop. Record nothing.

3. **Is it universal or local?** Does it apply to every project, or only this one? This decides
   where it lands.

---

## 3. Route to the right artifact

| What you learned | Where it goes |
|---|---|
| A preference or constraint specific to this project | Project memory (`feedback` or `project` type) |
| A universal preference about how you work | A global skill — e.g. communication standards |
| A missing or stale behavioral rule | `~/.claude/rules/delegation.md`, or the owning skill |
| A durable fact about this codebase | That project's `CLAUDE.md` |
| A convention for a specific agent | That agent's skill file |
| Nothing generalizable | **Nothing.** This is a valid and common outcome. |

Route to exactly one place. The same lesson written into two artifacts will drift, and the
copies will eventually contradict each other.

---

## 4. Propose vs. apply

**Write directly:** project memories. They are additive, scoped, and cheap to correct.

**Propose and wait for approval:** anything that governs future behavior —
`delegation.md`, global skills, agent definitions, `CLAUDE.md`.

State the proposal in one or two sentences: what you'd change, where, and which correction
prompted it. Then continue the actual task — do not block on the answer.

Editing your own governing rules without the user seeing the change is how a rule set drifts
into something nobody chose.

---

## 5. Keep the rule set lean

Every global rule costs context in **every** session, forever.

- **Prefer editing an existing rule over adding a new one.** Most corrections are a
  clarification of something already written.
- **Prefer deleting over qualifying.** If a rule needed an exception, it may have been wrong.
- **Be specific.** "Be more careful" changes nothing. "Update README when install.sh behavior
  changes" is checkable.
- **Always record the why.** A rule without its reason gets followed cargo-cult long after the
  reason expires, and nobody can tell when it is safe to remove.

A rule set that grows monotonically becomes noise, and noise is indistinguishable from having
no rules at all.

---

## 6. Memory format

Match the existing convention:

```markdown
---
name: <short-kebab-case-slug>
description: <one line, used to decide relevance on recall>
metadata:
  type: user | feedback | project | reference
---

<the fact>

**Why:** <what happened, with the date, and the user's own words where possible>

**How to apply:** <when this applies, and when it does not> Related: [[other-memory]].
```

Then add one line to `MEMORY.md`: `- [Title](file.md) — hook`.

Check for an existing memory covering the same ground first and update it rather than
creating a near-duplicate. Delete memories that turn out to be wrong.

---

## 7. Close the loop

When you act on a correction, say so in one line — what you changed, or what you proposed.

The user needs to know the lesson landed somewhere durable rather than evaporating at the end
of the session. One sentence is enough; this is not a ceremony.

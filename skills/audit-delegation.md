---
name: audit-delegation
scope: global
description: "Audit the PreToolUse log for delegation violations — files edited directly by the main thread, or routed to the wrong agent. Use when the user asks whether delegation rules are being followed, or to check for regressions after changing agents or routing."
globs: ["**/*"]
---

# Audit Delegation

Checks whether delegated-language files were actually edited by the agents that own them, using
the `PreToolUse` audit log as the record of what happened.

This is **post-hoc**. It detects violations after the fact; it does not prevent them.

---

## What counts as a violation

| Edit on | Should have been | Violation if |
|---|---|---|
| `.py` in a Playwright E2E repo | `e2e-developer` | any other agent, or the main thread |
| `.py` elsewhere | `python-developer` | any other agent, or the main thread |
| `.ts` `.tsx` `.jsx` in a Next.js project | `next-developer` | any other agent, or the main thread |
| `.ts` `.tsx` `.jsx` outside Next.js | handled directly | *not* a violation — direct editing is correct here |

**The discriminator is `agent_id`, not `agent_type`.** A record with no `agent_id` is a main-thread
call. An empty `agent_type` on a main-thread record is correct and expected — it is not the
`agent_type_unresolved` bug, which applies only to `SubagentStart`/`SubagentStop`.

---

## Run the audit

```bash
python3 - "$PWD/.claude/logs/audit/pre_tool_use.jsonl" <<'PY'
import json, sys
from pathlib import Path

LOG = Path(sys.argv[1])
if not LOG.is_file():
    print(f"No audit log at {LOG}"); raise SystemExit(0)

PY_AGENTS = {"python-developer", "e2e-developer"}
WEB_EXT = (".ts", ".tsx", ".jsx")

def project_kind(cwd: str) -> set[str]:
    """Best-effort project detection. Returns tags; empty if cwd is gone."""
    root, tags = Path(cwd), set()
    if not root.is_dir():
        return tags
    for name in ("pyproject.toml", "requirements.txt"):
        f = root / name
        if f.is_file():
            try:
                if "playwright" in f.read_text(errors="ignore"):
                    tags.add("playwright")
            except OSError:
                pass
    if (root / "pages").is_dir():
        tags.add("playwright")
    pkg = root / "package.json"
    if (root / "next.config.ts").is_file() or (root / "next.config.mjs").is_file():
        tags.add("next")
    elif pkg.is_file():
        try:
            if '"next"' in pkg.read_text(errors="ignore"):
                tags.add("next")
        except OSError:
            pass
    return tags

records, bad_json = [], 0
for line in LOG.read_text(errors="ignore").splitlines():
    line = line.strip()
    if not line:
        continue
    try:
        records.append(json.loads(line))
    except json.JSONDecodeError:
        bad_json += 1

kinds, violations, checked = {}, [], 0
for r in records:
    if r.get("tool_name") not in ("Edit", "Write", "NotebookEdit"):
        continue
    path = str((r.get("tool_input") or {}).get("file_path") or "")
    if not path:
        continue
    cwd = r.get("cwd") or ""
    if cwd not in kinds:
        kinds[cwd] = project_kind(cwd)
    tags = kinds[cwd]
    actual = r.get("agent_type") or None
    main_thread = not r.get("agent_id")

    expected = None
    if path.endswith(".py"):
        expected = "e2e-developer" if "playwright" in tags else "python-developer"
        # cwd gone: can't tell which Python agent, but delegation itself is still checkable
        loose = not tags and not (Path(cwd).is_dir() if cwd else False)
        checked += 1
        if main_thread:
            violations.append((r, path, expected, "main thread", "VIOLATION"))
        elif actual == "general-purpose":
            # documented fallback when the named agent fails to resolve — verify, don't assume
            violations.append((r, path, expected, actual, "FALLBACK?"))
        elif actual not in PY_AGENTS:
            violations.append((r, path, expected, actual, "VIOLATION"))
        elif not loose and actual != expected:
            violations.append((r, path, expected, actual, "WRONG AGENT"))
    elif path.endswith(WEB_EXT) and "next" in tags:
        checked += 1
        if main_thread:
            violations.append((r, path, expected, "main thread", "VIOLATION"))
        elif actual == "general-purpose":
            violations.append((r, path, expected, actual, "FALLBACK?"))
        elif actual != expected:
            violations.append((r, path, expected, actual, "VIOLATION"))

print(f"records: {len(records)}   delegated-language edits checked: {checked}"
      + (f"   unparseable lines: {bad_json}" if bad_json else ""))

if not violations:
    print("\nNo delegation violations found.")
    raise SystemExit(0)

order = {"VIOLATION": 0, "WRONG AGENT": 1, "FALLBACK?": 2}
tally = {}
for *_rest, kind in violations:
    tally[kind] = tally.get(kind, 0) + 1
print("\n" + "  ".join(f"{k}: {v}" for k, v in sorted(tally.items(), key=lambda kv: order[kv[0]])))

for kind in sorted(tally, key=lambda k: order[k]):
    group = [v for v in violations if v[4] == kind]
    print(f"\n--- {kind} ({len(group)}) ---")
    if kind == "FALLBACK?":
        print("  general-purpose is the documented fallback when the named agent fails to")
        print("  resolve. Cross-check tool_failures.jsonl for \"not found\" near these times")
        print("  before treating them as real violations.")
    by_session = {}
    for r, path, expected, actual, _ in group:
        by_session.setdefault(r.get("session_id", "?"), []).append((r, path, expected, actual))
    for sid, items in by_session.items():
        print(f"  session {sid[:8]}  ({len(items)})")
        for r, path, expected, actual in items[:6]:
            print(f"    {r.get('_timestamp','?')[:19]}  {r.get('tool_name'):6}  {path.split('/')[-1]}")
            print(f"        expected {expected}, was {actual}")
        if len(items) > 6:
            print(f"        ... and {len(items) - 6} more")
PY
```

Run it from the project root. To audit a different project, substitute its path for `$PWD`.

---

## Interpreting the result

- **No violations** — routing is holding. This is the expected result; treat it as a regression check.
- **Main-thread edits** — the delegation rules were not followed. Check whether the rule is
  present and unambiguous in `delegation.md` and in the agent's `description`.
- **Wrong agent** — usually project detection, not discipline: `python-developer` used in a
  Playwright repo, or `next-developer` in a plain TypeScript project. Fix the detection criteria.
- **`FALLBACK?` is not automatically a violation.** When a named agent fails to resolve, the rules
  say to spawn `general-purpose` with the agent definition as the prompt — which looks identical to
  misrouting in the log. Check `tool_failures.jsonl` for an `Agent type '<name>' not found` error
  near that timestamp. If one is there, the fallback worked correctly and the real problem was the
  unregistered agent.
- **Repeated violations of the same kind** are the valuable signal. A rule that is broken
  repeatedly is ineffective, not merely unlucky — route that into `self-improvement`.

## Limitations

- Project type is detected from the project's **current** state, so a repo that gained or lost
  Playwright since an edit may be classified by today's layout rather than the layout at the time.
  When the logged `cwd` no longer exists, the audit still flags undelegated edits but will not
  claim which of the two Python agents was correct.
- Only `Edit`, `Write`, and `NotebookEdit` are inspected. A file written through `Bash`
  (`cat > x.py`, `sed -i`) is invisible to this audit — a real bypass path worth remembering.
- The log is trimmed at 10 MB, so very old history may be gone.

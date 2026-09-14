#!/bin/bash
# =============================================================================
# AI Agent Environment — Global Installer
# =============================================================================
#
# PURPOSE:
#   Sets up global Claude Code configuration so every project gets hooks,
#   agents, and delegation rules automatically. No per-project setup needed.
#
# PORTABILITY:
#   Nothing at runtime depends on the AI_AGENT_ENV_PATH environment variable.
#   This repo contains no machine-specific paths; each machine's install.sh
#   run resolves its own absolute path and bakes it into the generated
#   artifacts under ~/.claude/ (which are never committed):
#
#     - Hook commands in settings.json get absolute script paths.
#     - Python hooks self-locate via Path(__file__), so they need nothing.
#     - Markdown files ship a {{AI_AGENT_ENV_PATH}} placeholder, which is
#       substituted with the real path as they are copied into ~/.claude/.
#
#   AI_AGENT_ENV_PATH is still exported and pinned in settings.json, but only
#   as a convenience for humans poking around in a shell. If it is unset or
#   wrong, nothing breaks.
#
# WHAT IT DOES:
#   1. Installs ai-interaction skill to ~/.claude/skills/
#   2. Copies delegation rules to ~/.claude/rules/
#   3. Copies agent definitions to ~/.claude/agents/
#   4. Copies commands to ~/.claude/commands/
#   5. Merges hook definitions into ~/.claude/settings.json
#   6. Sets AI_AGENT_ENV_PATH environment variable (convenience only)
#   7. Cleans up retired skills (ai-initialize, ai-sync)
#
# USAGE:
#   ./install.sh
#   # Then restart Claude Code. No shell reload required.
#
# SAFE TO RE-RUN:
#   - Files are overwritten with latest versions from the repo
#   - Environment variable is only added once (skipped if already present)
#   - Existing settings.json keys (statusLine, etc.) are preserved
#   - A corrupt settings.json is backed up and the install aborts
# =============================================================================

set -euo pipefail

# Resolve the PHYSICAL path (-P), not the logical one. A logical path can point
# through a symlink (e.g. ~/Dropbox -> ~/Library/CloudStorage/Dropbox), which
# would disagree with Python's Path.resolve() and break the string-prefix
# comparisons pre_tool_use.py makes against its allowed directories.
REPO_DIR="$(cd "$(dirname "$0")" && pwd -P)"

SKILLS_DIR="$HOME/.claude/skills"
RULES_DIR="$HOME/.claude/rules"
AGENTS_DIR="$HOME/.claude/agents"
COMMANDS_DIR="$HOME/.claude/commands"

SHELL_RC="$HOME/.zshrc"
[ -f "$SHELL_RC" ] || SHELL_RC="$HOME/.bashrc"

echo "Installing from: $REPO_DIR"
echo ""

# ---------------------------------------------------------------------------
# Preflight: the hook commands invoke `python3`. If it is missing, every hook
# fails at runtime — and because PreToolUse matches Bash|Read|Write|Edit, that
# means every tool call is blocked. Fail loudly here instead.
# ---------------------------------------------------------------------------

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found on PATH." >&2
  echo "       The hooks are Python scripts and cannot run without it." >&2
  echo "       Install python3, then re-run this script." >&2
  exit 1
fi
echo "  Found python3: $(command -v python3)"

# ---------------------------------------------------------------------------
# render SRC DST — copy a file, substituting {{AI_AGENT_ENV_PATH}} with the
# absolute repo path. Uses '|' as the sed delimiter since the path contains '/'.
# ---------------------------------------------------------------------------

render() {
  sed "s|{{AI_AGENT_ENV_PATH}}|$REPO_DIR|g" "$1" > "$2"
}

# ---------------------------------------------------------------------------
# Step 1: Install global skill (ai-interaction only)
# ---------------------------------------------------------------------------

mkdir -p "$SKILLS_DIR/ai-interaction"
render "$REPO_DIR/skills/ai-interaction.md" "$SKILLS_DIR/ai-interaction/SKILL.md"
echo "  Installed skill: ai-interaction"

# ---------------------------------------------------------------------------
# Step 2: Copy delegation rules to ~/.claude/rules/
# ---------------------------------------------------------------------------

mkdir -p "$RULES_DIR"
render "$REPO_DIR/prompts/delegation.md" "$RULES_DIR/delegation.md"
echo "  Installed rule: delegation.md"

# ---------------------------------------------------------------------------
# Step 3: Copy agent definitions to ~/.claude/agents/
# ---------------------------------------------------------------------------

mkdir -p "$AGENTS_DIR"
for agent_file in "$REPO_DIR"/agents/*.md; do
  [ -f "$agent_file" ] || continue
  render "$agent_file" "$AGENTS_DIR/$(basename "$agent_file")"
  echo "  Installed agent: $(basename "$agent_file")"
done

# ---------------------------------------------------------------------------
# Step 4: Copy commands to ~/.claude/commands/
# ---------------------------------------------------------------------------

mkdir -p "$COMMANDS_DIR"
for cmd_file in "$REPO_DIR"/commands/*.md; do
  [ -f "$cmd_file" ] || continue
  render "$cmd_file" "$COMMANDS_DIR/$(basename "$cmd_file")"
  echo "  Installed command: $(basename "$cmd_file")"
done

# ---------------------------------------------------------------------------
# Step 5: Merge hooks into ~/.claude/settings.json
#
# The script resolves the repo root from its own location, so it needs no
# environment. It aborts non-zero on a corrupt settings.json, which `set -e`
# turns into a failed install rather than a silently clobbered config.
# ---------------------------------------------------------------------------

python3 "$REPO_DIR/scripts/merge_global_settings.py"

# ---------------------------------------------------------------------------
# Step 6: Set up AI_AGENT_ENV_PATH environment variable
#
# Convenience only — nothing at runtime reads this. It is here so that you can
# `cd $AI_AGENT_ENV_PATH` in a terminal.
# ---------------------------------------------------------------------------

if grep -q "AI_AGENT_ENV_PATH" "$SHELL_RC" 2>/dev/null; then
  echo ""
  echo "  AI_AGENT_ENV_PATH already in $SHELL_RC (skipping)"
else
  echo "" >> "$SHELL_RC"
  echo "# AI Agent Environment — path to skills/agents repo (convenience only)" >> "$SHELL_RC"
  echo "export AI_AGENT_ENV_PATH=\"$REPO_DIR\"" >> "$SHELL_RC"
  echo ""
  echo "  Added AI_AGENT_ENV_PATH=$REPO_DIR to $SHELL_RC"
fi

# ---------------------------------------------------------------------------
# Step 7: Clean up retired skills
# ---------------------------------------------------------------------------

for retired in ai-initialize ai-sync; do
  if [ -d "$SKILLS_DIR/$retired" ]; then
    rm -rf "$SKILLS_DIR/$retired"
    echo "  Removed retired skill: $retired"
  fi
done

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "Done. Restart Claude Code to pick up the new agents and hooks."
echo ""
echo "No per-project setup needed — hooks, agents, and delegation are global."

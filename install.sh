#!/bin/bash
# =============================================================================
# AI Agent Environment — Global Installer
# =============================================================================
#
# PURPOSE:
#   Sets up global Claude Code configuration so every project gets hooks,
#   agents, and delegation rules automatically. No per-project setup needed.
#
# WHAT IT DOES:
#   1. Installs ai-interaction skill to ~/.claude/skills/
#   2. Copies delegation rules to ~/.claude/rules/
#   3. Copies agent definitions to ~/.claude/agents/
#   4. Merges hook definitions into ~/.claude/settings.json
#   5. Sets AI_AGENT_ENV_PATH environment variable
#   6. Cleans up retired skills (ai-initialize, ai-sync)
#
# USAGE:
#   ./install.sh
#   source ~/.zshrc   # (or ~/.bashrc) to pick up the new env var
#   # Then restart Claude Code
#
# SAFE TO RE-RUN:
#   - Files are overwritten with latest versions from the repo
#   - Environment variable is only added once (skipped if already present)
#   - Existing settings.json keys (statusLine, etc.) are preserved
# =============================================================================

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

SKILLS_DIR="$HOME/.claude/skills"
RULES_DIR="$HOME/.claude/rules"
AGENTS_DIR="$HOME/.claude/agents"

SHELL_RC="$HOME/.zshrc"
[ -f "$SHELL_RC" ] || SHELL_RC="$HOME/.bashrc"

echo "Installing from: $REPO_DIR"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Install global skill (ai-interaction only)
# ---------------------------------------------------------------------------

mkdir -p "$SKILLS_DIR/ai-interaction"
cp "$REPO_DIR/skills/ai-interaction.md" "$SKILLS_DIR/ai-interaction/SKILL.md"
echo "  Installed skill: ai-interaction"

# ---------------------------------------------------------------------------
# Step 2: Copy delegation rules to ~/.claude/rules/
# ---------------------------------------------------------------------------

mkdir -p "$RULES_DIR"
cp "$REPO_DIR/prompts/delegation.md" "$RULES_DIR/delegation.md"
echo "  Installed rule: delegation.md"

# ---------------------------------------------------------------------------
# Step 3: Copy agent definitions to ~/.claude/agents/
# ---------------------------------------------------------------------------

mkdir -p "$AGENTS_DIR"
for agent_file in "$REPO_DIR"/agents/*.md; do
  [ -f "$agent_file" ] || continue
  cp "$agent_file" "$AGENTS_DIR/$(basename "$agent_file")"
  echo "  Installed agent: $(basename "$agent_file")"
done

# ---------------------------------------------------------------------------
# Step 4: Merge hooks into ~/.claude/settings.json
# ---------------------------------------------------------------------------

# Export so the merge script can reference it if needed
export AI_AGENT_ENV_PATH="$REPO_DIR"
python3 "$REPO_DIR/scripts/merge_global_settings.py"

# ---------------------------------------------------------------------------
# Step 5: Set up AI_AGENT_ENV_PATH environment variable
# ---------------------------------------------------------------------------

if grep -q "AI_AGENT_ENV_PATH" "$SHELL_RC" 2>/dev/null; then
  echo ""
  echo "  AI_AGENT_ENV_PATH already in $SHELL_RC (skipping)"
else
  echo "" >> "$SHELL_RC"
  echo "# AI Agent Environment — path to skills/agents repo" >> "$SHELL_RC"
  echo "export AI_AGENT_ENV_PATH=\"$REPO_DIR\"" >> "$SHELL_RC"
  echo ""
  echo "  Added AI_AGENT_ENV_PATH=$REPO_DIR to $SHELL_RC"
fi

# ---------------------------------------------------------------------------
# Step 6: Clean up retired skills
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
echo "Done. Restart your shell and Claude Code:"
echo "  source $SHELL_RC"
echo ""
echo "No per-project setup needed — hooks, agents, and delegation are global."

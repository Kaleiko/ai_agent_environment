#!/bin/bash
# =============================================================================
# AI Agent Environment — Global Installer
# =============================================================================
#
# PURPOSE:
#   One-time setup script that installs the global components needed to use
#   the AI Agent Environment on any machine. Run this after cloning the repo.
#
# WHAT IT DOES:
#   1. Installs global skills to ~/.claude/skills/ (subdirectory format):
#      - ai-interaction: Communication guidelines loaded in every Claude session
#      - ai-initialize:  The /ai-initialize command used to set up projects
#      - ai-sync:        The /ai-sync command to update project skills from repo
#
#   2. Sets the AI_AGENT_ENV_PATH environment variable in your shell profile
#      so the /ai-initialize command knows where to find this repo's skills
#      and agents when copying them to a project.
#
# USAGE:
#   ./install.sh
#   source ~/.zshrc   # (or ~/.bashrc) to pick up the new env var
#
# AFTER INSTALL:
#   Open any project in Claude Code and run /ai-initialize to copy
#   skills and agents into that project's .claude/ directory.
#
# SAFE TO RE-RUN:
#   - Skills are overwritten with latest versions from the repo
#   - Environment variable is only added once (skipped if already present)
# =============================================================================

set -e  # Exit immediately if any command fails

# Resolve the absolute path to this repo, regardless of where the script is
# called from. This becomes the value of AI_AGENT_ENV_PATH.
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

# Claude Code looks for global skills in ~/.claude/skills/
# Each skill must be in a subdirectory with a SKILL.md file inside it.
SKILLS_DIR="$HOME/.claude/skills"

# Detect the user's shell profile for setting environment variables.
# Prefers zsh (macOS default), falls back to bash.
SHELL_RC="$HOME/.zshrc"
[ -f "$SHELL_RC" ] || SHELL_RC="$HOME/.bashrc"

echo "Installing from: $REPO_DIR"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Install global skills
# ---------------------------------------------------------------------------
# These are the only skills that live globally. All other skills (Python
# conventions, etc.) are copied per-project by the /ai-initialize command.

# ai-interaction: Basic communication guidelines and code review process.
# Has globs: ["**/*"] so it loads in every Claude Code session regardless
# of what files are open.
mkdir -p "$SKILLS_DIR/ai-interaction"
cp "$REPO_DIR/skills/ai-interaction.md" "$SKILLS_DIR/ai-interaction/SKILL.md"
echo "  Installed skill: ai-interaction"

# ai-initialize: The /ai-initialize command that users invoke to set up a
# project with skills and agents. Marked as user-invocable so it appears
# as a slash command in Claude Code.
mkdir -p "$SKILLS_DIR/ai-initialize"
cp "$REPO_DIR/commands/ai-initialize.md" "$SKILLS_DIR/ai-initialize/SKILL.md"
echo "  Installed skill: ai-initialize"

# ai-sync: The /ai-sync command that re-copies the latest skills and agents
# from this repo into a project's .claude/ directory. Use this after updating
# skills in the repo to push changes to active projects.
mkdir -p "$SKILLS_DIR/ai-sync"
cp "$REPO_DIR/commands/ai-sync.md" "$SKILLS_DIR/ai-sync/SKILL.md"
echo "  Installed skill: ai-sync"

# ---------------------------------------------------------------------------
# Step 2: Set up AI_AGENT_ENV_PATH environment variable
# ---------------------------------------------------------------------------
# The /ai-initialize command uses $AI_AGENT_ENV_PATH to locate this repo
# when copying skills and agents to a project. Without it, the command
# won't know where to find the source files.

if grep -q "AI_AGENT_ENV_PATH" "$SHELL_RC" 2>/dev/null; then
  # Already set — don't duplicate. User may need to update manually if
  # the repo moved to a different location.
  echo ""
  echo "  AI_AGENT_ENV_PATH already in $SHELL_RC (skipping)"
else
  # Append the export to the shell profile so it persists across sessions.
  echo "" >> "$SHELL_RC"
  echo "# AI Agent Environment — path to skills/agents repo" >> "$SHELL_RC"
  echo "export AI_AGENT_ENV_PATH=\"$REPO_DIR\"" >> "$SHELL_RC"
  echo ""
  echo "  Added AI_AGENT_ENV_PATH=$REPO_DIR to $SHELL_RC"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "Done. Restart your shell or run:"
echo "  source $SHELL_RC"
echo ""
echo "Then use /ai-initialize in any project to set up skills and agents."

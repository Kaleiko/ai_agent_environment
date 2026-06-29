"""Tests for the three bug fixes in pre_tool_use.py."""

import os
import sys

# Add the hooks directory to the path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))

import pre_tool_use


def test_tier1_rm_rf_blocks_root_deletion() -> None:
    """Tier 1 regex blocks rm -rf targeting the root filesystem.

    Args: None

    Returns: None
    """
    # These should all be blocked (catastrophic root-level deletion)
    dangerous_commands = [
        "rm -rf /",
        "rm -rf /*",
        "rm -rf / && echo done",
        "rm -rf /;",
        "rm -rf / | cat",
    ]
    for cmd in dangerous_commands:
        result = pre_tool_use.check_tier1(cmd)
        assert result is not None, f"Should block: {cmd}"


def test_tier1_rm_rf_allows_project_paths() -> None:
    """Tier 1 regex does NOT block rm -rf on legitimate subdirectory paths.

    Args: None

    Returns: None
    """
    # These should NOT be blocked by Tier 1 (legitimate project paths)
    safe_commands = [
        "rm -rf /Users/kaleiko/project/src/api/v1/books",
        "rm -rf /tmp/build",
        "rm -rf /var/folders/test_output",
    ]
    for cmd in safe_commands:
        result = pre_tool_use.check_tier1(cmd)
        assert result is None, f"Should NOT block: {cmd} (got: {result})"


def test_allowed_external_dirs_includes_ai_env() -> None:
    """AI_AGENT_ENV_PATH is added to allowed external dirs when set and valid.

    Args: None

    Returns: None
    """
    # The module-level check already ran at import time with the real env var.
    # Verify the current AI_AGENT_ENV_PATH is in the list if it's set.
    ai_env = os.environ.get("AI_AGENT_ENV_PATH")
    if ai_env and os.path.isdir(ai_env):
        assert ai_env in pre_tool_use.ALLOWED_EXTERNAL_DIRS, (
            f"AI_AGENT_ENV_PATH ({ai_env}) should be in ALLOWED_EXTERNAL_DIRS"
        )


def test_allowed_external_dirs_file_path_check() -> None:
    """File paths within AI_AGENT_ENV_PATH are allowed by is_in_allowed_external_dir.

    Args: None

    Returns: None
    """
    ai_env = os.environ.get("AI_AGENT_ENV_PATH")
    if not ai_env or not os.path.isdir(ai_env):
        return  # Skip if not configured

    test_path = os.path.join(ai_env, "skills", "python-conventions.md")
    resolved = os.path.realpath(test_path)
    assert pre_tool_use.is_in_allowed_external_dir(resolved, "/some/other/project"), (
        f"Path within AI_AGENT_ENV_PATH should be allowed: {test_path}"
    )


def test_check_env_allows_ls_commands() -> None:
    """check_env_in_command allows ls commands that reference .env files.

    Args: None

    Returns: None
    """
    # ls commands should be allowed (read-only, just listing)
    ls_commands = [
        "ls .env*",
        "ls -la .env",
        "ls .env.local",
        "/bin/ls .env",
    ]
    for cmd in ls_commands:
        result = pre_tool_use.check_env_in_command(cmd)
        assert result is None, f"ls command should be allowed: {cmd} (got: {result})"


def test_check_env_still_blocks_non_ls_commands() -> None:
    """check_env_in_command still blocks non-ls access to .env files.

    Args: None

    Returns: None
    """
    # These should still be blocked
    blocked_commands = [
        "cat .env",
        "source .env",
        "cp .env .env.bak",
    ]
    for cmd in blocked_commands:
        result = pre_tool_use.check_env_in_command(cmd)
        assert result is not None, f"Should block: {cmd}"


if __name__ == "__main__":
    test_tier1_rm_rf_blocks_root_deletion()
    print("PASS: test_tier1_rm_rf_blocks_root_deletion")

    test_tier1_rm_rf_allows_project_paths()
    print("PASS: test_tier1_rm_rf_allows_project_paths")

    test_allowed_external_dirs_includes_ai_env()
    print("PASS: test_allowed_external_dirs_includes_ai_env")

    test_allowed_external_dirs_file_path_check()
    print("PASS: test_allowed_external_dirs_file_path_check")

    test_check_env_allows_ls_commands()
    print("PASS: test_check_env_allows_ls_commands")

    test_check_env_still_blocks_non_ls_commands()
    print("PASS: test_check_env_still_blocks_non_ls_commands")

    print("\nAll tests passed!")

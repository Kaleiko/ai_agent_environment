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


def test_allowed_external_dirs_includes_repo_root() -> None:
    """The repo root (derived from __file__, not the env var) is an allowed dir.

    Args: None

    Returns: None
    """
    # REPO_ROOT is computed at import time from the hook's own location, so this
    # passes with AI_AGENT_ENV_PATH completely unset.
    repo_root = pre_tool_use.REPO_ROOT
    assert repo_root in pre_tool_use.ALLOWED_EXTERNAL_DIRS, (
        f"Repo root ({repo_root}) should be in ALLOWED_EXTERNAL_DIRS"
    )


def test_allowed_external_dirs_file_path_check() -> None:
    """File paths within the repo root are allowed by is_in_allowed_external_dir.

    Args: None

    Returns: None
    """
    repo_root = pre_tool_use.REPO_ROOT
    test_path = os.path.join(repo_root, "skills", "python-conventions.md")
    resolved = os.path.realpath(test_path)
    assert pre_tool_use.is_in_allowed_external_dir(resolved, "/some/other/project"), (
        f"Path within the repo root should be allowed: {test_path}"
    )


def test_symlinked_repo_path_treated_as_inside_repo(tmp_path) -> None:
    """A file reached via a symlink to the repo is recognized as inside the repo.

    Guards the physical-path (realpath) consistency fix: when the repo is reached
    through a symlink (e.g. ~/Dropbox -> ~/Library/CloudStorage/Dropbox), a path
    resolved through the symlink must still match the physical REPO_ROOT.

    Args:
        tmp_path: Pytest-provided temporary directory.

    Returns: None
    """
    repo_root = pre_tool_use.REPO_ROOT
    link = tmp_path / "repo_link"
    link.symlink_to(repo_root)

    # Access a real repo file through the symlinked path.
    symlinked_file = str(link / "skills" / "python-conventions.md")
    resolved = pre_tool_use.resolve_path(symlinked_file, str(tmp_path))
    assert pre_tool_use.is_in_allowed_external_dir(resolved, "/some/other/project"), (
        f"Symlinked repo path should resolve to inside the repo: {symlinked_file}"
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

    test_allowed_external_dirs_includes_repo_root()
    print("PASS: test_allowed_external_dirs_includes_repo_root")

    test_allowed_external_dirs_file_path_check()
    print("PASS: test_allowed_external_dirs_file_path_check")

    test_check_env_allows_ls_commands()
    print("PASS: test_check_env_allows_ls_commands")

    test_check_env_still_blocks_non_ls_commands()
    print("PASS: test_check_env_still_blocks_non_ls_commands")

    print("\nAll tests passed!")

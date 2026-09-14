"""Regression tests for two hook defects.

Fix 1: hook log directories are anchored to a stable project root
(CLAUDE_PROJECT_DIR) instead of the tool's live cwd, so a `cd` into a
subdirectory no longer scatters logs into that subdirectory.

Fix 2: pre_tool_use.py fails CLOSED — a broken/unwritable log directory or a
crash inside the security logic can never suppress a Tier-1 block.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks directory to path so we can import the hook modules.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

import hook_paths
import pre_tool_use

CLAUDE_PROJECT_DIR_ENV = "CLAUDE_PROJECT_DIR"


# ---------------------------------------------------------------------------
# Fix 1: get_project_root resolution order
# ---------------------------------------------------------------------------


class TestGetProjectRoot:
    """Tests for hook_paths.get_project_root resolution order."""

    def test_prefers_claude_project_dir_over_cwd(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """CLAUDE_PROJECT_DIR wins even when the payload carries a different cwd."""
        root = tmp_path / "root"
        monkeypatch.setenv(CLAUDE_PROJECT_DIR_ENV, str(root))
        payload = {"cwd": str(tmp_path / "sub")}
        assert hook_paths.get_project_root(payload) == str(root)

    def test_blank_env_is_ignored(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A whitespace-only CLAUDE_PROJECT_DIR is treated as unset."""
        monkeypatch.setenv(CLAUDE_PROJECT_DIR_ENV, "   ")
        payload = {"cwd": str(tmp_path)}
        assert hook_paths.get_project_root(payload) == str(tmp_path)

    def test_falls_back_to_payload_cwd(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """With no env var, the payload cwd is used."""
        monkeypatch.delenv(CLAUDE_PROJECT_DIR_ENV, raising=False)
        payload = {"cwd": str(tmp_path)}
        assert hook_paths.get_project_root(payload) == str(tmp_path)

    def test_falls_back_to_getcwd(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With neither env var nor payload cwd, os.getcwd() is the last resort."""
        monkeypatch.delenv(CLAUDE_PROJECT_DIR_ENV, raising=False)
        assert hook_paths.get_project_root({}) == os.getcwd()


# ---------------------------------------------------------------------------
# Fix 1: pre_tool_use audit log lands under the project root, not the cwd
# ---------------------------------------------------------------------------


class TestAuditLogAnchoredToProjectRoot:
    """Tests that audit logs follow the project root, not a subdirectory cwd."""

    def test_audit_lands_under_project_root_not_subdir(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A tool cwd inside a subdirectory still logs under the project root."""
        project_root = tmp_path / "project"
        subdir = project_root / "hooks"
        subdir.mkdir(parents=True)
        monkeypatch.setenv(CLAUDE_PROJECT_DIR_ENV, str(project_root))

        payload = json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "echo hi"},  # benign, not blocked
                "cwd": str(subdir),  # tool has cd'd into a subdirectory
            }
        )
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = payload
            pre_tool_use.main()

        root_log = project_root / ".claude" / "logs" / "audit" / "pre_tool_use.jsonl"
        subdir_log = subdir / ".claude" / "logs" / "audit" / "pre_tool_use.jsonl"
        assert root_log.is_file(), "audit log should be written under the project root"
        assert not subdir_log.exists(), (
            "audit log must NOT be created under the subdirectory cwd"
        )


# ---------------------------------------------------------------------------
# Fix 2: pre_tool_use fails closed — logging failures never suppress a block
# ---------------------------------------------------------------------------


class TestFailClosed:
    """Tests that a Tier-1 block survives broken logging and security crashes."""

    def test_unwritable_audit_dir_does_not_suppress_tier1_block(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """An unwritable audit directory must not stop an rm -rf / block."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        # Make .claude a FILE so the audit dir mkdir(parents=True) raises.
        (project_root / ".claude").write_text("not a directory")
        monkeypatch.setenv(CLAUDE_PROJECT_DIR_ENV, str(project_root))

        payload = json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "rm -rf /"},
                "cwd": str(project_root),
            }
        )
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = payload
            pre_tool_use.main()

        out = capsys.readouterr().out
        assert out.strip(), "a deny must be printed even when logging is broken"
        result = json.loads(out)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert (
            "catastrophic" in result["hookSpecificOutput"]["permissionDecisionReason"]
        )

    def test_blocked_log_failure_does_not_suppress_deny(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A crash while writing the blocked-log must not suppress the deny."""
        audit_dir = tmp_path / ".claude" / "logs" / "audit"
        audit_dir.mkdir(parents=True)
        monkeypatch.setenv(CLAUDE_PROJECT_DIR_ENV, str(tmp_path))

        def boom(*args: object, **kwargs: object) -> None:
            raise OSError("simulated disk full")

        monkeypatch.setattr(pre_tool_use, "log_blocked", boom)

        payload = json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "rm -rf /"},
                "cwd": str(tmp_path),
            }
        )
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = payload
            pre_tool_use.main()

        out = capsys.readouterr().out
        result = json.loads(out)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_security_check_crash_fails_closed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """An unexpected exception in the security logic blocks the call."""
        audit_dir = tmp_path / ".claude" / "logs" / "audit"
        audit_dir.mkdir(parents=True)
        monkeypatch.setenv(CLAUDE_PROJECT_DIR_ENV, str(tmp_path))

        def boom(*args: object, **kwargs: object) -> None:
            raise RuntimeError("simulated bug in checker")

        # check_env_in_command runs first inside evaluate_security.
        monkeypatch.setattr(pre_tool_use, "check_env_in_command", boom)

        payload = json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},  # otherwise benign
                "cwd": str(tmp_path),
            }
        )
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = payload
            pre_tool_use.main()

        out = capsys.readouterr().out
        result = json.loads(out)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert (
            "failing closed" in result["hookSpecificOutput"]["permissionDecisionReason"]
        )

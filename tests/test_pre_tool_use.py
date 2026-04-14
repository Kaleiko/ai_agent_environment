"""Tests for pre_tool_use hook — full_log.md blocking."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks directory to path so we can import pre_tool_use
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

import pre_tool_use


# ---------------------------------------------------------------------------
# is_full_log_file
# ---------------------------------------------------------------------------


class TestIsFullLogFile:
    """Tests for is_full_log_file."""

    def test_exact_filename(self) -> None:
        """Detects full_log.md as the basename."""
        assert pre_tool_use.is_full_log_file("full_log.md") is True

    def test_absolute_path(self) -> None:
        """Detects full_log.md in an absolute path."""
        assert (
            pre_tool_use.is_full_log_file("/project/.claude/logs/full_log.md") is True
        )

    def test_relative_path(self) -> None:
        """Detects full_log.md in a relative path."""
        assert pre_tool_use.is_full_log_file(".claude/logs/full_log.md") is True

    def test_different_filename(self) -> None:
        """Does not flag unrelated filenames."""
        assert pre_tool_use.is_full_log_file("last_session.md") is False

    def test_similar_but_different_name(self) -> None:
        """Does not flag files with similar but different names."""
        assert pre_tool_use.is_full_log_file("full_log_backup.md") is False

    def test_substring_in_directory_name(self) -> None:
        """Flags when full_log.md appears as a path component (contains check)."""
        assert pre_tool_use.is_full_log_file("/some/full_log.md/extra") is True


# ---------------------------------------------------------------------------
# check_file_path_tool — full_log blocking
# ---------------------------------------------------------------------------


class TestCheckFilePathToolFullLog:
    """Tests for check_file_path_tool blocking Read of full_log.md."""

    def test_read_full_log_blocked(self) -> None:
        """Read tool targeting full_log.md is blocked."""
        reason = pre_tool_use.check_file_path_tool(
            "Read",
            {"file_path": "/project/.claude/logs/full_log.md"},
            "/project",
        )
        assert reason is not None
        assert "full_log.md" in reason
        assert "prohibited" in reason

    def test_read_full_log_blocked_relative_path(self) -> None:
        """Read tool with relative path to full_log.md is blocked."""
        reason = pre_tool_use.check_file_path_tool(
            "Read",
            {"file_path": ".claude/logs/full_log.md"},
            "/project",
        )
        assert reason is not None
        assert "prohibited" in reason

    def test_write_full_log_not_blocked(self) -> None:
        """Write tool targeting full_log.md is NOT blocked (only Read is)."""
        reason = pre_tool_use.check_file_path_tool(
            "Write",
            {"file_path": "/project/.claude/logs/full_log.md"},
            "/project",
        )
        # Should not be blocked by the full_log rule (may be blocked by CWD check, but not by full_log)
        if reason:
            assert "full_log.md" not in reason

    def test_edit_full_log_not_blocked(self) -> None:
        """Edit tool targeting full_log.md is NOT blocked by the full_log rule."""
        reason = pre_tool_use.check_file_path_tool(
            "Edit",
            {"file_path": "/project/.claude/logs/full_log.md"},
            "/project",
        )
        if reason:
            assert "full_log.md" not in reason

    def test_read_other_file_not_blocked(self) -> None:
        """Read tool targeting a non-full_log file is not blocked by this rule."""
        reason = pre_tool_use.check_file_path_tool(
            "Read",
            {"file_path": "/project/src/main.py"},
            "/project",
        )
        assert reason is None

    def test_read_last_session_not_blocked(self) -> None:
        """Read tool targeting last_session.md is not blocked."""
        reason = pre_tool_use.check_file_path_tool(
            "Read",
            {"file_path": "/project/.claude/logs/last_session.md"},
            "/project",
        )
        assert reason is None


# ---------------------------------------------------------------------------
# main() integration — full_log blocking via deny JSON
# ---------------------------------------------------------------------------


class TestMainFullLogBlocking:
    """Tests for main() producing deny output when Read targets full_log.md."""

    def test_main_denies_read_full_log(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """main() prints deny JSON when Read targets full_log.md."""
        cwd = str(tmp_path)
        # Create the audit directory so logging doesn't fail
        audit_dir = tmp_path / ".claude" / "logs" / "audit"
        audit_dir.mkdir(parents=True)

        payload = json.dumps(
            {
                "tool_name": "Read",
                "tool_input": {"file_path": f"{cwd}/.claude/logs/full_log.md"},
                "cwd": cwd,
            }
        )

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = payload
            pre_tool_use.main()

        output = capsys.readouterr().out
        assert output.strip()  # Something was printed
        result = json.loads(output)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "full_log.md" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_main_allows_read_other_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """main() does not print deny JSON for a normal Read within CWD."""
        cwd = str(tmp_path)
        audit_dir = tmp_path / ".claude" / "logs" / "audit"
        audit_dir.mkdir(parents=True)

        payload = json.dumps(
            {
                "tool_name": "Read",
                "tool_input": {"file_path": f"{cwd}/src/main.py"},
                "cwd": cwd,
            }
        )

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = payload
            pre_tool_use.main()

        output = capsys.readouterr().out
        assert output.strip() == ""  # No deny output

    def test_main_allows_write_full_log(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """main() does not block Write to full_log.md."""
        cwd = str(tmp_path)
        audit_dir = tmp_path / ".claude" / "logs" / "audit"
        audit_dir.mkdir(parents=True)

        payload = json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": f"{cwd}/.claude/logs/full_log.md"},
                "cwd": cwd,
            }
        )

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = payload
            pre_tool_use.main()

        output = capsys.readouterr().out
        assert output.strip() == ""  # No deny output

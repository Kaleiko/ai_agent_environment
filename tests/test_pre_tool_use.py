"""Tests for pre_tool_use hook — security validations."""

import json
import os
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


# ---------------------------------------------------------------------------
# Bug Fix 1: Project's own .claude/ directory allowed
# ---------------------------------------------------------------------------


class TestProjectClaudeDirectoryAllowed:
    """Tests that {CWD}/.claude/ is allowed even when CWD != ~/.claude/."""

    def test_write_to_project_claude_skills(self, tmp_path: Path) -> None:
        """Write to {CWD}/.claude/skills/ should not be blocked."""
        cwd = str(tmp_path)
        reason = pre_tool_use.check_file_path_tool(
            "Write",
            {"file_path": f"{cwd}/.claude/skills/my-skill.md"},
            cwd,
        )
        assert reason is None

    def test_write_to_project_claude_logs(self, tmp_path: Path) -> None:
        """Write to {CWD}/.claude/logs/ should not be blocked."""
        cwd = str(tmp_path)
        reason = pre_tool_use.check_file_path_tool(
            "Write",
            {"file_path": f"{cwd}/.claude/logs/audit/test.jsonl"},
            cwd,
        )
        assert reason is None

    def test_read_from_project_claude_settings(self, tmp_path: Path) -> None:
        """Read from {CWD}/.claude/settings.json should not be blocked."""
        cwd = str(tmp_path)
        reason = pre_tool_use.check_file_path_tool(
            "Read",
            {"file_path": f"{cwd}/.claude/settings.json"},
            cwd,
        )
        assert reason is None

    def test_write_to_home_claude_still_allowed(self) -> None:
        """Write to ~/.claude/ should still be allowed (existing behavior)."""
        home_claude = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
        reason = pre_tool_use.check_file_path_tool(
            "Write",
            {"file_path": home_claude},
            "/some/other/project",
        )
        assert reason is None

    def test_write_outside_both_claude_dirs_blocked(self, tmp_path: Path) -> None:
        """Write to a path outside both CWD and allowed dirs is still blocked."""
        cwd = str(tmp_path)
        reason = pre_tool_use.check_file_path_tool(
            "Write",
            {"file_path": "/etc/passwd"},
            cwd,
        )
        assert reason is not None
        assert "outside project directory" in reason

    def test_get_allowed_external_dirs_includes_cwd_claude(self) -> None:
        """get_allowed_external_dirs includes {CWD}/.claude/."""
        cwd = "/Users/test/project"
        dirs = pre_tool_use.get_allowed_external_dirs(cwd)
        assert os.path.join(cwd, ".claude") in dirs

    def test_get_allowed_external_dirs_includes_home_claude(self) -> None:
        """get_allowed_external_dirs includes ~/.claude/."""
        dirs = pre_tool_use.get_allowed_external_dirs("/some/cwd")
        home_claude = os.path.join(os.path.expanduser("~"), ".claude")
        assert home_claude in dirs


# ---------------------------------------------------------------------------
# Bug Fix 2: .env regex false positives in Bash commands
# ---------------------------------------------------------------------------


class TestCheckEnvInCommand:
    """Tests for check_env_in_command — no false positives on quoted/heredoc content."""

    def test_direct_cat_env_blocked(self) -> None:
        """Direct `cat .env` is blocked."""
        assert pre_tool_use.check_env_in_command("cat .env") is not None

    def test_source_env_blocked(self) -> None:
        """source .env is blocked."""
        assert pre_tool_use.check_env_in_command("source .env") is not None

    def test_cp_env_blocked(self) -> None:
        """cp .env .env.bak is blocked."""
        assert pre_tool_use.check_env_in_command("cp .env .env.bak") is not None

    def test_path_with_env_blocked(self) -> None:
        """cat /path/to/.env is blocked."""
        assert pre_tool_use.check_env_in_command("cat /path/to/.env") is not None

    def test_dot_slash_env_blocked(self) -> None:
        """./.env access is blocked."""
        assert pre_tool_use.check_env_in_command("cat ./.env") is not None

    def test_env_local_blocked(self) -> None:
        """.env.local is blocked (not a safe suffix)."""
        assert pre_tool_use.check_env_in_command("cat .env.local") is not None

    def test_env_sample_allowed(self) -> None:
        """.env.sample is allowed."""
        assert pre_tool_use.check_env_in_command("cat .env.sample") is None

    def test_env_example_allowed(self) -> None:
        """.env.example is allowed."""
        assert pre_tool_use.check_env_in_command("cat .env.example") is None

    def test_env_template_allowed(self) -> None:
        """.env.template is allowed."""
        assert pre_tool_use.check_env_in_command("cat .env.template") is None

    def test_env_in_single_quoted_string_allowed(self) -> None:
        """'.env' inside single quotes (echo content) is allowed."""
        cmd = "echo 'Add your secrets to .env file'"
        assert pre_tool_use.check_env_in_command(cmd) is None

    def test_env_in_double_quoted_string_allowed(self) -> None:
        """'.env' inside double quotes (echo content) is allowed."""
        cmd = 'echo "Remember to create a .env file"'
        assert pre_tool_use.check_env_in_command(cmd) is None

    def test_env_in_heredoc_allowed(self) -> None:
        """'.env' inside a heredoc body is allowed."""
        cmd = "cat <<EOF\nAdd .env to .gitignore\nEOF"
        assert pre_tool_use.check_env_in_command(cmd) is None

    def test_env_in_heredoc_with_quotes_allowed(self) -> None:
        """'.env' inside a quoted heredoc body is allowed."""
        cmd = "cat <<'EOF'\nMake sure .env is in .gitignore\nEOF"
        assert pre_tool_use.check_env_in_command(cmd) is None

    def test_echo_with_env_mention_allowed(self) -> None:
        """echo mentioning .env in quoted text is allowed."""
        cmd = """printf "# .env\\nDATABASE_URL=postgres://..." > .env.example"""
        assert pre_tool_use.check_env_in_command(cmd) is None

    def test_no_env_at_all_allowed(self) -> None:
        """Command with no .env reference is allowed."""
        assert pre_tool_use.check_env_in_command("ls -la") is None

    def test_environment_word_not_blocked(self) -> None:
        """The word 'environment' should not trigger the block."""
        assert pre_tool_use.check_env_in_command("echo environment") is None


# ---------------------------------------------------------------------------
# Bug Fix 3: Read blocked on files within CWD (symlink resolution)
# ---------------------------------------------------------------------------


class TestSymlinkResolution:
    """Tests for resolve_path and is_within_cwd handling symlinks."""

    def test_read_subdirectory_file_allowed(self, tmp_path: Path) -> None:
        """Reading a file in a subdirectory of CWD should be allowed."""
        sub_dir = tmp_path / "frontend"
        sub_dir.mkdir()
        gitignore = sub_dir / ".gitignore"
        gitignore.write_text("node_modules/\n")

        cwd = str(tmp_path)
        reason = pre_tool_use.check_file_path_tool(
            "Read",
            {"file_path": str(gitignore)},
            cwd,
        )
        assert reason is None

    def test_read_via_symlinked_cwd(self, tmp_path: Path) -> None:
        """Reading a file works when CWD is accessed via a symlink."""
        real_dir = tmp_path / "real_project"
        real_dir.mkdir()
        test_file = real_dir / "main.py"
        test_file.write_text("print('hello')\n")

        symlink_dir = tmp_path / "link_project"
        symlink_dir.symlink_to(real_dir)

        # CWD is the symlink path, file_path uses the symlink path
        cwd = str(symlink_dir)
        reason = pre_tool_use.check_file_path_tool(
            "Read",
            {"file_path": f"{cwd}/main.py"},
            cwd,
        )
        assert reason is None

    def test_read_real_path_with_symlink_cwd(self, tmp_path: Path) -> None:
        """Reading real path when CWD is a symlink should work."""
        real_dir = tmp_path / "real_project"
        real_dir.mkdir()
        test_file = real_dir / "src" / "app.py"
        test_file.parent.mkdir()
        test_file.write_text("# app\n")

        symlink_dir = tmp_path / "link_project"
        symlink_dir.symlink_to(real_dir)

        # CWD is symlink, but file_path resolves to real path
        cwd = str(symlink_dir)
        reason = pre_tool_use.check_file_path_tool(
            "Read",
            {"file_path": str(test_file)},  # real path
            cwd,
        )
        assert reason is None

    def test_read_symlink_path_with_real_cwd(self, tmp_path: Path) -> None:
        """Reading via symlink path when CWD is the real path should work."""
        real_dir = tmp_path / "real_project"
        real_dir.mkdir()
        test_file = real_dir / "config.py"
        test_file.write_text("# config\n")

        symlink_dir = tmp_path / "link_project"
        symlink_dir.symlink_to(real_dir)

        # CWD is real path, file uses symlink
        cwd = str(real_dir)
        reason = pre_tool_use.check_file_path_tool(
            "Read",
            {"file_path": f"{symlink_dir}/config.py"},
            cwd,
        )
        assert reason is None

    def test_resolve_path_resolves_symlinks(self, tmp_path: Path) -> None:
        """resolve_path should resolve symlinks to the real path."""
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        link_dir = tmp_path / "link"
        link_dir.symlink_to(real_dir)

        resolved = pre_tool_use.resolve_path("link/file.py", str(tmp_path))
        expected = os.path.realpath(str(real_dir / "file.py"))
        assert resolved == expected

    def test_is_within_cwd_with_symlinks(self, tmp_path: Path) -> None:
        """is_within_cwd should handle symlinked paths correctly."""
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        link_dir = tmp_path / "link"
        link_dir.symlink_to(real_dir)

        real_file = str(real_dir / "test.py")
        # CWD is the symlink, file is the real path — should still be within CWD
        assert pre_tool_use.is_within_cwd(real_file, str(link_dir)) is True

    def test_file_outside_cwd_still_blocked(self, tmp_path: Path) -> None:
        """Files genuinely outside CWD are still blocked."""
        cwd = str(tmp_path / "project")
        reason = pre_tool_use.check_file_path_tool(
            "Read",
            {"file_path": "/etc/hosts"},
            cwd,
        )
        assert reason is not None
        assert "outside project directory" in reason

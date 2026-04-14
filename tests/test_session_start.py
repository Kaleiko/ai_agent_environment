"""Tests for session_start hook — archive, cleanup, and context injection."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks directory to path so we can import session_start
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

import session_start


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def logs_dir(tmp_path: Path) -> Path:
    """Create a temporary .claude/logs directory.

    Args:
        tmp_path: Pytest-provided temporary directory.

    Returns:
        Path to the logs directory.
    """
    d = tmp_path / ".claude" / "logs"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def sessions_dir(logs_dir: Path) -> Path:
    """Create a temporary sessions directory inside logs.

    Args:
        logs_dir: The logs directory fixture.

    Returns:
        Path to the sessions directory.
    """
    d = logs_dir / "sessions"
    d.mkdir(parents=True)
    return d


# ---------------------------------------------------------------------------
# enforce_max_size_text
# ---------------------------------------------------------------------------


class TestEnforceMaxSizeText:
    """Tests for enforce_max_size_text."""

    def test_no_op_when_file_does_not_exist(self, tmp_path: Path) -> None:
        """Does nothing when the file does not exist."""
        nonexistent = tmp_path / "missing.log"
        session_start.enforce_max_size_text(nonexistent)
        assert not nonexistent.exists()

    def test_no_op_when_file_is_under_limit(self, tmp_path: Path) -> None:
        """Does not modify a file smaller than MAX_LOG_BYTES."""
        small_file = tmp_path / "small.log"
        content = "short line\n"
        small_file.write_text(content)
        session_start.enforce_max_size_text(small_file)
        assert small_file.read_text() == content

    def test_trims_file_over_limit(self, tmp_path: Path) -> None:
        """Trims file to approximately MAX_LOG_BYTES when it exceeds the limit."""
        log_file = tmp_path / "big.log"
        # Write content exceeding MAX_LOG_BYTES
        line = "x" * 200 + "\n"
        num_lines = (session_start.MAX_LOG_BYTES // len(line)) + 100
        log_file.write_text(line * num_lines)

        original_size = log_file.stat().st_size
        assert original_size > session_start.MAX_LOG_BYTES

        session_start.enforce_max_size_text(log_file)

        trimmed_size = log_file.stat().st_size
        assert trimmed_size <= session_start.MAX_LOG_BYTES


# ---------------------------------------------------------------------------
# truncate_content
# ---------------------------------------------------------------------------


class TestTruncateContent:
    """Tests for truncate_content."""

    def test_returns_content_unchanged_when_under_limit(self) -> None:
        """Content shorter than max_chars is returned as-is."""
        content = "short content"
        result = session_start.truncate_content(content, 1000)
        assert result == content

    def test_truncates_to_tail(self) -> None:
        """Content exceeding max_chars is truncated from the beginning."""
        content = "A" * 100 + "\n## Header\nrecent text"
        result = session_start.truncate_content(content, 30)
        assert "recent text" in result
        assert len(result) <= 30

    def test_snaps_to_section_header(self) -> None:
        """Truncation snaps to the first complete section header."""
        content = "old stuff\n## Section One\ndata one\n## Section Two\ndata two"
        result = session_start.truncate_content(content, 40)
        assert result.startswith("## ")

    def test_returns_content_when_exactly_at_limit(self) -> None:
        """Content exactly at max_chars is returned unchanged."""
        content = "x" * 50
        result = session_start.truncate_content(content, 50)
        assert result == content


# ---------------------------------------------------------------------------
# archive_last_session
# ---------------------------------------------------------------------------


class TestArchiveLastSession:
    """Tests for archive_last_session."""

    def test_no_op_when_last_session_missing(self, logs_dir: Path) -> None:
        """Does nothing when last_session.md does not exist."""
        session_start.archive_last_session(logs_dir)
        sessions_dir = logs_dir / "sessions"
        assert not sessions_dir.exists()

    def test_no_op_when_last_session_empty(self, logs_dir: Path) -> None:
        """Does nothing when last_session.md is empty."""
        last_session = logs_dir / "last_session.md"
        last_session.write_text("")
        session_start.archive_last_session(logs_dir)
        sessions_dir = logs_dir / "sessions"
        assert not sessions_dir.exists()

    def test_no_op_when_last_session_whitespace_only(self, logs_dir: Path) -> None:
        """Does nothing when last_session.md contains only whitespace."""
        last_session = logs_dir / "last_session.md"
        last_session.write_text("   \n\n  ")
        session_start.archive_last_session(logs_dir)
        sessions_dir = logs_dir / "sessions"
        assert not sessions_dir.exists()

    def test_archives_content_to_sessions_dir(self, logs_dir: Path) -> None:
        """Copies last_session.md content to a timestamped file in sessions/."""
        last_session = logs_dir / "last_session.md"
        last_session.write_text("## User\nHello\n\n## Assistant\nWorld")

        session_start.archive_last_session(logs_dir)

        sessions_dir = logs_dir / "sessions"
        assert sessions_dir.is_dir()
        session_files = list(sessions_dir.glob("*_session.md"))
        assert len(session_files) == 1
        assert session_files[0].read_text() == "## User\nHello\n\n## Assistant\nWorld"

    def test_does_not_clear_last_session_after_archive(self, logs_dir: Path) -> None:
        """last_session.md retains its content after archiving (crash-recovery safety).

        The session_stop hook overwrites last_session.md on every assistant turn,
        so clearing it here is unnecessary and causes data loss if a session crashes
        before the first complete turn.
        """
        last_session = logs_dir / "last_session.md"
        original_content = "## User\nImportant context\n\n## Assistant\nKey response"
        last_session.write_text(original_content)

        session_start.archive_last_session(logs_dir)

        # last_session.md must NOT be cleared
        assert last_session.read_text() == original_content

    def test_creates_sessions_dir_if_missing(self, logs_dir: Path) -> None:
        """Creates the sessions/ directory if it does not exist."""
        last_session = logs_dir / "last_session.md"
        last_session.write_text("some content")

        sessions_dir = logs_dir / "sessions"
        assert not sessions_dir.exists()

        session_start.archive_last_session(logs_dir)
        assert sessions_dir.is_dir()

    def test_archived_filename_has_timestamp_format(self, logs_dir: Path) -> None:
        """Archived file uses ISO-like timestamp in its name."""
        last_session = logs_dir / "last_session.md"
        last_session.write_text("content")

        fixed_time = datetime(2026, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
        with patch("session_start.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_time
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            session_start.archive_last_session(logs_dir)

        sessions_dir = logs_dir / "sessions"
        session_files = list(sessions_dir.glob("*_session.md"))
        assert len(session_files) == 1
        assert session_files[0].name == "2026-01-15T10-30-45_session.md"


# ---------------------------------------------------------------------------
# cleanup_old_sessions
# ---------------------------------------------------------------------------


class TestCleanupOldSessions:
    """Tests for cleanup_old_sessions."""

    def test_no_op_when_dir_missing(self, tmp_path: Path) -> None:
        """Does nothing when sessions directory does not exist."""
        session_start.cleanup_old_sessions(tmp_path / "nonexistent")

    def test_no_op_when_under_limit(self, sessions_dir: Path) -> None:
        """Does not delete files when count is at or below MAX_SESSIONS_TO_KEEP."""
        (sessions_dir / "2026-01-01T00-00-00_session.md").write_text("a")
        (sessions_dir / "2026-01-02T00-00-00_session.md").write_text("b")

        session_start.cleanup_old_sessions(sessions_dir)

        files = list(sessions_dir.glob("*_session.md"))
        assert len(files) == 2

    def test_deletes_oldest_files_over_limit(self, sessions_dir: Path) -> None:
        """Deletes oldest files when count exceeds MAX_SESSIONS_TO_KEEP."""
        (sessions_dir / "2026-01-01T00-00-00_session.md").write_text("oldest")
        (sessions_dir / "2026-01-02T00-00-00_session.md").write_text("middle")
        (sessions_dir / "2026-01-03T00-00-00_session.md").write_text("newest")

        session_start.cleanup_old_sessions(sessions_dir)

        files = sorted(sessions_dir.glob("*_session.md"))
        assert len(files) == session_start.MAX_SESSIONS_TO_KEEP
        # The oldest file should be gone
        remaining_names = [f.name for f in files]
        assert "2026-01-01T00-00-00_session.md" not in remaining_names
        assert "2026-01-02T00-00-00_session.md" in remaining_names
        assert "2026-01-03T00-00-00_session.md" in remaining_names


# ---------------------------------------------------------------------------
# get_session_context
# ---------------------------------------------------------------------------


class TestGetSessionContext:
    """Tests for get_session_context."""

    def test_returns_empty_when_dir_missing(self, tmp_path: Path) -> None:
        """Returns empty string when sessions directory does not exist."""
        result = session_start.get_session_context(tmp_path / "nonexistent")
        assert result == ""

    def test_returns_empty_when_no_sessions(self, sessions_dir: Path) -> None:
        """Returns empty string when sessions directory has no session files."""
        result = session_start.get_session_context(sessions_dir)
        assert result == ""

    def test_returns_most_recent_session(self, sessions_dir: Path) -> None:
        """Returns content from the most recent session file."""
        (sessions_dir / "2026-01-01T00-00-00_session.md").write_text("session one")
        result = session_start.get_session_context(sessions_dir)
        assert "### Most Recent Session" in result
        assert "session one" in result

    def test_returns_both_sessions_when_two_exist(self, sessions_dir: Path) -> None:
        """Returns content from both sessions when two are available."""
        (sessions_dir / "2026-01-01T00-00-00_session.md").write_text("older session")
        (sessions_dir / "2026-01-02T00-00-00_session.md").write_text("newer session")

        result = session_start.get_session_context(sessions_dir)
        assert "### Most Recent Session" in result
        assert "newer session" in result
        assert "### Earlier Session" in result
        assert "older session" in result

    def test_skips_empty_session_files(self, sessions_dir: Path) -> None:
        """Skips session files that are empty or whitespace-only."""
        (sessions_dir / "2026-01-01T00-00-00_session.md").write_text("   ")
        (sessions_dir / "2026-01-02T00-00-00_session.md").write_text("valid content")

        result = session_start.get_session_context(sessions_dir)
        assert "### Most Recent Session" in result
        assert "valid content" in result
        assert "### Earlier Session" not in result


# ---------------------------------------------------------------------------
# get_active_plans
# ---------------------------------------------------------------------------


class TestGetActivePlans:
    """Tests for get_active_plans."""

    def test_returns_empty_when_no_plans_dir(self, tmp_path: Path) -> None:
        """Returns empty string when .claude/plans/ does not exist."""
        result = session_start.get_active_plans(str(tmp_path))
        assert result == ""

    def test_returns_empty_when_plans_dir_empty(self, tmp_path: Path) -> None:
        """Returns empty string when .claude/plans/ has no .md files."""
        plans_dir = tmp_path / ".claude" / "plans"
        plans_dir.mkdir(parents=True)
        result = session_start.get_active_plans(str(tmp_path))
        assert result == ""

    def test_lists_plan_files(self, tmp_path: Path) -> None:
        """Lists all .md files in .claude/plans/."""
        plans_dir = tmp_path / ".claude" / "plans"
        plans_dir.mkdir(parents=True)
        (plans_dir / "PHASE1_PLAN.md").write_text("plan content")
        (plans_dir / "ARCHITECTURE_PLAN.md").write_text("arch content")

        result = session_start.get_active_plans(str(tmp_path))
        assert "### Active Plans" in result
        assert "PHASE1_PLAN.md" in result
        assert "ARCHITECTURE_PLAN.md" in result
        assert "Review these plans" in result


# ---------------------------------------------------------------------------
# main() integration
# ---------------------------------------------------------------------------


class TestMainIntegration:
    """Tests for main() end-to-end behavior."""

    def _build_payload(self, cwd: str, source: str = "startup") -> str:
        """Build a JSON payload string mimicking the hook input.

        Args:
            cwd: Working directory.
            source: The source event type.

        Returns:
            JSON string payload.
        """
        return json.dumps(
            {
                "session_id": "test-session",
                "source": source,
                "cwd": cwd,
            }
        )

    def test_skips_injection_on_resume(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Does not inject context when source is 'resume'."""
        cwd = str(tmp_path)
        payload = self._build_payload(cwd, source="resume")

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = payload
            session_start.main()

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_skips_injection_on_compact(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Does not inject context when source is 'compact'."""
        cwd = str(tmp_path)
        payload = self._build_payload(cwd, source="compact")

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = payload
            session_start.main()

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_injects_context_on_startup(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Injects previous session context when source is 'startup'."""
        cwd = str(tmp_path)
        logs_dir = tmp_path / ".claude" / "logs"
        sessions_dir = logs_dir / "sessions"
        sessions_dir.mkdir(parents=True)

        (sessions_dir / "2026-01-01T00-00-00_session.md").write_text(
            "## User\nPrevious question\n\n## Assistant\nPrevious answer"
        )

        payload = self._build_payload(cwd, source="startup")

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = payload
            session_start.main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        context = output["hookSpecificOutput"]["additionalContext"]
        assert "Previous question" in context
        assert "Previous answer" in context

    def test_archives_last_session_on_startup(self, tmp_path: Path) -> None:
        """Archives last_session.md into sessions/ on startup."""
        cwd = str(tmp_path)
        logs_dir = tmp_path / ".claude" / "logs"
        logs_dir.mkdir(parents=True)
        last_session = logs_dir / "last_session.md"
        last_session.write_text("## User\nArchive me")

        payload = self._build_payload(cwd, source="startup")

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = payload
            session_start.main()

        sessions_dir = logs_dir / "sessions"
        session_files = list(sessions_dir.glob("*_session.md"))
        assert len(session_files) == 1
        assert "Archive me" in session_files[0].read_text()

    def test_last_session_preserved_after_startup_archive(self, tmp_path: Path) -> None:
        """last_session.md is NOT cleared after archiving on startup (crash-recovery safety)."""
        cwd = str(tmp_path)
        logs_dir = tmp_path / ".claude" / "logs"
        logs_dir.mkdir(parents=True)
        last_session = logs_dir / "last_session.md"
        original_content = "## User\nCrash recovery data"
        last_session.write_text(original_content)

        payload = self._build_payload(cwd, source="startup")

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = payload
            session_start.main()

        # last_session.md must retain its content
        assert last_session.read_text() == original_content

    def test_handles_invalid_json_gracefully(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Does not crash on invalid JSON input."""
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = "not valid json"
            session_start.main()

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_no_output_when_no_context(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Produces no output when there is no session context or plans."""
        cwd = str(tmp_path)
        payload = self._build_payload(cwd, source="startup")

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = payload
            session_start.main()

        captured = capsys.readouterr()
        assert captured.out == ""

"""Tests for session_stop hook — full_log feature and resilience."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks directory to path so we can import session_stop
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

import session_stop


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
def transcript_file(tmp_path: Path) -> Path:
    """Create a temporary transcript JSONL file.

    Args:
        tmp_path: Pytest-provided temporary directory.

    Returns:
        Path to the empty transcript file.
    """
    f = tmp_path / "transcript.jsonl"
    f.touch()
    return f


def _make_user_entry(text: str) -> str:
    """Build a JSONL line for a user message.

    Args:
        text: The user message text.

    Returns:
        JSON string representing the user entry.
    """
    return json.dumps({"type": "user", "message": {"content": text}})


def _make_assistant_entry(text: str) -> str:
    """Build a JSONL line for an assistant message.

    Args:
        text: The assistant message text.

    Returns:
        JSON string representing the assistant entry.
    """
    return json.dumps(
        {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}
    )


# ---------------------------------------------------------------------------
# is_full_log_enabled
# ---------------------------------------------------------------------------


class TestIsFullLogEnabled:
    """Tests for is_full_log_enabled()."""

    def test_enabled_when_set_to_1(self) -> None:
        """FULL_LOG=1 should be truthy."""
        with patch.dict(os.environ, {"FULL_LOG": "1"}):
            assert session_stop.is_full_log_enabled() is True

    def test_enabled_when_set_to_true(self) -> None:
        """FULL_LOG=true should be truthy."""
        with patch.dict(os.environ, {"FULL_LOG": "true"}):
            assert session_stop.is_full_log_enabled() is True

    def test_enabled_when_set_to_yes(self) -> None:
        """FULL_LOG=yes should be truthy (not in the falsy list)."""
        with patch.dict(os.environ, {"FULL_LOG": "yes"}):
            assert session_stop.is_full_log_enabled() is True

    def test_enabled_when_set_to_arbitrary_string(self) -> None:
        """FULL_LOG=anything should be truthy."""
        with patch.dict(os.environ, {"FULL_LOG": "anything"}):
            assert session_stop.is_full_log_enabled() is True

    def test_disabled_when_unset(self) -> None:
        """FULL_LOG not set should be falsy."""
        env = os.environ.copy()
        env.pop("FULL_LOG", None)
        with patch.dict(os.environ, env, clear=True):
            assert session_stop.is_full_log_enabled() is False

    def test_disabled_when_empty(self) -> None:
        """FULL_LOG='' should be falsy."""
        with patch.dict(os.environ, {"FULL_LOG": ""}):
            assert session_stop.is_full_log_enabled() is False

    def test_disabled_when_zero(self) -> None:
        """FULL_LOG=0 should be falsy."""
        with patch.dict(os.environ, {"FULL_LOG": "0"}):
            assert session_stop.is_full_log_enabled() is False

    def test_disabled_when_false(self) -> None:
        """FULL_LOG=false should be falsy."""
        with patch.dict(os.environ, {"FULL_LOG": "false"}):
            assert session_stop.is_full_log_enabled() is False

    def test_disabled_when_no(self) -> None:
        """FULL_LOG=no should be falsy."""
        with patch.dict(os.environ, {"FULL_LOG": "no"}):
            assert session_stop.is_full_log_enabled() is False


# ---------------------------------------------------------------------------
# load_full_log_state / save_full_log_state
# ---------------------------------------------------------------------------


class TestFullLogState:
    """Tests for load_full_log_state and save_full_log_state."""

    def test_load_returns_defaults_when_missing(self, tmp_path: Path) -> None:
        """Returns default state when the state file does not exist."""
        state = session_stop.load_full_log_state(tmp_path / "nonexistent.json")
        assert state == {"transcript_path": "", "line_offset": 0}

    def test_load_returns_defaults_on_corrupt_json(self, tmp_path: Path) -> None:
        """Returns default state when the state file contains invalid JSON."""
        state_file = tmp_path / "state.json"
        state_file.write_text("not json")
        state = session_stop.load_full_log_state(state_file)
        assert state == {"transcript_path": "", "line_offset": 0}

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        """State is preserved across save and load."""
        state_file = tmp_path / "state.json"
        session_stop.save_full_log_state(state_file, "/some/transcript.jsonl", 42)
        state = session_stop.load_full_log_state(state_file)
        assert state["transcript_path"] == "/some/transcript.jsonl"
        assert state["line_offset"] == 42


# ---------------------------------------------------------------------------
# parse_transcript_lines
# ---------------------------------------------------------------------------


class TestParseTranscriptLines:
    """Tests for parse_transcript_lines."""

    def test_returns_empty_for_nonexistent_file(self) -> None:
        """Returns empty list when the file does not exist."""
        result = session_stop.parse_transcript_lines("/nonexistent/path.jsonl")
        assert result == []

    def test_strips_and_filters_blank_lines(self, transcript_file: Path) -> None:
        """Returns only non-empty stripped lines."""
        transcript_file.write_text("line1\n\n  line2  \n\n")
        result = session_stop.parse_transcript_lines(str(transcript_file))
        assert result == ["line1", "line2"]


# ---------------------------------------------------------------------------
# format_messages_from_lines
# ---------------------------------------------------------------------------


class TestFormatMessagesFromLines:
    """Tests for format_messages_from_lines."""

    def test_formats_user_and_assistant(self) -> None:
        """Produces markdown headers for user and assistant entries."""
        lines = [
            _make_user_entry("Hello"),
            _make_assistant_entry("Hi there"),
        ]
        result = session_stop.format_messages_from_lines(lines)
        assert "## User\nHello" in result
        assert "## Assistant\nHi there" in result

    def test_skips_invalid_json(self) -> None:
        """Invalid JSON lines are silently skipped."""
        lines = ["not json", _make_user_entry("valid")]
        result = session_stop.format_messages_from_lines(lines)
        assert "## User\nvalid" in result

    def test_skips_non_user_assistant_types(self) -> None:
        """Entries with types other than user/assistant are ignored."""
        lines = [json.dumps({"type": "system", "message": {"content": "boot"}})]
        result = session_stop.format_messages_from_lines(lines)
        assert result == ""

    def test_empty_lines_returns_empty_string(self) -> None:
        """An empty list of lines produces an empty string."""
        assert session_stop.format_messages_from_lines([]) == ""


# ---------------------------------------------------------------------------
# append_full_log — integration tests
# ---------------------------------------------------------------------------


class TestAppendFullLog:
    """Tests for append_full_log."""

    def test_first_invocation_creates_full_log(
        self, logs_dir: Path, transcript_file: Path
    ) -> None:
        """First call creates full_log.md with a session header and content."""
        transcript_file.write_text(
            _make_user_entry("Hello") + "\n" + _make_assistant_entry("World") + "\n"
        )
        session_stop.append_full_log(logs_dir, str(transcript_file))

        full_log = (logs_dir / "full_log.md").read_text()
        assert "# Session:" in full_log
        assert "## User\nHello" in full_log
        assert "## Assistant\nWorld" in full_log

    def test_second_invocation_appends_delta_only(
        self, logs_dir: Path, transcript_file: Path
    ) -> None:
        """Second call with more lines only appends the new messages."""
        # First invocation with 2 lines
        transcript_file.write_text(
            _make_user_entry("msg1") + "\n" + _make_assistant_entry("reply1") + "\n"
        )
        session_stop.append_full_log(logs_dir, str(transcript_file))

        # Append more lines to the transcript
        with open(transcript_file, "a") as f:
            f.write(_make_user_entry("msg2") + "\n")
            f.write(_make_assistant_entry("reply2") + "\n")

        session_stop.append_full_log(logs_dir, str(transcript_file))

        full_log = (logs_dir / "full_log.md").read_text()
        # msg1 and reply1 should appear exactly once
        assert full_log.count("## User\nmsg1") == 1
        assert full_log.count("## Assistant\nreply1") == 1
        # msg2 and reply2 should also appear
        assert "## User\nmsg2" in full_log
        assert "## Assistant\nreply2" in full_log

    def test_no_duplicate_on_idempotent_call(
        self, logs_dir: Path, transcript_file: Path
    ) -> None:
        """Calling again with no new lines does not duplicate content."""
        transcript_file.write_text(_make_user_entry("once") + "\n")
        session_stop.append_full_log(logs_dir, str(transcript_file))
        session_stop.append_full_log(logs_dir, str(transcript_file))

        full_log = (logs_dir / "full_log.md").read_text()
        assert full_log.count("## User\nonce") == 1

    def test_new_session_adds_separator(self, logs_dir: Path, tmp_path: Path) -> None:
        """A different transcript path triggers a new session separator."""
        transcript_a = tmp_path / "transcript_a.jsonl"
        transcript_b = tmp_path / "transcript_b.jsonl"
        transcript_a.write_text(_make_user_entry("session A") + "\n")
        transcript_b.write_text(_make_user_entry("session B") + "\n")

        session_stop.append_full_log(logs_dir, str(transcript_a))
        session_stop.append_full_log(logs_dir, str(transcript_b))

        full_log = (logs_dir / "full_log.md").read_text()
        # Should have two session headers (---\n\n# Session:)
        assert full_log.count("# Session:") == 2
        assert full_log.count("---") == 2

    def test_state_file_updated_after_append(
        self, logs_dir: Path, transcript_file: Path
    ) -> None:
        """State file reflects the correct line offset after appending."""
        transcript_file.write_text(
            _make_user_entry("a") + "\n" + _make_assistant_entry("b") + "\n"
        )
        session_stop.append_full_log(logs_dir, str(transcript_file))

        state = session_stop.load_full_log_state(
            logs_dir / session_stop.FULL_LOG_STATE_FILENAME
        )
        assert state["transcript_path"] == str(transcript_file)
        assert state["line_offset"] == 2

    def test_non_message_lines_advance_offset(
        self, logs_dir: Path, transcript_file: Path
    ) -> None:
        """Lines that are not user/assistant still advance the offset to avoid reprocessing."""
        transcript_file.write_text(
            json.dumps({"type": "system", "message": {"content": "boot"}}) + "\n"
        )
        session_stop.append_full_log(logs_dir, str(transcript_file))

        state = session_stop.load_full_log_state(
            logs_dir / session_stop.FULL_LOG_STATE_FILENAME
        )
        assert state["line_offset"] == 1

    def test_no_size_cap_on_full_log(
        self, logs_dir: Path, transcript_file: Path
    ) -> None:
        """full_log.md has no character cap — unlike last_session.md's 20K limit."""
        # Write a transcript that would exceed MAX_CHAT_CHARS
        large_text = "x" * 25_000
        transcript_file.write_text(_make_user_entry(large_text) + "\n")
        session_stop.append_full_log(logs_dir, str(transcript_file))

        full_log = (logs_dir / "full_log.md").read_text()
        # The full 25K text should be present, not truncated
        assert large_text in full_log


# ---------------------------------------------------------------------------
# main() integration — FULL_LOG behavior
# ---------------------------------------------------------------------------


class TestMainFullLogIntegration:
    """Tests for main() with FULL_LOG enabled and disabled."""

    def _build_payload(self, cwd: str, transcript_path: str) -> str:
        """Build a JSON payload string mimicking the hook input.

        Args:
            cwd: Working directory.
            transcript_path: Path to the transcript file.

        Returns:
            JSON string payload.
        """
        return json.dumps(
            {
                "session_id": "test-session",
                "transcript_path": transcript_path,
                "cwd": cwd,
            }
        )

    def test_full_log_written_when_enabled(self, tmp_path: Path) -> None:
        """full_log.md is created when FULL_LOG=1."""
        cwd = str(tmp_path)
        logs_dir = tmp_path / ".claude" / "logs"
        logs_dir.mkdir(parents=True)

        transcript = tmp_path / "t.jsonl"
        transcript.write_text(_make_user_entry("hi") + "\n")

        payload = self._build_payload(cwd, str(transcript))

        with patch.dict(os.environ, {"FULL_LOG": "1"}):
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = payload
                session_stop.main()

        assert (logs_dir / "full_log.md").exists()
        assert "## User\nhi" in (logs_dir / "full_log.md").read_text()

    def test_full_log_not_written_when_disabled(self, tmp_path: Path) -> None:
        """full_log.md is not created when FULL_LOG is not set."""
        cwd = str(tmp_path)
        logs_dir = tmp_path / ".claude" / "logs"
        logs_dir.mkdir(parents=True)

        transcript = tmp_path / "t.jsonl"
        transcript.write_text(_make_user_entry("hi") + "\n")

        payload = self._build_payload(cwd, str(transcript))

        env = os.environ.copy()
        env.pop("FULL_LOG", None)
        with patch.dict(os.environ, env, clear=True):
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = payload
                session_stop.main()

        assert not (logs_dir / "full_log.md").exists()

    def test_last_session_unchanged_when_full_log_enabled(self, tmp_path: Path) -> None:
        """last_session.md is written normally regardless of FULL_LOG."""
        cwd = str(tmp_path)
        logs_dir = tmp_path / ".claude" / "logs"
        logs_dir.mkdir(parents=True)

        transcript = tmp_path / "t.jsonl"
        transcript.write_text(
            _make_user_entry("hello") + "\n" + _make_assistant_entry("world") + "\n"
        )

        payload = self._build_payload(cwd, str(transcript))

        with patch.dict(os.environ, {"FULL_LOG": "1"}):
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = payload
                session_stop.main()

        last_session = (logs_dir / "last_session.md").read_text()
        assert "## User\nhello" in last_session
        assert "## Assistant\nworld" in last_session


# ---------------------------------------------------------------------------
# main() resilience — individual stage failures must not crash the hook
# ---------------------------------------------------------------------------


class TestMainResilience:
    """Tests that main() survives individual operation failures.

    If any single operation (parse, write, append, audit) raises an
    exception, the hook MUST still exit cleanly (exit code 0) so that
    Claude Code continues to invoke it on subsequent turns.
    """

    def _build_payload(self, cwd: str, transcript_path: str) -> str:
        """Build a JSON payload string mimicking the hook input.

        Args:
            cwd: Working directory.
            transcript_path: Path to the transcript file.

        Returns:
            JSON string payload.
        """
        return json.dumps(
            {
                "session_id": "test-resilience",
                "transcript_path": transcript_path,
                "cwd": cwd,
            }
        )

    def test_survives_parse_transcript_failure(self, tmp_path: Path) -> None:
        """Hook continues when parse_transcript raises an exception."""
        cwd = str(tmp_path)
        logs_dir = tmp_path / ".claude" / "logs"
        logs_dir.mkdir(parents=True)

        transcript = tmp_path / "t.jsonl"
        transcript.write_text(_make_user_entry("hello") + "\n")

        payload = self._build_payload(cwd, str(transcript))

        env = os.environ.copy()
        env.pop("FULL_LOG", None)
        with patch.dict(os.environ, env, clear=True):
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = payload
                with patch.object(
                    session_stop,
                    "parse_transcript",
                    side_effect=OSError("disk error"),
                ):
                    session_stop.main()

        # last_session.md should still be written (with empty content)
        assert (logs_dir / "last_session.md").exists()
        # Audit log should still be written
        audit_file = logs_dir / "audit" / "session_stop.jsonl"
        assert audit_file.exists()

    def test_survives_write_last_session_failure(self, tmp_path: Path) -> None:
        """Hook continues when writing last_session.md fails."""
        cwd = str(tmp_path)
        logs_dir = tmp_path / ".claude" / "logs"
        logs_dir.mkdir(parents=True)

        transcript = tmp_path / "t.jsonl"
        transcript.write_text(_make_user_entry("hello") + "\n")

        payload = self._build_payload(cwd, str(transcript))

        env = os.environ.copy()
        env.pop("FULL_LOG", None)
        with patch.dict(os.environ, env, clear=True):
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = payload
                with patch("pathlib.Path.write_text", side_effect=OSError("locked")):
                    session_stop.main()

        # Audit log should still be written (via open(), not write_text)
        audit_file = logs_dir / "audit" / "session_stop.jsonl"
        assert audit_file.exists()

    def test_survives_log_audit_failure(self, tmp_path: Path) -> None:
        """Hook continues when log_audit raises an exception."""
        cwd = str(tmp_path)
        logs_dir = tmp_path / ".claude" / "logs"
        logs_dir.mkdir(parents=True)

        transcript = tmp_path / "t.jsonl"
        transcript.write_text(_make_user_entry("hello") + "\n")

        payload = self._build_payload(cwd, str(transcript))

        env = os.environ.copy()
        env.pop("FULL_LOG", None)
        with patch.dict(os.environ, env, clear=True):
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = payload
                with patch.object(
                    session_stop, "log_audit", side_effect=PermissionError("no write")
                ):
                    session_stop.main()

        # last_session.md should still be written despite audit failure
        assert (logs_dir / "last_session.md").exists()
        content = (logs_dir / "last_session.md").read_text()
        assert "## User\nhello" in content

    def test_survives_append_full_log_failure(self, tmp_path: Path) -> None:
        """Hook continues when append_full_log raises an exception."""
        cwd = str(tmp_path)
        logs_dir = tmp_path / ".claude" / "logs"
        logs_dir.mkdir(parents=True)

        transcript = tmp_path / "t.jsonl"
        transcript.write_text(_make_user_entry("hello") + "\n")

        payload = self._build_payload(cwd, str(transcript))

        with patch.dict(os.environ, {"FULL_LOG": "1"}):
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = payload
                with patch.object(
                    session_stop,
                    "append_full_log",
                    side_effect=OSError("full_log write failed"),
                ):
                    session_stop.main()

        # last_session.md and audit should still be written
        assert (logs_dir / "last_session.md").exists()
        audit_file = logs_dir / "audit" / "session_stop.jsonl"
        assert audit_file.exists()

    def test_invalid_stdin_does_not_crash(self) -> None:
        """Hook handles invalid stdin gracefully."""
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = "not json at all {"
            session_stop.main()  # Should not raise

    def test_empty_stdin_does_not_crash(self) -> None:
        """Hook handles empty stdin gracefully."""
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = ""
            session_stop.main()  # Should not raise

    def test_stdin_read_oserror_does_not_crash(self) -> None:
        """Hook handles OSError on stdin.read() gracefully."""
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.side_effect = OSError("broken pipe")
            session_stop.main()  # Should not raise

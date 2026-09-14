"""Tests for agent log directory naming, shared by subagent_start and subagent_stop.

The two hooks share .agent_map.json, so they must derive a directory name
identically. They also both take the agent type straight from a hook payload, so
neither may let it escape the agents log directory.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks directory to path so we can import the hook modules.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

import hook_paths
import subagent_start
import subagent_stop

AGENTS_RELATIVE_PATH = Path(".claude") / "logs" / "agents"
TRAVERSING_TYPE = "../../etc/passwd"


@pytest.fixture(autouse=True)
def unset_project_dir_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force log anchoring to the payload cwd so tests write into tmp_path."""
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)


def agents_dir_of(project_root: Path) -> Path:
    """Return the agents log directory for a project root.

    Args:
        project_root: The project the hooks anchored their logs to.

    Returns:
        The ``.claude/logs/agents`` path.
    """
    return project_root / AGENTS_RELATIVE_PATH


def read_agent_map(project_root: Path) -> dict:
    """Read the agent_id to directory mapping.

    Args:
        project_root: The project the hooks anchored their logs to.

    Returns:
        The decoded map, empty when it has not been written.
    """
    map_file = agents_dir_of(project_root) / ".agent_map.json"
    if not map_file.is_file():
        return {}
    return json.loads(map_file.read_text())


def run_stop(payload: dict) -> None:
    """Run subagent_stop.main() with the given payload.

    Args:
        payload: The full JSON payload to feed the hook on stdin.
    """
    with patch("sys.stdin") as mock_stdin:
        mock_stdin.read.return_value = json.dumps(payload)
        subagent_stop.main()


def run_start(payload: dict) -> None:
    """Run subagent_start.main() with the given payload, discarding stdout.

    Args:
        payload: The full JSON payload to feed the hook on stdin.
    """
    with patch("sys.stdin") as mock_stdin:
        mock_stdin.read.return_value = json.dumps(payload)
        subagent_start.main()


class TestAgentDirPrefix:
    """Tests for reducing an agent type to a safe directory prefix."""

    @pytest.mark.parametrize(
        "agent_type",
        [
            "python-developer",
            "claude-code-guide",
            "general-purpose",
            "Plan",
            "e2e-developer",
        ],
    )
    def test_existing_types_pass_through_unchanged(self, agent_type: str) -> None:
        """Every agent type already on disk keeps its exact prefix."""
        assert hook_paths.agent_dir_prefix(agent_type) == agent_type

    @pytest.mark.parametrize(
        "agent_type",
        ["", "   ", TRAVERSING_TYPE, "..", "a/b", ".hidden", "with space"],
    )
    def test_unsafe_types_become_neutral(self, agent_type: str) -> None:
        """An empty or unsafe type becomes a neutral, legible prefix."""
        assert (
            hook_paths.agent_dir_prefix(agent_type)
            == hook_paths.UNKNOWN_AGENT_DIR_PREFIX
        )


class TestNextAgentNumber:
    """Tests that numbering still counts against what already exists."""

    def test_counts_existing_directories(self, tmp_path: Path) -> None:
        """Existing directories on disk are counted even with no map."""
        (tmp_path / "python-developer-29").mkdir()
        (tmp_path / "python-developer-7").mkdir()

        assert hook_paths.next_agent_number(tmp_path, "python-developer", {}) == 30

    def test_counts_map_entries_without_directories(self, tmp_path: Path) -> None:
        """Map entries count even before their directories exist."""
        agent_map = {"aaa": "python-developer-30"}
        assert (
            hook_paths.next_agent_number(tmp_path, "python-developer", agent_map) == 31
        )

    def test_legacy_empty_prefix_dirs_do_not_feed_unknown(self, tmp_path: Path) -> None:
        """Pre-existing "-18" directories do not inflate the unknown- sequence."""
        (tmp_path / "-18").mkdir()
        (tmp_path / "-19").mkdir()

        assert hook_paths.next_agent_number(tmp_path, "unknown", {}) == 1

    def test_prefixes_do_not_bleed_into_each_other(self, tmp_path: Path) -> None:
        """A different prefix's directories do not affect this prefix's count."""
        (tmp_path / "next-developer-12").mkdir()
        assert hook_paths.next_agent_number(tmp_path, "python-developer", {}) == 1


class TestBothHooksDeriveTheSameName:
    """The regression that would hurt most: start and stop disagreeing."""

    @pytest.mark.parametrize(
        "agent_type", ["python-developer", "", TRAVERSING_TYPE, "general-purpose"]
    )
    def test_start_and_stop_agree(self, agent_type: str, tmp_path: Path) -> None:
        """Both hooks name the directory identically from identical state."""
        start_root = tmp_path / "start"
        stop_root = tmp_path / "stop"
        for root in (start_root, stop_root):
            agents_dir_of(root).mkdir(parents=True)

        start_name = subagent_start.register_agent(
            str(start_root), "agent-1", agent_type
        )
        stop_path = subagent_stop.resolve_agent_dir(
            agents_dir_of(stop_root), "agent-1", agent_type
        )

        assert start_name == stop_path.name

    def test_stop_reuses_the_directory_start_registered(self, tmp_path: Path) -> None:
        """A full start-then-stop cycle writes into one directory."""
        payload = {
            "agent_type": "python-developer",
            "agent_id": "shared-agent",
            "cwd": str(tmp_path),
        }
        run_start(payload)
        registered = read_agent_map(tmp_path)["shared-agent"]

        run_stop(payload)

        summary = agents_dir_of(tmp_path) / registered / "summary.jsonl"
        assert summary.is_file()
        assert registered == "python-developer-1"


class TestTraversalIsContained:
    """Tests that a path-shaped agent type cannot steer directory creation."""

    def test_stop_creates_nothing_outside_the_agents_dir(self, tmp_path: Path) -> None:
        """subagent_stop is the hook that creates the directory, so it must contain it."""
        run_stop(
            {"agent_type": TRAVERSING_TYPE, "agent_id": "evil-1", "cwd": str(tmp_path)}
        )

        agents_dir = agents_dir_of(tmp_path)
        created = sorted(p.name for p in agents_dir.iterdir() if p.is_dir())
        assert created == ["unknown-1"]
        assert not (tmp_path / "etc").exists()
        assert not (tmp_path.parent / "etc").exists()

    def test_start_records_nothing_outside_the_agents_dir(self, tmp_path: Path) -> None:
        """subagent_start records only a contained name in the map."""
        run_start(
            {"agent_type": TRAVERSING_TYPE, "agent_id": "evil-2", "cwd": str(tmp_path)}
        )

        assert read_agent_map(tmp_path)["evil-2"] == "unknown-1"

    def test_resolved_path_stays_inside_agents_dir(self, tmp_path: Path) -> None:
        """The resolved directory is a child of the agents directory."""
        agents_dir = agents_dir_of(tmp_path)
        agents_dir.mkdir(parents=True)

        resolved = subagent_stop.resolve_agent_dir(
            agents_dir, "evil-3", TRAVERSING_TYPE
        )

        assert resolved.resolve().parent == agents_dir.resolve()


class TestEmptyAgentType:
    """Tests the empty-type case that produced the "-NN" directory noise."""

    def test_stop_uses_the_neutral_name(self, tmp_path: Path) -> None:
        """An empty type yields unknown-1, not a directory named "-1"."""
        run_stop({"agent_type": "", "agent_id": "blank-1", "cwd": str(tmp_path)})

        agents_dir = agents_dir_of(tmp_path)
        assert (agents_dir / "unknown-1").is_dir()
        assert not (agents_dir / "-1").exists()

    def test_original_type_is_preserved_in_the_summary(self, tmp_path: Path) -> None:
        """Sanitising the path must not lose the real payload value."""
        run_stop({"agent_type": "", "agent_id": "blank-2", "cwd": str(tmp_path)})

        summary_file = agents_dir_of(tmp_path) / "unknown-1" / "summary.jsonl"
        entry = json.loads(summary_file.read_text().strip())
        assert entry["agent_type"] == ""
        assert entry["agent_dir"] == "unknown-1"
        assert entry["event"] == "completed"

    def test_start_audit_preserves_the_unsafe_type(self, tmp_path: Path) -> None:
        """The audit record keeps the raw type and names the substituted directory."""
        run_start(
            {"agent_type": TRAVERSING_TYPE, "agent_id": "blank-3", "cwd": str(tmp_path)}
        )

        audit = tmp_path / ".claude" / "logs" / "audit" / "subagent_start.jsonl"
        record = json.loads(audit.read_text().strip())
        assert record["agent_type"] == TRAVERSING_TYPE
        assert record["agent_dir_name"] == "unknown-1"

    def test_successive_blanks_increment(self, tmp_path: Path) -> None:
        """A second unnamed agent gets unknown-2, not a collision."""
        run_stop({"agent_type": "", "agent_id": "blank-a", "cwd": str(tmp_path)})
        run_stop({"agent_type": "", "agent_id": "blank-b", "cwd": str(tmp_path)})

        agents_dir = agents_dir_of(tmp_path)
        assert (agents_dir / "unknown-1").is_dir()
        assert (agents_dir / "unknown-2").is_dir()


class TestExistingDirectoriesStillResolve:
    """Tests that nothing already on disk is disturbed."""

    @pytest.mark.parametrize(
        "dir_name",
        [
            "python-developer-29",
            "claude-code-guide-6",
            "general-purpose-1",
            "Plan-1",
            "-18",
        ],
    )
    def test_mapped_agent_keeps_its_directory(
        self, dir_name: str, tmp_path: Path
    ) -> None:
        """An agent already in the map resolves to the same directory as before."""
        agents_dir = agents_dir_of(tmp_path)
        agents_dir.mkdir(parents=True)
        (agents_dir / ".agent_map.json").write_text(json.dumps({"old-agent": dir_name}))

        resolved = subagent_stop.resolve_agent_dir(agents_dir, "old-agent", "")

        assert resolved == agents_dir / dir_name

    def test_new_agent_of_existing_type_increments(self, tmp_path: Path) -> None:
        """Numbering continues from the highest existing directory."""
        agents_dir = agents_dir_of(tmp_path)
        agents_dir.mkdir(parents=True)
        (agents_dir / "python-developer-29").mkdir()

        resolved = subagent_stop.resolve_agent_dir(
            agents_dir, "new-agent", "python-developer"
        )

        assert resolved.name == "python-developer-30"

    def test_normal_type_summary_shape_unchanged(self, tmp_path: Path) -> None:
        """A safe agent type writes exactly the summary fields it always has."""
        run_stop(
            {"agent_type": "python-developer", "agent_id": "ok-1", "cwd": str(tmp_path)}
        )

        summary_file = agents_dir_of(tmp_path) / "python-developer-1" / "summary.jsonl"
        entry = json.loads(summary_file.read_text().strip())
        assert list(entry) == ["_timestamp", "agent_id", "agent_type", "event"]

    def test_transcript_is_captured_into_the_resolved_directory(
        self, tmp_path: Path
    ) -> None:
        """The transcript still lands in the agent's directory."""
        transcript = tmp_path / "src.jsonl"
        transcript.write_text('{"role": "user"}\n')

        run_stop(
            {
                "agent_type": "python-developer",
                "agent_id": "ok-2",
                "cwd": str(tmp_path),
                "agent_transcript_path": str(transcript),
            }
        )

        captured = agents_dir_of(tmp_path) / "python-developer-1" / "transcript.jsonl"
        assert captured.read_text() == '{"role": "user"}\n'

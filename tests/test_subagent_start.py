"""Tests for subagent_start — repo-path derivation, skill injection, and audit logging."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks directory to path so we can import subagent_start.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

import subagent_start

AUDIT_RELATIVE_PATH = Path(".claude") / "logs" / "audit" / "subagent_start.jsonl"


def read_audit_lines(project_root: Path) -> list[dict]:
    """Read the audit records written under a project root.

    Args:
        project_root: Directory the hook anchored its .claude/logs tree to.

    Returns:
        One decoded record per audit line, in write order.
    """
    audit_file = project_root / AUDIT_RELATIVE_PATH
    if not audit_file.is_file():
        return []
    return [
        json.loads(line) for line in audit_file.read_text().splitlines() if line.strip()
    ]


def run_main(payload: dict, capsys: pytest.CaptureFixture) -> str:
    """Run main() with the given payload and return captured stdout.

    Args:
        payload: The full JSON payload to feed the hook on stdin.
        capsys: Pytest stdout/stderr capture fixture.

    Returns:
        The captured stdout string.
    """
    with patch("sys.stdin") as mock_stdin:
        mock_stdin.read.return_value = json.dumps(payload)
        subagent_start.main()
    return capsys.readouterr().out


@pytest.fixture(autouse=True)
def unset_project_dir_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force log anchoring to the payload cwd so tests write into tmp_path."""
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)


class TestSubstituteRepoPath:
    """Tests for substitute_repo_path."""

    def test_substitute_repo_path_replaces_placeholder(self) -> None:
        """Replaces every placeholder occurrence with the absolute repo root."""
        repo_root = Path("/abs/repo")
        text = "See {{AI_AGENT_ENV_PATH}}/templates/Makefile.docker and {{AI_AGENT_ENV_PATH}}/skills."

        result = subagent_start.substitute_repo_path(text, repo_root)

        assert "{{AI_AGENT_ENV_PATH}}" not in result
        assert result.count("/abs/repo") == 2

    def test_substitute_repo_path_no_placeholder_unchanged(self) -> None:
        """Leaves text without the placeholder unchanged."""
        text = "no placeholder here"
        result = subagent_start.substitute_repo_path(text, Path("/abs/repo"))
        assert result == text


class TestRepoRootDerivation:
    """Tests that the repo root is derived from the hook file location."""

    def test_repo_root_is_hook_parent_parent(self) -> None:
        """REPO_ROOT resolves to <repo> (the hook's parent.parent)."""
        expected = Path(subagent_start.__file__).resolve().parent.parent
        assert subagent_start.REPO_ROOT == expected
        assert subagent_start.REPO_ROOT.is_absolute()


class TestResolveAgentType:
    """Tests for resolving the agent type across payload shapes."""

    def test_prefers_agent_type_key(self) -> None:
        """Uses agent_type first when several candidate keys are present."""
        payload = {"agent_type": "python-developer", "subagent_type": "next-developer"}
        assert subagent_start.resolve_agent_type(payload) == (
            "python-developer",
            "agent_type",
        )

    def test_empty_string_treated_as_absent(self) -> None:
        """An empty agent_type falls through to the next candidate key."""
        payload = {"agent_type": "", "subagent_type": "e2e-developer"}
        assert subagent_start.resolve_agent_type(payload) == (
            "e2e-developer",
            "subagent_type",
        )

    def test_whitespace_only_treated_as_absent(self) -> None:
        """A whitespace-only value does not count as a resolution."""
        assert subagent_start.resolve_agent_type({"agent_type": "   "}) == ("", "")

    def test_camel_case_alternate_key(self) -> None:
        """Recognises the camelCase spelling of the field."""
        assert subagent_start.resolve_agent_type({"agentType": "next-developer"}) == (
            "next-developer",
            "agentType",
        )

    def test_nested_container_key(self) -> None:
        """Finds the type nested inside a container object."""
        payload = {"agent_type": "", "agent": {"name": "python-developer"}}
        assert subagent_start.resolve_agent_type(payload) == (
            "python-developer",
            "agent.name",
        )

    def test_unresolvable_payload(self) -> None:
        """Returns empty strings when no candidate key holds a value."""
        assert subagent_start.resolve_agent_type({"session_id": "abc"}) == ("", "")


class TestCapturePayload:
    """Tests for the redacted diagnostic payload capture."""

    def test_redacts_bulk_text_keys(self) -> None:
        """Replaces transcript- and prompt-like values instead of copying them."""
        captured = subagent_start.capture_payload(
            {
                "agent_transcript_path": "/x/y.jsonl",
                "prompt": "a" * 5000,
                "cwd": "/repo",
            }
        )
        assert captured["agent_transcript_path"] == subagent_start.REDACTED_MARKER
        assert captured["prompt"] == subagent_start.REDACTED_MARKER
        assert captured["cwd"] == "/repo"

    def test_truncates_long_plain_values(self) -> None:
        """Truncates an over-long value under a key that is not redacted outright."""
        captured = subagent_start.capture_payload({"cwd": "b" * 5000})
        assert captured["cwd"].endswith(subagent_start.TRUNCATED_SUFFIX)
        assert len(captured["cwd"]) < 5000

    def test_returns_none_when_still_too_large(self) -> None:
        """Declines to capture a payload that stays over the size cap."""
        oversized = {f"field_{i}": "c" * 100 for i in range(200)}
        assert subagent_start.capture_payload(oversized) is None


class TestParseFrontmatter:
    """Tests for skill frontmatter parsing."""

    def test_parses_name_description_globs(self) -> None:
        """Reads the scalar fields the fallback context needs."""
        text = '---\nname: python-conventions\ndescription: "Python conventions"\nglobs: ["**/*.py"]\n---\n\nBody'
        fields = subagent_start.parse_frontmatter(text)
        assert fields["name"] == "python-conventions"
        assert fields["description"] == "Python conventions"
        assert fields["globs"] == '["**/*.py"]'

    def test_no_frontmatter_returns_empty(self) -> None:
        """Returns an empty mapping for a file without a frontmatter block."""
        assert subagent_start.parse_frontmatter("# Just a heading\n") == {}

    def test_parses_block_sequence(self) -> None:
        """Reads a YAML block sequence such as an agent's skills: list."""
        text = "---\nname: python-developer\nskills:\n  - python-conventions\n  - extra\n---\n\nBody"
        fields = subagent_start.parse_frontmatter(text)
        assert fields["skills"] == ["python-conventions", "extra"]
        assert fields["name"] == "python-developer"

    def test_key_with_no_value_and_no_items_is_empty_list(self) -> None:
        """A skills: key with nothing under it yields an empty list, not a scalar."""
        fields = subagent_start.parse_frontmatter("---\nskills:\n---\n")
        assert fields["skills"] == []


class TestParseInlineList:
    """Tests for the single-line skills: spelling."""

    def test_flow_sequence(self) -> None:
        """Splits a YAML flow sequence into items."""
        assert subagent_start.parse_inline_list('["a", b]') == ["a", "b"]

    def test_bare_scalar(self) -> None:
        """Treats a bare scalar as a one-item list."""
        assert subagent_start.parse_inline_list("python-conventions") == [
            "python-conventions"
        ]

    def test_empty(self) -> None:
        """Yields no items for an empty value."""
        assert subagent_start.parse_inline_list("   ") == []


class TestNameSafety:
    """Tests that payload- and file-supplied names cannot escape their directory."""

    @pytest.mark.parametrize(
        "name",
        ["../../etc/passwd", "..", "a/b", "a\\b", ".hidden", "", "with space"],
    )
    def test_rejects_unsafe_names(self, name: str) -> None:
        """Rejects traversal, separators, and other unusable names."""
        assert subagent_start.is_safe_name(name) is False

    def test_accepts_ordinary_names(self) -> None:
        """Accepts the names the repo actually uses."""
        assert subagent_start.is_safe_name("python-developer") is True
        assert subagent_start.is_safe_name("python-conventions.md") is True

    def test_traversing_agent_type_finds_no_definition(self, tmp_path: Path) -> None:
        """An agent type that looks like a path resolves to no definition file."""
        assert (
            subagent_start.resolve_agent_definition_path(
                str(tmp_path), "../../etc/passwd"
            )
            is None
        )

    def test_traversing_skill_name_is_dropped(self) -> None:
        """A skill name that looks like a path normalises to nothing."""
        assert subagent_start.normalize_skill_filename("../../../etc/passwd") == ""


class TestNormalizeSkillFilename:
    """Tests for mapping a declared skill name onto a file name."""

    def test_appends_markdown_suffix(self) -> None:
        """A bare skill name gains the .md suffix."""
        assert (
            subagent_start.normalize_skill_filename("python-conventions")
            == "python-conventions.md"
        )

    def test_accepts_filename_spelling(self) -> None:
        """A name already written as a file name is left alone."""
        assert (
            subagent_start.normalize_skill_filename("python-conventions.md")
            == "python-conventions.md"
        )


class TestAvailableSkillFilenames:
    """Tests that the fallback listing enumerates real files, not the dict."""

    def test_includes_skills_absent_from_agent_skills(self, tmp_path: Path) -> None:
        """A skill no agent maps to is still listed."""
        filenames = subagent_start.available_skill_filenames(str(tmp_path))
        mapped = {f for files in subagent_start.AGENT_SKILLS.values() for f in files}
        assert mapped <= set(filenames)
        # ai-interaction.md exists in the repo but is in no AGENT_SKILLS entry.
        assert "ai-interaction.md" in filenames
        assert "ai-interaction.md" not in mapped

    def test_includes_project_only_skills(self, tmp_path: Path) -> None:
        """A project-local skill with no repo counterpart is listed."""
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "house-style.md").write_text("---\nname: house-style\n---\n")

        assert "house-style.md" in subagent_start.available_skill_filenames(
            str(tmp_path)
        )


def write_agent_definition(root: Path, agent_type: str, body: str) -> Path:
    """Write a project-local agent definition file.

    Args:
        root: Project root to write under.
        agent_type: Agent type, used as the file stem.
        body: Full file contents.

    Returns:
        The path written.
    """
    agents_dir = root / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    path = agents_dir / f"{agent_type}.md"
    path.write_text(body)
    return path


def write_project_skill(root: Path, filename: str, body: str) -> Path:
    """Write a project-local skill file.

    Args:
        root: Project root to write under.
        filename: Skill file name.
        body: Full file contents.

    Returns:
        The path written.
    """
    skills_dir = root / ".claude" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    path = skills_dir / filename
    path.write_text(body)
    return path


class TestFrontmatterDrivenSkills:
    """Tests that agents/<type>.md frontmatter is the source of truth."""

    def test_frontmatter_drives_injection(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A skill declared only in frontmatter is injected."""
        write_agent_definition(
            tmp_path,
            "house-agent",
            "---\nname: house-agent\nskills:\n  - house-style\n---\n\nBody",
        )
        write_project_skill(tmp_path, "house-style.md", "HOUSE STYLE RULES")

        output = run_main(
            {"agent_type": "house-agent", "agent_id": "a", "cwd": str(tmp_path)}, capsys
        )

        context = json.loads(output)["hookSpecificOutput"]["additionalContext"]
        assert "HOUSE STYLE RULES" in context

        records = read_audit_lines(tmp_path)
        assert records[0]["skills_source"] == subagent_start.SKILLS_SOURCE_FRONTMATTER
        assert records[0]["skills_injected"]

    def test_name_without_md_suffix_resolves(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A frontmatter entry without .md still finds the skill file."""
        write_agent_definition(
            tmp_path,
            "house-agent",
            "---\nname: house-agent\nskills:\n  - house-style\n---\n",
        )
        write_project_skill(tmp_path, "house-style.md", "HOUSE STYLE RULES")

        run_main(
            {"agent_type": "house-agent", "agent_id": "a", "cwd": str(tmp_path)}, capsys
        )

        assert read_audit_lines(tmp_path)[0]["skills_injected"] == [
            f"house-style.md ({tmp_path / '.claude' / 'skills'})"
        ]

    def test_md_suffix_spelling_also_resolves(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A frontmatter entry written as a file name resolves identically."""
        write_agent_definition(
            tmp_path,
            "house-agent",
            "---\nname: house-agent\nskills:\n  - house-style.md\n---\n",
        )
        write_project_skill(tmp_path, "house-style.md", "HOUSE STYLE RULES")

        output = run_main(
            {"agent_type": "house-agent", "agent_id": "a", "cwd": str(tmp_path)}, capsys
        )

        assert (
            "HOUSE STYLE RULES"
            in json.loads(output)["hookSpecificOutput"]["additionalContext"]
        )

    def test_inline_list_spelling_resolves(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A single-line skills: [a] declaration is honoured."""
        write_agent_definition(
            tmp_path,
            "house-agent",
            '---\nname: house-agent\nskills: ["house-style"]\n---\n',
        )
        write_project_skill(tmp_path, "house-style.md", "HOUSE STYLE RULES")

        output = run_main(
            {"agent_type": "house-agent", "agent_id": "a", "cwd": str(tmp_path)}, capsys
        )

        assert (
            "HOUSE STYLE RULES"
            in json.loads(output)["hookSpecificOutput"]["additionalContext"]
        )

    def test_project_agent_file_overrides_repo(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A project-local agent definition wins over the repo's own."""
        write_agent_definition(
            tmp_path,
            "python-developer",
            "---\nname: python-developer\nskills:\n  - house-style\n---\n",
        )
        write_project_skill(tmp_path, "house-style.md", "HOUSE STYLE RULES")

        output = run_main(
            {"agent_type": "python-developer", "agent_id": "a", "cwd": str(tmp_path)},
            capsys,
        )

        context = json.loads(output)["hookSpecificOutput"]["additionalContext"]
        assert "HOUSE STYLE RULES" in context
        assert "MANDATORY conventions" not in context

        records = read_audit_lines(tmp_path)
        assert records[0]["skills_source"] == subagent_start.SKILLS_SOURCE_FRONTMATTER
        assert records[0]["agent_definition"] == str(
            tmp_path / ".claude" / "agents" / "python-developer.md"
        )
        assert records[0]["skills_divergence"] == {
            "frontmatter": ["house-style.md"],
            "agent_skills": ["python-conventions.md"],
        }

    def test_agent_without_skills_key_injects_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """plan-* agents declare no skills and must keep injecting nothing."""
        output = run_main(
            {"agent_type": "plan-critic", "agent_id": "a", "cwd": str(tmp_path)}, capsys
        )

        assert output == ""
        records = read_audit_lines(tmp_path)
        assert records[0]["skills_injected"] == []
        assert records[0]["note"] == subagent_start.NOTE_NO_SKILLS_DECLARED
        assert records[0]["skills_source"] == subagent_start.SKILLS_SOURCE_NO_SKILLS_KEY

    def test_empty_skills_list_injects_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A skills: key with no items injects nothing rather than everything."""
        write_agent_definition(
            tmp_path, "python-developer", "---\nname: python-developer\nskills:\n---\n"
        )

        output = run_main(
            {"agent_type": "python-developer", "agent_id": "a", "cwd": str(tmp_path)},
            capsys,
        )

        assert output == ""
        records = read_audit_lines(tmp_path)
        assert records[0]["skills_injected"] == []
        assert records[0]["skills_source"] == subagent_start.SKILLS_SOURCE_FRONTMATTER

    def test_malformed_agent_file_degrades_to_dict(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A definition with no frontmatter falls back to AGENT_SKILLS."""
        write_agent_definition(tmp_path, "python-developer", "# No frontmatter here\n")

        output = run_main(
            {"agent_type": "python-developer", "agent_id": "a", "cwd": str(tmp_path)},
            capsys,
        )

        context = json.loads(output)["hookSpecificOutput"]["additionalContext"]
        assert "MANDATORY conventions" in context

        records = read_audit_lines(tmp_path)
        assert records[0]["skills_source"] == subagent_start.SKILLS_SOURCE_FALLBACK_DICT
        assert records[0]["skills_injected"]

    def test_missing_agent_file_degrades_to_dict(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """No definition file anywhere still injects the dict's skills."""
        monkeypatch.setattr(subagent_start, "REPO_ROOT", tmp_path / "norepo")
        monkeypatch.setattr(
            subagent_start, "AGENT_SKILLS", {"python-developer": ["house-style.md"]}
        )
        write_project_skill(tmp_path, "house-style.md", "HOUSE STYLE RULES")

        output = run_main(
            {"agent_type": "python-developer", "agent_id": "a", "cwd": str(tmp_path)},
            capsys,
        )

        assert (
            "HOUSE STYLE RULES"
            in json.loads(output)["hookSpecificOutput"]["additionalContext"]
        )
        records = read_audit_lines(tmp_path)
        assert records[0]["skills_source"] == subagent_start.SKILLS_SOURCE_FALLBACK_DICT
        assert "agent_definition" not in records[0]

    def test_unknown_agent_type_injects_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """An agent with no definition and no dict entry stays an unmapped no-op."""
        output = run_main(
            {"agent_type": "unmapped-agent", "agent_id": "a", "cwd": str(tmp_path)},
            capsys,
        )

        assert output == ""
        records = read_audit_lines(tmp_path)
        assert records[0]["note"] == subagent_start.NOTE_UNMAPPED_AGENT_TYPE
        assert records[0]["skills_source"] == subagent_start.SKILLS_SOURCE_FALLBACK_DICT


class TestAuditSilentOnlyWhenSourcesAgree:
    """Tests the one condition under which the skill source is left unrecorded."""

    @pytest.mark.parametrize(
        "agent_type", ["python-developer", "next-developer", "e2e-developer"]
    )
    def test_agreeing_sources_keep_the_historical_record_shape(
        self, agent_type: str, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Frontmatter agreeing with AGENT_SKILLS logs exactly the old fields."""
        run_main(
            {"agent_type": agent_type, "agent_id": "a", "cwd": str(tmp_path)}, capsys
        )

        record = read_audit_lines(tmp_path)[0]
        assert list(record) == [
            "agent_id",
            "agent_type",
            "skills_injected",
            "_timestamp",
        ]


class TestMainInjection:
    """Tests for skill injection with placeholder substitution."""

    def _run_main(
        self, cwd: str, agent_type: str, capsys: pytest.CaptureFixture
    ) -> str:
        """Run main() with a mocked payload and return captured stdout.

        Args:
            cwd: Working directory reported in the payload.
            agent_type: The subagent type spawning.
            capsys: Pytest stdout/stderr capture fixture.

        Returns:
            The captured stdout string.
        """
        return run_main(
            {"agent_type": agent_type, "agent_id": "test-agent-1", "cwd": cwd}, capsys
        )

    def test_project_skill_placeholder_substituted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A project skill's placeholder is replaced with the absolute repo root."""
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "python-conventions.md").write_text(
            "Template: {{AI_AGENT_ENV_PATH}}/templates/Makefile.docker"
        )

        output = self._run_main(str(tmp_path), "python-developer", capsys)

        result = json.loads(output)
        context = result["hookSpecificOutput"]["additionalContext"]
        assert "{{AI_AGENT_ENV_PATH}}" not in context
        assert f"{subagent_start.REPO_ROOT}/templates/Makefile.docker" in context

    def test_repo_skill_used_when_no_project_override(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Falls back to the repo's own skills/ dir when no project override exists."""
        # No project .claude/skills — should load the real repo skill file.
        output = self._run_main(str(tmp_path), "python-developer", capsys)

        result = json.loads(output)
        context = result["hookSpecificOutput"]["additionalContext"]
        # The real repo skill file must have loaded and contain no unsubstituted
        # placeholder (whether or not it currently contains one).
        assert "## Injected Skills" in context
        assert "{{AI_AGENT_ENV_PATH}}" not in context

    def test_happy_path_audit_record_shape_unchanged(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A normal spawn writes exactly the audit fields it always has."""
        self._run_main(str(tmp_path), "python-developer", capsys)

        records = read_audit_lines(tmp_path)
        assert len(records) == 1
        assert list(records[0]) == [
            "agent_id",
            "agent_type",
            "skills_injected",
            "_timestamp",
        ]
        assert records[0]["agent_type"] == "python-developer"
        assert records[0]["skills_injected"]

    def test_unmapped_agent_type_no_injection_but_audited(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Produces no injection output for an unmapped agent type, but still audits it."""
        output = self._run_main(str(tmp_path), "unmapped-agent", capsys)

        assert output == ""
        records = read_audit_lines(tmp_path)
        assert len(records) == 1
        assert records[0]["agent_type"] == "unmapped-agent"
        assert records[0]["skills_injected"] == []
        assert records[0]["note"] == subagent_start.NOTE_UNMAPPED_AGENT_TYPE


class TestAlternateAgentTypeKey:
    """Tests that a renamed payload field still drives normal injection."""

    def test_alternate_key_injects_and_records_source(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A type carried by subagent_type injects skills and records the source key."""
        output = run_main(
            {
                "agent_type": "",
                "subagent_type": "python-developer",
                "agent_id": "test-agent-alt",
                "cwd": str(tmp_path),
            },
            capsys,
        )

        context = json.loads(output)["hookSpecificOutput"]["additionalContext"]
        assert "## Injected Skills" in context

        records = read_audit_lines(tmp_path)
        assert len(records) == 1
        assert records[0]["agent_type"] == "python-developer"
        assert records[0]["resolved_from"] == "subagent_type"
        assert records[0]["skills_injected"]


class TestUnresolvedAgentType:
    """Regression tests for the silent no-op when the agent type cannot be resolved."""

    @pytest.mark.parametrize(
        "payload_extra",
        [
            pytest.param({"agent_type": ""}, id="empty-string-agent-type"),
            pytest.param({}, id="missing-agent-type-key"),
        ],
    )
    def test_emits_read_conventions_fallback(
        self, payload_extra: dict, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Tells the agent to read the conventions itself rather than guessing."""
        payload = {"agent_id": "test-agent-2", "cwd": str(tmp_path), **payload_extra}

        output = run_main(payload, capsys)

        context = json.loads(output)["hookSpecificOutput"]["additionalContext"]
        assert "## Injected Skills" not in context
        assert "MUST read" in context
        # Every convention file is offered with an absolute path so the agent can choose.
        for filename in subagent_start.available_skill_filenames(str(tmp_path)):
            assert f"{subagent_start.REPO_ROOT / 'skills' / filename}" in context

    @pytest.mark.parametrize(
        "payload_extra",
        [
            pytest.param({"agent_type": ""}, id="empty-string-agent-type"),
            pytest.param({}, id="missing-agent-type-key"),
        ],
    )
    def test_writes_audit_record_with_payload_keys(
        self, payload_extra: dict, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Never fails silently: records the payload's key list for diagnosis."""
        payload = {
            "agent_id": "test-agent-2",
            "cwd": str(tmp_path),
            "session_id": "s-1",
            **payload_extra,
        }

        run_main(payload, capsys)

        records = read_audit_lines(tmp_path)
        assert len(records) == 1
        assert records[0]["agent_type"] == ""
        assert records[0]["note"] == subagent_start.NOTE_UNRESOLVED_AGENT_TYPE
        assert records[0]["fallback_emitted"] is True
        assert records[0]["unresolved_payload_keys"] == sorted(payload)
        assert records[0]["unresolved_payload"]["session_id"] == "s-1"

    def test_does_not_guess_a_skill(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Injects no skill body, since **/*.py is claimed by two convention files."""
        output = run_main({"agent_id": "a", "cwd": str(tmp_path)}, capsys)

        context = json.loads(output)["hookSpecificOutput"]["additionalContext"]
        assert "MANDATORY conventions" not in context
        records = read_audit_lines(tmp_path)
        assert records[0]["skills_injected"] == []

    def test_does_not_register_agent_directory(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Avoids creating the empty-prefixed "-N" directories seen in the logs."""
        run_main({"agent_id": "a", "cwd": str(tmp_path)}, capsys)

        agent_map = tmp_path / ".claude" / "logs" / "agents" / ".agent_map.json"
        assert not agent_map.exists()

    def test_undecodable_payload_is_audited(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """A non-JSON payload is recorded instead of exiting silently."""
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = "not json at all"
            subagent_start.main()

        assert capsys.readouterr().out == ""
        records = read_audit_lines(tmp_path)
        assert len(records) == 1
        assert records[0]["note"] == subagent_start.NOTE_UNDECODABLE_PAYLOAD

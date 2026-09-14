"""Tests for merge_global_settings — hook merge, env pin, and corrupt-file safety."""

import json
import sys
from pathlib import Path

import pytest

# Add scripts directory to path so we can import merge_global_settings.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import merge_global_settings


@pytest.fixture
def settings_path(tmp_path: Path) -> Path:
    """Provide a settings.json path inside a temporary .claude directory.

    Args:
        tmp_path: Pytest-provided temporary directory.

    Returns:
        Path to a (not-yet-created) settings.json file.
    """
    return tmp_path / ".claude" / "settings.json"


def _write_settings(settings_path: Path, data: dict) -> None:
    """Write a settings dictionary to disk as JSON.

    Args:
        settings_path: Destination settings.json path.
        data: Settings dictionary to serialize.

    Returns:
        None
    """
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(data, indent=2) + "\n")


class TestMainEnvBlock:
    """Tests for the AI_AGENT_ENV_PATH env pin written by main()."""

    def test_main_writes_env_block_with_absolute_path(
        self, settings_path: Path
    ) -> None:
        """Writes an env block pinning AI_AGENT_ENV_PATH to the repo's absolute path."""
        merge_global_settings.main(settings_path)

        settings = json.loads(settings_path.read_text())
        env_value = settings["env"]["AI_AGENT_ENV_PATH"]

        assert env_value == str(merge_global_settings.REPO_ROOT)
        assert Path(env_value).is_absolute()

    def test_main_env_path_derived_from_script_location_not_env_var(
        self, settings_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pins the path from the script location even if the env var is unset/empty."""
        # The whole point of the pin is to not depend on the env var being set.
        monkeypatch.delenv("AI_AGENT_ENV_PATH", raising=False)

        merge_global_settings.main(settings_path)

        settings = json.loads(settings_path.read_text())
        expected_root = str(
            Path(merge_global_settings.__file__).resolve().parent.parent
        )
        assert settings["env"]["AI_AGENT_ENV_PATH"] == expected_root


class TestMainPreservesExistingKeys:
    """Tests that main() preserves unrelated pre-existing settings."""

    def test_main_preserves_top_level_keys(self, settings_path: Path) -> None:
        """Preserves pre-existing top-level keys like theme, tui, and statusLine."""
        _write_settings(
            settings_path,
            {
                "theme": "dark",
                "tui": {"foo": "bar"},
                "statusLine": {"type": "command", "command": "echo hi"},
            },
        )

        merge_global_settings.main(settings_path)

        settings = json.loads(settings_path.read_text())
        assert settings["theme"] == "dark"
        assert settings["tui"] == {"foo": "bar"}
        assert settings["statusLine"] == {"type": "command", "command": "echo hi"}
        # And the new content is present.
        assert "hooks" in settings
        assert settings["env"]["AI_AGENT_ENV_PATH"] == str(
            merge_global_settings.REPO_ROOT
        )

    def test_main_preserves_other_env_keys(self, settings_path: Path) -> None:
        """Preserves other keys inside a pre-existing env block; only sets the pin."""
        _write_settings(
            settings_path,
            {
                "env": {
                    "SOME_OTHER_VAR": "keep-me",
                    "AI_AGENT_ENV_PATH": "/old/stale/path",
                }
            },
        )

        merge_global_settings.main(settings_path)

        settings = json.loads(settings_path.read_text())
        assert settings["env"]["SOME_OTHER_VAR"] == "keep-me"
        # The stale AI_AGENT_ENV_PATH is overwritten with the resolved repo root.
        assert settings["env"]["AI_AGENT_ENV_PATH"] == str(
            merge_global_settings.REPO_ROOT
        )

    def test_main_replaces_hooks_key(self, settings_path: Path) -> None:
        """Overwrites any pre-existing hooks with the canonical HOOKS definition."""
        _write_settings(settings_path, {"hooks": {"StaleEvent": [{"hooks": []}]}})

        merge_global_settings.main(settings_path)

        settings = json.loads(settings_path.read_text())
        assert settings["hooks"] == merge_global_settings.HOOKS
        assert "StaleEvent" not in settings["hooks"]


class TestMainHookCommands:
    """Tests for the absolute-path hook command strings (no env-var expansion)."""

    def test_hook_commands_use_absolute_path_and_no_env_var(
        self, settings_path: Path
    ) -> None:
        """Every emitted hook command embeds the absolute repo path and has no '$'."""
        merge_global_settings.main(settings_path)

        settings = json.loads(settings_path.read_text())
        repo_root = str(merge_global_settings.REPO_ROOT)

        assert len(settings["hooks"]) == 7
        for event, definitions in settings["hooks"].items():
            for group in definitions:
                for hook in group["hooks"]:
                    command = hook["command"]
                    assert "$" not in command, (
                        f"{event} command contains '$': {command}"
                    )
                    assert repo_root in command, (
                        f"{event} command missing repo root: {command}"
                    )
                    assert command.startswith('python3 "'), event

    def test_pretooluse_command_string_and_matcher(self, settings_path: Path) -> None:
        """PreToolUse keeps its matcher and emits the exact absolute command path."""
        merge_global_settings.main(settings_path)

        settings = json.loads(settings_path.read_text())
        pre = settings["hooks"]["PreToolUse"][0]

        assert pre["matcher"] == "Bash|Read|Write|Edit"
        command = pre["hooks"][0]["command"]
        expected = f'python3 "{merge_global_settings.REPO_ROOT}/hooks/pre_tool_use.py"'
        assert command == expected
        assert "$" not in command


class TestMainIdempotency:
    """Tests that re-running main() is idempotent."""

    def test_main_idempotent_on_rerun(self, settings_path: Path) -> None:
        """Running twice yields identical content with no duplicated hook entries."""
        merge_global_settings.main(settings_path)
        first = settings_path.read_text()

        merge_global_settings.main(settings_path)
        second = settings_path.read_text()

        assert first == second
        settings = json.loads(second)
        # Each event maps to exactly one matcher/hook group — no appended duplicates.
        for event, definitions in settings["hooks"].items():
            assert len(definitions) == 1, event


class TestMainCorruptFile:
    """Tests for the non-destructive corrupt-file handling."""

    def test_main_backs_up_and_exits_on_corrupt_json(self, settings_path: Path) -> None:
        """Backs up an unparseable file and exits non-zero instead of rebuilding."""
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        corrupt = '{"theme": "dark", "tui": {'  # truncated / invalid JSON
        settings_path.write_text(corrupt)

        with pytest.raises(SystemExit) as exc_info:
            merge_global_settings.main(settings_path)

        assert exc_info.value.code == 1

        # The original (corrupt) file is left untouched — NOT rebuilt hooks-only.
        assert settings_path.read_text() == corrupt

        # A backup with the exact original bytes exists alongside it.
        backup_path = settings_path.with_name(
            settings_path.name + merge_global_settings.BACKUP_SUFFIX
        )
        assert backup_path.read_text() == corrupt

    def test_main_returns_empty_when_file_absent(self, settings_path: Path) -> None:
        """Creates fresh settings (hooks + env) when no file exists yet."""
        assert not settings_path.exists()

        merge_global_settings.main(settings_path)

        settings = json.loads(settings_path.read_text())
        assert set(settings.keys()) == {"hooks", "env"}

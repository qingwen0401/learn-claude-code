"""Regression tests for the s15 config/bootstrap contract.

These tests lock the *public* module-level interface that
``s15_integrated_harness/code.py`` exposes (paths, model ids, runtime limits,
client bootstrap, env cleanup). They intentionally never assert on code text,
line numbers, or which file a name lives in, so the config/bootstrap layer can
be extracted or moved without invalidating the tests.

Loading follows the same convention as tests/test_task_system.py and
tests/test_agent_teams_runtime.py: the lesson is executed by path through
importlib, with stub ``anthropic``/``dotenv``/``yaml`` modules, from a
temporary working directory, and with ``MODEL_ID=test-model``. No network
calls are made and no API key is required.
"""

import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
LESSON = ROOT / "s15_integrated_harness" / "code.py"


def load_lesson(workdir: Path):
    fake_anthropic = types.ModuleType("anthropic")
    fake_dotenv = types.ModuleType("dotenv")
    fake_yaml = types.ModuleType("yaml")
    dotenv_calls: list[tuple[tuple, dict]] = []

    class FakeAnthropic:
        instances: list = []

        def __init__(self, *args, **kwargs):
            self.messages = types.SimpleNamespace(create=None)
            self.init_args = args
            self.init_kwargs = kwargs
            FakeAnthropic.instances.append(self)

    def fake_load_dotenv(*args, **kwargs):
        dotenv_calls.append((args, kwargs))
        return None

    fake_anthropic.Anthropic = FakeAnthropic
    fake_dotenv.load_dotenv = fake_load_dotenv
    fake_yaml.safe_load = lambda value: {}
    fake_yaml.YAMLError = ValueError

    previous_modules = {
        "anthropic": sys.modules.get("anthropic"),
        "dotenv": sys.modules.get("dotenv"),
        "yaml": sys.modules.get("yaml"),
    }
    previous_cwd = Path.cwd()
    previous_model = os.environ.get("MODEL_ID")

    module_name = f"s15_config_contract_{id(workdir)}_{len(dotenv_calls)}"
    spec = importlib.util.spec_from_file_location(module_name, LESSON)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)

    sys.modules["anthropic"] = fake_anthropic
    sys.modules["dotenv"] = fake_dotenv
    sys.modules["yaml"] = fake_yaml
    sys.modules[module_name] = module
    try:
        os.chdir(workdir)
        os.environ["MODEL_ID"] = "test-model"
        spec.loader.exec_module(module)
        return types.SimpleNamespace(
            module=module,
            cwd=Path.cwd(),
            dotenv_calls=dotenv_calls,
            anthropic=fake_anthropic,
        )
    finally:
        os.chdir(previous_cwd)
        sys.modules.pop(module_name, None)
        if previous_model is None:
            os.environ.pop("MODEL_ID", None)
        else:
            os.environ["MODEL_ID"] = previous_model
        for name, previous in previous_modules.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def test_workdir_is_a_path_equal_to_the_load_time_cwd(tmp_path: Path) -> None:
    loaded = load_lesson(tmp_path)

    assert isinstance(loaded.module.WORKDIR, Path)
    assert loaded.module.WORKDIR == loaded.cwd
    assert loaded.cwd == tmp_path.resolve()


def test_model_ids_keep_their_public_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FALLBACK_MODEL_ID", raising=False)
    loaded = load_lesson(tmp_path)

    assert isinstance(loaded.module.MODEL, str)
    assert loaded.module.MODEL == "test-model"
    assert loaded.module.PRIMARY_MODEL == loaded.module.MODEL
    assert hasattr(loaded.module, "FALLBACK_MODEL")
    assert loaded.module.FALLBACK_MODEL is None


def test_workspace_directories_derive_from_workdir(tmp_path: Path) -> None:
    loaded = load_lesson(tmp_path)
    workdir = loaded.module.WORKDIR

    assert loaded.module.SKILLS_DIR == workdir / "skills"
    assert loaded.module.TRANSCRIPT_DIR == workdir / ".transcripts"
    assert loaded.module.TOOL_RESULTS_DIR == (
        workdir / ".task_outputs" / "tool-results"
    )


def test_runtime_limits_keep_their_current_values(tmp_path: Path) -> None:
    loaded = load_lesson(tmp_path)

    assert loaded.module.DEFAULT_MAX_TOKENS == 8000
    assert loaded.module.ESCALATED_MAX_TOKENS == 16000
    assert loaded.module.MAX_RETRIES == 3
    assert loaded.module.MAX_CONSECUTIVE_529 == 2
    assert loaded.module.MAX_RECOVERY_RETRIES == 2
    assert loaded.module.BASE_DELAY_MS == 500
    assert loaded.module.CONTEXT_LIMIT == 50000
    assert loaded.module.KEEP_RECENT_TOOL_RESULTS == 3
    assert loaded.module.PERSIST_THRESHOLD == 30000


def test_client_is_the_configured_anthropic_instance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://example.invalid")
    loaded = load_lesson(tmp_path)

    client = loaded.module.client
    assert isinstance(client, loaded.anthropic.Anthropic)
    assert client.init_kwargs.get("base_url") == "https://example.invalid"


def test_load_dotenv_is_called_with_override(tmp_path: Path) -> None:
    loaded = load_lesson(tmp_path)

    assert loaded.dotenv_calls, "load_dotenv was never called"
    assert all(
        kwargs.get("override") is True
        for _args, kwargs in loaded.dotenv_calls
    )


def test_auth_token_is_dropped_when_base_url_is_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://example.invalid")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "secret-token")

    load_lesson(tmp_path)

    assert "ANTHROPIC_AUTH_TOKEN" not in os.environ


def test_auth_token_survives_without_base_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "secret-token")

    load_lesson(tmp_path)

    assert os.environ.get("ANTHROPIC_AUTH_TOKEN") == "secret-token"

"""Regression tests for the s15 permission-hook contract.

These tests lock the *public* behaviour of ``permission_hook`` and the
``DENY_LIST`` constant that ``s15_integrated_harness/code.py`` exposes: deny
listed shell patterns, reject non-string command/path inputs, reject paths
outside the workspace, allow in-workspace paths, refuse interactive approval
from worker threads, and honour a non-approving user answer.

They intentionally never assert on code text, line numbers, or which file the
permission layer lives in, so it can be extracted into its own module without
invalidating the tests. Loading follows the same convention as
tests/test_task_system.py and tests/test_agent_teams_runtime.py: executed by
path through importlib, with stub ``anthropic``/``dotenv``/``yaml`` modules,
from a temporary working directory, and ``MODEL_ID=test-model``. No network
calls are made and no API key is required.
"""

import importlib.util
import os
import sys
import threading
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
LESSON = ROOT / "s15_integrated_harness" / "code.py"

DENY_LIST = ["rm -rf /", "sudo", "shutdown", "reboot", "mkfs", "dd if="]


def load_lesson(workdir: Path):
    fake_anthropic = types.ModuleType("anthropic")
    fake_dotenv = types.ModuleType("dotenv")
    fake_yaml = types.ModuleType("yaml")

    class FakeAnthropic:
        def __init__(self, *args, **kwargs):
            self.messages = types.SimpleNamespace(create=None)

    fake_anthropic.Anthropic = FakeAnthropic
    fake_dotenv.load_dotenv = lambda override=True: None
    fake_yaml.safe_load = lambda value: {}
    fake_yaml.YAMLError = ValueError

    previous_modules = {
        "anthropic": sys.modules.get("anthropic"),
        "dotenv": sys.modules.get("dotenv"),
        "yaml": sys.modules.get("yaml"),
    }
    previous_cwd = Path.cwd()
    previous_model = os.environ.get("MODEL_ID")

    module_name = f"s15_permission_contract_{id(workdir)}"
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
        return module
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


def block(name: str, **inputs):
    return types.SimpleNamespace(name=name, input=inputs)


def test_deny_list_keeps_its_public_contents(tmp_path: Path) -> None:
    lesson = load_lesson(tmp_path)

    assert lesson.DENY_LIST == DENY_LIST


@pytest.mark.parametrize("pattern", DENY_LIST)
def test_bash_deny_list_patterns_are_denied(
    tmp_path: Path, pattern: str
) -> None:
    lesson = load_lesson(tmp_path)

    result = lesson.permission_hook(
        block("bash", command=f"echo safe && {pattern}")
    )

    assert isinstance(result, str)
    assert result.startswith("Permission denied")


def test_bash_with_non_string_command_is_denied(tmp_path: Path) -> None:
    lesson = load_lesson(tmp_path)

    result = lesson.permission_hook(block("bash", command=123))

    assert isinstance(result, str)
    assert result.startswith("Permission denied")


@pytest.mark.parametrize("tool", ["read_file", "write_file", "edit_file"])
def test_file_tools_reject_a_non_string_path(
    tmp_path: Path, tool: str
) -> None:
    lesson = load_lesson(tmp_path)

    result = lesson.permission_hook(block(tool, path=123))

    assert isinstance(result, str)
    assert result.startswith("Permission denied")


@pytest.mark.parametrize("tool", ["read_file", "write_file", "edit_file"])
def test_file_tools_reject_paths_outside_the_workspace(
    tmp_path: Path, tool: str
) -> None:
    lesson = load_lesson(tmp_path)
    outside = tmp_path.parent / "other"

    result = lesson.permission_hook(block(tool, path=str(outside)))

    assert isinstance(result, str)
    assert result.startswith("Permission denied")


@pytest.mark.parametrize(
    "tool,extra",
    [("read_file", {}), ("write_file", {"content": "x"}),
     ("edit_file", {"old_text": "a", "new_text": "b"})],
)
def test_file_tools_allow_paths_inside_the_workspace(
    tmp_path: Path, tool: str, extra: dict
) -> None:
    lesson = load_lesson(tmp_path)

    assert lesson.permission_hook(
        block(tool, path="notes.txt", **extra)
    ) is None


def test_bash_from_a_worker_thread_has_no_approval_channel(
    tmp_path: Path,
) -> None:
    lesson = load_lesson(tmp_path)
    results: list = []

    def call_hook() -> None:
        results.append(
            lesson.permission_hook(block("bash", command="echo hi"))
        )

    worker = threading.Thread(target=call_hook)
    worker.start()
    worker.join(timeout=5)

    assert not worker.is_alive()
    assert len(results) == 1
    assert isinstance(results[0], str)
    assert results[0].startswith("Permission denied")


@pytest.mark.parametrize("answer", ["no", "n", ""])
def test_bash_is_denied_when_the_user_does_not_approve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, answer: str
) -> None:
    lesson = load_lesson(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: answer)

    result = lesson.permission_hook(block("bash", command="echo hi"))

    assert result == "Permission denied by user"

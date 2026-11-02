import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from ms_toolbox.catalog import load_catalog
from ms_toolbox.installations import Installation
from ms_toolbox.launch import LaunchManager


def test_late_process_failure_is_reported_with_log(qapp, tmp_path, monkeypatch):
    launcher = LaunchManager(tmp_path)
    proc = SimpleNamespace(poll=lambda: None)
    def spawn(command, **kwargs):
        assert command[1:4] == ["-I", "-m", "amdockvs"]
        assert command[-2:] == ["--project-id", "project-id"]
        kwargs["stderr"]  # stderr shares the log file, not a potentially blocking pipe.
        kwargs["stdout"].write(b"missing chemistry dependency\n")
        return proc
    monkeypatch.setattr("ms_toolbox.launch.subprocess.Popen", spawn)
    failures = []
    launcher.failed.connect(lambda app_id, message: failures.append((app_id, message)))
    state = Installation(Path(sys.executable), "0.8.1", "Linked")
    launcher.start(load_catalog()["amdockvs"], state, "project-id")
    launcher.poll()
    assert not failures
    proc.poll = lambda: 1
    launcher.poll()
    assert failures[0][0] == "amdockvs"
    assert "missing chemistry dependency" in failures[0][1]
    assert not launcher.processes


def test_real_failed_child_is_observed_after_creation(qapp, tmp_path):
    app = replace(load_catalog()["amdockvs"], package="ms_toolbox_deliberately_absent_app")
    manager = LaunchManager(tmp_path)
    errors = []
    manager.failed.connect(lambda _, message: errors.append(message))
    proc = manager.start(app, Installation(Path(sys.executable), "1", "Linked"), "p1")
    assert proc.wait(timeout=10) != 0
    manager.poll()
    assert len(errors) == 1 and "No module named" in errors[0]


def test_no_process_is_created_for_a_missing_installation(qapp, tmp_path):
    manager = LaunchManager(tmp_path)
    with pytest.raises(RuntimeError, match="not installed"):
        manager.start(load_catalog()["amdockvs"], Installation(), "p1")
    assert not tmp_path.joinpath("logs").exists()

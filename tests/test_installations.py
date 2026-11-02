import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from ms_toolbox.catalog import load_catalog
from ms_toolbox.installations import Installations, app_environment, bridge_call


def test_source_checkout_is_not_an_installation(tmp_path, monkeypatch):
    installations = Installations(tmp_path)
    probe = Mock(return_value={"version": "", "error": ""})
    monkeypatch.setattr("ms_toolbox.installations.bridge_call", probe)
    state = installations.inspect(load_catalog()["amdockvs"])
    assert not state.available
    assert state.kind == "Not installed"
    assert probe.call_count == 1
    assert probe.call_args.args[0] == Path(sys.executable)


def test_only_the_explicitly_linked_environment_is_checked(tmp_path, monkeypatch):
    app = load_catalog()["amdockvs"]
    python = tmp_path / "chosen-python"
    python.touch()
    probe = Mock(return_value={"version": "0.8.0", "error": ""})
    monkeypatch.setattr("ms_toolbox.installations.bridge_call", probe)
    installations = Installations(tmp_path / "toolbox")
    installations.link(app, python)
    restored = Installations(installations.home)
    state = restored.inspect(app)
    assert state.available and state.kind == "Linked"
    assert state.python == python
    assert probe.call_args.args[0] == python
    restored.unlink(app.app_id)
    assert python.exists()


def test_failed_link_does_not_replace_a_working_registry(tmp_path, monkeypatch):
    installations = Installations(tmp_path)
    installations._save({"amdockvs": "/known/python"})
    monkeypatch.setattr("ms_toolbox.installations.bridge_call", lambda *_: {"version": "", "error": ""})
    with pytest.raises(ValueError):
        installations.link(load_catalog()["amdockvs"], tmp_path / "other")
    assert json.loads(installations.path.read_text()) == {"amdockvs": "/known/python"}


def test_missing_link_is_reported_instead_of_falling_back(tmp_path):
    installations = Installations(tmp_path)
    installations._save({"amdockvs": str(tmp_path / "gone")})
    state = installations.inspect(load_catalog()["amdockvs"])
    assert not state.available
    assert "no longer exists" in state.error


def test_bridge_timeout_and_stderr_are_visible(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr("ms_toolbox.installations.subprocess.run", lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="broken interpreter"))
    with pytest.raises(RuntimeError, match="broken interpreter"):
        bridge_call(tmp_path / "python", {"action": "probe"})


def test_other_environment_does_not_inherit_source_or_qt_paths(tmp_path, monkeypatch):
    for key in ("PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
        monkeypatch.setenv(key, "/wrong/environment")
    env = app_environment(tmp_path / "bin/python")
    assert "PYTHONPATH" not in env and "QT_PLUGIN_PATH" not in env
    assert env["PATH"].startswith(str(tmp_path / "bin"))


def test_uninstall_delegates_only_to_ms_env_and_preserves_projects(tmp_path, monkeypatch):
    installations = Installations(tmp_path / "toolbox")
    project = tmp_path / "project/data.txt"
    project.parent.mkdir()
    project.write_text("keep")
    remove = Mock(return_value=True)
    monkeypatch.setattr("ms_toolbox.installations.remove", remove)
    installations.remove(load_catalog()["amdockvs"])
    assert remove.call_args.args[0].prefix == str(installations.home / "apps/amdockvs")
    assert project.read_text() == "keep"

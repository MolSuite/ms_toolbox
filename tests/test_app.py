import sys

import pytest

from ms_toolbox.app import install_desktop_entry


def test_desktop_shortcut_points_to_the_selected_python_with_spaces(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "executable", "/chosen environment/bin/python")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert install_desktop_entry() == 0
    entry = (tmp_path / "applications/ms-toolbox.desktop").read_text()
    assert 'Exec="/chosen environment/bin/python" -m ms_toolbox' in entry
    assert "Terminal=false" in entry
    assert (tmp_path / "icons/hicolor/scalable/apps/ms-toolbox.svg").exists()


def test_desktop_exec_handles_both_string_and_argument_escaping(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "executable", '/chosen $env"\\name%/python')
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    install_desktop_entry()
    entry = (tmp_path / "applications/ms-toolbox.desktop").read_text()
    assert r"\\$" in entry and r'\\"' in entry and r"\\\\" in entry and "%%" in entry


def test_desktop_exec_rejects_paths_that_cannot_be_represented(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "executable", "/invalid=path/python")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    with pytest.raises(SystemExit, match="Python path"):
        install_desktop_entry()

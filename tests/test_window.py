from datetime import datetime
from types import SimpleNamespace

from PySide6.QtCore import QElapsedTimer, QThread
from PySide6.QtWidgets import QMessageBox
from ms_flow.core.settings.manager import SettingsManager

from ms_toolbox.catalog import load_catalog
from ms_toolbox.installations import Installation, Installations
from ms_toolbox.window import ToolboxWindow
from ms_toolbox.projects import APP_COLUMN


class Backend:
    def __init__(self, home):
        self.catalog = SimpleNamespace(settings_manager=SettingsManager())
        self.catalog.settings_manager.global_dir = home
        self.available_apps = set()
        self.raw = SimpleNamespace(id="p1", name="Kept project", description="", path=str(home / "project"), updated_at=datetime.now(), app_id="amdockvs", favorite=False, tags="")

    def list_apps(self):
        return [load_catalog()["amdockvs"].manifest()] if "amdockvs" in self.available_apps else []

    def get_app_manifest(self, app_id):
        return load_catalog()["amdockvs"].manifest() if app_id == "amdockvs" else None

    def get_total_projects(self):
        return 1

    def list_projects(self, *args):
        return [self.raw]

    def parse_tags(self, tags):
        return []

    def get_project(self, project_id):
        return self.raw

    def shutdown(self):
        pass


def drain(qapp, window):
    timer = QElapsedTimer()
    timer.start()
    while window._workers and timer.elapsed() < 5000:
        qapp.processEvents()
        QThread.msleep(1)
    assert not window._workers


def test_missing_app_keeps_projects_and_double_click_selects_apps(qapp, tmp_path, monkeypatch):
    backend = Backend(tmp_path)
    installations = Installations(tmp_path / "toolbox")
    monkeypatch.setattr(installations, "inspect", lambda _: Installation())
    errors = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: errors.append(args[-1]))
    window = ToolboxWindow(backend=backend, installations=installations)
    drain(qapp, window)
    assert window.projects.get_total_projects() == 1
    assert not window.projects.new_button.isEnabled()
    assert not window.projects.project_tree.view.isColumnHidden(APP_COLUMN)
    window.hosts_page._show("local")
    assert "cpus" in window.hosts_page._editors and "gpus" in window.hosts_page._editors
    assert window.workspace.settings_manager is backend.catalog.settings_manager
    window.sidebar.setCurrentRow(1)
    assert window.projects.project_tree.view.isColumnHidden(APP_COLUMN)
    window.open_project("p1")
    drain(qapp, window)
    assert window.tabs.currentWidget() is window.tools_page
    assert "not installed" in errors[0]
    assert backend.raw.name == "Kept project"
    window.close()

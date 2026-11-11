from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt

from ms_toolbox.catalog import load_catalog
from ms_toolbox.projects import APP_COLUMN, ToolboxBackend, ToolboxProjectModel
from ms_components.ms_projects.browser import ProjectItem


def test_all_projects_show_the_app_and_keep_the_correct_path_header(qapp):
    model = ToolboxProjectModel()
    model.load([ProjectItem(id="p1", name="Same name", description="", path="/one", last_modified="today", app_id="amdockvs", language="AMDockVS")])
    assert model.data(model.index(0, APP_COLUMN)) == "AMDockVS"
    assert model.headerData(2, Qt.Horizontal) == "Path"
    assert model.headerData(3, Qt.Horizontal) == "Modified"


def test_legacy_unassigned_projects_can_be_scoped_without_showing_other_apps(qapp):
    model = ToolboxProjectModel()
    model.load([
        ProjectItem(id="p1", name="Legacy", description="", path="/one", last_modified="today"),
        ProjectItem(id="p2", name="Docking", description="", path="/two", last_modified="today", app_id="amdockvs"),
    ])
    model.set_scope("")
    assert model.rowCount() == 1 and model.project_at(0).id == "p1"
    model.set_scope(None)
    assert model.rowCount() == 2


def test_backend_does_not_discover_workspace_apps_or_create_for_missing_apps(monkeypatch):
    init = []
    monkeypatch.setattr("ms_flow.api.ProjectCatalogBackend.__init__", lambda self, **kwargs: init.append(kwargs))
    backend = ToolboxBackend(load_catalog())
    assert init[0]["discover_apps"] is False
    with pytest.raises(ValueError, match="Install or link"):
        backend.create_project(app_id="amdockvs", name="test")

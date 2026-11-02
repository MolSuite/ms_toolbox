from __future__ import annotations

import hashlib

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHeaderView
from ms_components.ms_projects.browser import ProjectTableModel
from ms_components.ms_projects import ProjectsMenuWidget
from ms_flow.api import ProjectCatalogBackend

APP_COLUMN = 6


class ToolboxBackend(ProjectCatalogBackend):
    def __init__(self, apps):
        self.available_apps = set()
        super().__init__(discover_apps=False, manifests=[app.manifest() for app in apps.values()])

    def list_apps(self):
        return [app for app in super().list_apps() if app.app_id in self.available_apps]

    def create_project(self, **kwargs):
        if kwargs.get("app_id") not in self.available_apps:
            raise ValueError("Install or link the app before creating a project.")
        return super().create_project(**kwargs)


class ToolboxProjectModel(ProjectTableModel):
    HEADERS = ["Project", "Description", "Path", "Modified", "", "", "Application"]

    def columnCount(self, parent=QModelIndex()):
        return 7

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid() and index.column() == APP_COLUMN and role in (Qt.DisplayRole, Qt.ToolTipRole):
            project = self.project_at(index.row())
            return project.language or project.app_id or "Unknown app"
        return super().data(index, role)

    def _rebuild(self):
        super()._rebuild()
        if self._scope == "":
            self._visible = [project for project in self._visible if not project.app_id]
        if self._sort_col == APP_COLUMN:
            self._visible.sort(key=lambda p: (p.language or p.app_id).lower(), reverse=not self._sort_asc)


class ToolboxProjects(ProjectsMenuWidget):
    def __init__(self, *, apps, backend, parent=None):
        self.apps = apps
        super().__init__(backend=backend, title="Projects", parent=parent)
        tree = self.project_tree
        old_model = tree.model
        tree.model = ToolboxProjectModel(tree)
        tree.view.setModel(tree.model)
        tree.model.modelReset.connect(tree._update_count)
        old_model.deleteLater()
        header = tree.view.header()
        header.setSectionResizeMode(APP_COLUMN, QHeaderView.ResizeToContents)
        header.moveSection(header.visualIndex(APP_COLUMN), 1)
        self.refresh()

    def _build_color_map(self):
        self._app_color_map = {app.app_id: app.color for app in self.apps.values()}

    def _color_for_app(self, app_id):
        if app_id in self._app_color_map:
            return self._app_color_map[app_id]
        hue = int.from_bytes(hashlib.sha256(app_id.encode()).digest()[:2]) % 360
        return QColor.fromHsv(hue, 150, 210).name()

    def refresh(self):
        super().refresh()
        if isinstance(self.project_tree.model, ToolboxProjectModel):
            self.project_tree.view.setColumnHidden(APP_COLUMN, self.app_id is not None)
        self.new_button.setEnabled(bool(self._available_apps_for_dialog()))

    def _available_apps_for_dialog(self):
        apps = self.backend.list_apps()
        return apps if self.app_id is None else [app for app in apps if app.app_id == self.app_id]

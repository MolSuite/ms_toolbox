from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, QThread, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
    QSplitter, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from ms_components.ms_settings import AppSettingsPanel
from ms_components.ms_executors import KeptPage
from ms_components.theme import apply_theme, font
from ms_flow.api import Workspace

from ms_toolbox.catalog import load_catalog
from ms_toolbox.installations import Installations
from ms_toolbox.launch import LaunchManager
from ms_toolbox.projects import ToolboxBackend, ToolboxProjects
from ms_toolbox.settings import AppConfiguration, toolbox_configuration


class Worker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, function, parent):
        super().__init__(parent)
        self.function = function

    def run(self):
        try:
            result = self.function()
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.completed.emit(result)


class SettingsPanel(AppSettingsPanel):
    def reload_values(self):
        try:
            for configuration in self._configurations.values():
                if isinstance(configuration, AppConfiguration):
                    configuration.reload()
        except Exception as exc:
            QMessageBox.critical(self, "Reload settings", str(exc))
            return
        super().reload_values()


def app_icon(color, initial):
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(1, 1, 30, 30, 8, 8)
    painter.setPen(QColor("#102030") if QColor(color).lightness() > 150 else QColor("white"))
    painter.setFont(font("strong"))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, initial)
    painter.end()
    return QIcon(pixmap)


class ToolboxWindow(QMainWindow):
    def __init__(self, *, apps=None, backend=None, installations=None):
        super().__init__()
        self.apps = load_catalog() if apps is None else apps
        self.backend = backend if backend is not None else ToolboxBackend(self.apps)
        self.settings_manager = self.backend.catalog.settings_manager
        self.workspace = Workspace(app_id="ms_toolbox")
        self.workspace.settings_manager = self.settings_manager
        self.home = self.settings_manager.global_dir / "toolbox"
        self.configuration = toolbox_configuration(self.home)
        self.installations = installations if installations is not None else Installations(self.home)
        self.launcher = LaunchManager(self.home / "logs", self)
        self.launcher.failed.connect(self._launch_failed)
        self.launcher.finished.connect(lambda app_id: self.statusBar().showMessage(f"{self._app_name(app_id)} closed.", 5000))
        self.states = {}
        self._workers = set()
        self._install = None
        self._install_app = None
        self._settings_pages = {}
        self.setWindowTitle("MolSuite Toolbox")
        self.resize(1200, 780)
        self.apply_appearance()
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 16, 20, 16)
        title = QLabel("MolSuite Toolbox", root)
        title.setFont(font("title"))
        layout.addWidget(title)
        description = QLabel("Your applications, projects and settings.", root)
        description.setStyleSheet("color: palette(placeholder-text);")
        layout.addWidget(description)
        self.tabs = QTabWidget(root)
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(root)

        projects_page = QSplitter(self)
        self.sidebar = QListWidget(projects_page)
        self.sidebar.setMinimumWidth(200)
        self.sidebar.setIconSize(QSize(28, 28))
        self.sidebar.setSpacing(3)
        self.sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sidebar.currentItemChanged.connect(self._select_scope)
        self.projects = ToolboxProjects(apps=self.apps, backend=self.backend, parent=projects_page)
        self.projects.project_requested.connect(self.open_project)
        self.projects.project_created.connect(lambda _id: self._populate_sidebar())
        self.projects.refresh_button.clicked.connect(self._populate_sidebar)
        projects_page.addWidget(self.sidebar)
        projects_page.addWidget(self.projects)
        projects_page.setStretchFactor(1, 1)
        projects_page.setSizes([230, 930])
        self.tabs.addTab(projects_page, "Projects")

        self.tools_page = QWidget(self)
        tools_layout = QVBoxLayout(self.tools_page)
        heading = QHBoxLayout()
        hint = QLabel("Reviewed apps. Link an existing Python or install into a Toolbox-owned environment.")
        hint.setWordWrap(True)
        heading.addWidget(hint, 1)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        heading.addWidget(self.refresh_button)
        tools_layout.addLayout(heading)
        self.tools = QTableWidget(0, 5, self)
        self.tools.setHorizontalHeaderLabels(["Application", "Installed version", "Catalog version", "Status", "Python"])
        self.tools.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tools.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tools.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tools.verticalHeader().hide()
        self.tools.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tools.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.tools.itemSelectionChanged.connect(self._update_actions)
        tools_layout.addWidget(self.tools, 1)
        self.tool_description = QLabel(self)
        self.tool_description.setWordWrap(True)
        tools_layout.addWidget(self.tool_description)
        actions = QHBoxLayout()
        self.install_button = QPushButton("Install catalog version")
        self.link_button = QPushButton("Link Python…")
        self.unlink_button = QPushButton("Unlink")
        self.remove_button = QPushButton("Uninstall managed app")
        self.repository_button = QPushButton("Repository")
        for button, callback in (
            (self.install_button, self.install_selected), (self.link_button, self.link_selected),
            (self.unlink_button, self.unlink_selected), (self.remove_button, self.remove_selected),
            (self.repository_button, self.open_repository),
        ):
            button.clicked.connect(callback)
            actions.addWidget(button)
        actions.addStretch()
        tools_layout.addLayout(actions)
        self.install_log = QPlainTextEdit(self)
        self.install_log.setReadOnly(True)
        self.install_log.setMaximumBlockCount(1000)
        self.install_log.setMaximumHeight(170)
        self.install_log.hide()
        tools_layout.addWidget(self.install_log)
        self.tabs.addTab(self.tools_page, "Apps")

        self.settings_tabs = QTabWidget(self)
        global_page = QWidget(self)
        global_layout = QVBoxLayout(global_page)
        global_layout.addWidget(QLabel("Global settings. Changes to the project catalog path apply after restarting Toolbox."))
        self.global_settings = AppSettingsPanel(
            configurations=[self.configuration, self.settings_manager], app_name="MolSuite", parent=self,
        )
        self.global_settings.settings_saved.connect(self.apply_appearance)
        self.hosts_page = KeptPage(self.workspace, "hosts", parent=self)
        self.executors_page = KeptPage(self.workspace, "executors", parent=self)
        self.global_settings.add_page(self.hosts_page, "Hosts")
        self.global_settings.add_page(self.executors_page, "Executors")
        global_layout.addWidget(self.global_settings)
        self.settings_tabs.addTab(global_page, "MolSuite")
        self.settings_tabs.currentChanged.connect(self._load_settings)
        self.tabs.addTab(self.settings_tabs, "Settings")

        self.install_timer = QTimer(self)
        self.install_timer.setInterval(300)
        self.install_timer.timeout.connect(self._poll_install)

    def apply_appearance(self):
        apply_theme(self.configuration.get_value("appearance.theme"), base_font_pt=self.configuration.get_value("appearance.font_size"))

    def _run(self, function, on_success, on_error=None):
        worker = Worker(function, self)
        self._workers.add(worker)
        worker.completed.connect(on_success)
        worker.failed.connect(on_error or self._error)
        def finished():
            self._workers.discard(worker)
            self.refresh_button.setEnabled(not self._workers and self._install is None)
            self._update_actions()
        worker.finished.connect(finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()
        self._update_actions()

    def _error(self, message):
        QMessageBox.critical(self, "MolSuite Toolbox", message)

    def _app_name(self, app_id):
        return self.apps[app_id].name if app_id in self.apps else app_id or "Unknown app"

    def refresh(self):
        self.refresh_button.setEnabled(False)
        self.statusBar().showMessage("Checking registered applications…")
        self._populate_sidebar()
        self._run(lambda: {key: self.installations.inspect(app) for key, app in self.apps.items()}, self._refreshed)

    def _refreshed(self, states):
        self.states = states
        self.backend.available_apps = {key for key, state in states.items() if state.available}
        self.projects.refresh()
        self._populate_sidebar()
        previous = self.selected_app()
        self.tools.setRowCount(len(self.apps))
        for row, app in enumerate(self.apps.values()):
            state = states[app.app_id]
            status = "Unavailable" if state.error else state.kind
            for col, text in enumerate((app.name, state.version or "—", app.version, status, str(state.python or ""))):
                item = QTableWidgetItem(text)
                item.setData(Qt.UserRole, app.app_id)
                item.setToolTip(state.error or text)
                self.tools.setItem(row, col, item)
            self.tools.item(row, 0).setIcon(app_icon(app.color, app.initial))
        if self.apps:
            keys = list(self.apps)
            self.tools.selectRow(keys.index(previous.app_id) if previous else 0)
        self._rebuild_settings_tabs()
        self._update_actions()
        self.statusBar().showMessage("Ready", 3000)

    def _populate_sidebar(self):
        current = self.sidebar.currentItem()
        selected = current.data(Qt.UserRole) if current else None
        self.sidebar.blockSignals(True)
        self.sidebar.clear()
        counts = self.projects.project_tree.counts_by_app()
        entries = [(None, f"All apps  ·  {sum(counts.values())}")]
        for app_id in sorted(set(self.apps) | set(counts), key=lambda key: self._app_name(key).lower()):
            state = self.states.get(app_id)
            status = "available" if state and state.available else "unavailable" if state and state.error else "not installed"
            entries.append((app_id, f"{self._app_name(app_id)}\n{counts.get(app_id, 0)} projects · {status}"))
        target = 0
        for row, (app_id, text) in enumerate(entries):
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, app_id)
            item.setToolTip(text)
            item.setSizeHint(QSize(0, 54 if app_id is not None else 34))
            if app_id in self.apps:
                app = self.apps[app_id]
                item.setIcon(app_icon(app.color, app.initial))
            self.sidebar.addItem(item)
            if app_id == selected:
                target = row
        self.sidebar.setCurrentRow(target)
        self.sidebar.blockSignals(False)
        self._select_scope(self.sidebar.currentItem())

    def _select_scope(self, current, _previous=None):
        self.projects.app_id = current.data(Qt.UserRole) if current else None
        self.projects.refresh()

    def selected_app(self):
        item = self.tools.item(self.tools.currentRow(), 0)
        return self.apps.get(item.data(Qt.UserRole)) if item else None

    def _update_actions(self):
        app = self.selected_app()
        idle = app is not None and not self._workers and self._install is None and not self.launcher.running(app.app_id)
        state = self.states.get(app.app_id) if app else None
        self.install_button.setEnabled(idle and not (state and state.kind == "Managed" and state.available and state.version == app.version))
        self.link_button.setEnabled(idle)
        self.unlink_button.setEnabled(idle and app.app_id in self.installations.linked)
        self.remove_button.setEnabled(idle and self.installations.managed_python(app).is_file())
        self.repository_button.setEnabled(app is not None)
        self.projects.new_button.setEnabled(not self._workers and self._install is None and bool(self.projects._available_apps_for_dialog()))
        self.tool_description.setText((app.description + (f"\n{state.error}" if state and state.error else "")) if app else "Select an application.")

    def show_app(self, app_id):
        self.tabs.setCurrentWidget(self.tools_page)
        for row in range(self.tools.rowCount()):
            if self.tools.item(row, 0).data(Qt.UserRole) == app_id:
                self.tools.selectRow(row)
                break

    def open_project(self, project_id):
        if self._workers or self._install is not None:
            self.statusBar().showMessage("Wait for the current operation to finish before opening a project.", 5000)
            return
        try:
            project = self.backend.get_project(project_id)
        except Exception as exc:
            self._error(f"Could not read the project:\n{exc}")
            return
        app = self.apps.get(project.app_id)
        if app is None:
            self.show_app(project.app_id)
            self._error(f"The app '{project.app_id}' is not in the reviewed catalog. The project has been kept.")
            return
        def opened(state):
            if not state.available:
                self.show_app(app.app_id)
                self._error(f"{app.name} is not installed or is unavailable. Install it or link its Python in Apps.\n\n{state.error}")
                return
            try:
                self.launcher.start(app, state, project_id)
            except (OSError, RuntimeError) as exc:
                self._launch_failed(app.app_id, str(exc))
                return
            self.statusBar().showMessage(f"Opening {project.name} with {app.name}…", 5000)
            self._update_actions()
        self._run(lambda: self.installations.inspect(app), opened)

    def _launch_failed(self, app_id, message):
        self.show_app(app_id)
        self._error(f"Could not run {self._app_name(app_id)}.\n\n{message}")
        self._update_actions()

    def install_selected(self):
        app = self.selected_app()
        if app is None or self._install is not None:
            return
        if self.launcher.running(app.app_id):
            self._error("Close this app before changing its managed environment.")
            return
        self.install_log.clear()
        self.install_log.show()
        try:
            self._install = self.installations.install(app, busy=lambda: "The app is running." if self.launcher.running(app.app_id) else "")
        except Exception as exc:
            self._error(str(exc))
            return
        self._install_app = app
        self._log_position = 0
        self._update_actions()
        self.install_timer.start()

    def _poll_install(self):
        install = self._install
        if install is None:
            return
        lines = install.lines[self._log_position:]
        self._log_position += len(lines)
        if lines:
            self.install_log.appendPlainText("\n".join(lines))
        self.statusBar().showMessage(f"{self._install_app.name}: {install.step or 'Installing'} ({install.done}/{install.total})")
        if not install.future.done():
            return
        self.install_timer.stop()
        app = self._install_app
        self._install = None
        try:
            install.future.result()
            self.installations.unlink(app.app_id)
        except Exception as exc:
            self._error(str(exc))
        self.refresh()

    def link_selected(self):
        app = self.selected_app()
        if app is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, f"Select the Python where {app.name} is installed")
        if path:
            self._run(lambda: self.installations.link(app, Path(path)), lambda _result: self.refresh())

    def unlink_selected(self):
        app = self.selected_app()
        if app:
            try:
                self.installations.unlink(app.app_id)
            except OSError as exc:
                self._error(str(exc))
                return
            self.refresh()

    def remove_selected(self):
        app = self.selected_app()
        if app is None:
            return
        if self.launcher.running(app.app_id):
            self._error("Close this app before uninstalling it.")
            return
        answer = QMessageBox.question(self, "Uninstall app", f"Remove the Toolbox-managed installation of {app.name}? Close all instances of the app first.\n\nProjects and settings will be kept. Linked environments will be left untouched.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            self._run(lambda: self.installations.remove(app), self._removed)

    def _removed(self, removed):
        if not removed:
            self._error("This environment is not owned by Toolbox. It was left untouched.")
        self.refresh()

    def open_repository(self):
        app = self.selected_app()
        if app:
            QDesktopServices.openUrl(QUrl(app.repository))

    def _rebuild_settings_tabs(self):
        while self.settings_tabs.count() > 1:
            self.settings_tabs.widget(1).deleteLater()
            self.settings_tabs.removeTab(1)
        self._settings_pages.clear()
        for app in self.apps.values():
            if not app.configurations:
                continue
            page = QWidget(self)
            layout = QVBoxLayout(page)
            label = QLabel("Select this tab to load global settings from the app's registered environment.")
            label.setWordWrap(True)
            layout.addWidget(label)
            layout.addStretch()
            self._settings_pages[page] = (app, False)
            self.settings_tabs.addTab(page, app.name)

    def _load_settings(self, index):
        page = self.settings_tabs.widget(index)
        if page not in self._settings_pages:
            return
        app, loaded = self._settings_pages[page]
        if loaded:
            return
        state = self.states.get(app.app_id)
        if not state or not state.available:
            page.layout().itemAt(0).widget().setText(f"Install or link {app.name} in Apps to edit its settings.")
            return
        self._settings_pages[page] = (app, True)
        page.layout().itemAt(0).widget().setText(f"Loading {app.name} settings…")
        def loaded_settings(configurations):
            if page not in self._settings_pages:
                return
            label = page.layout().itemAt(0).widget()
            label.setText(f"{app.name} {state.version} · {state.python}\nGlobal settings; project overrides remain in their projects.")
            panel = SettingsPanel(configurations=configurations, app_name=app.name, parent=page)
            page.layout().insertWidget(1, panel, 1)
        def failed_settings(message):
            if page in self._settings_pages:
                self._settings_pages[page] = (app, False)
                page.layout().itemAt(0).widget().setText(f"Could not load settings: {message}\nSelect this tab again to retry.")
            self._error(message)
        self._run(lambda: [AppConfiguration(state.python, factory) for factory in app.configurations], loaded_settings, failed_settings)

    def closeEvent(self, event):
        if self._workers or self._install is not None:
            self.statusBar().showMessage("Wait for the current operation to finish before closing Toolbox.", 5000)
            event.ignore()
            return
        self.backend.shutdown()
        self.workspace.shutdown()
        super().closeEvent(event)

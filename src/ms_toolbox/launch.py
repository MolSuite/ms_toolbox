from __future__ import annotations

import subprocess
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, QTimer, Signal

from ms_toolbox.installations import app_environment


class LaunchManager(QObject):
    failed = Signal(str, str)
    finished = Signal(str)

    def __init__(self, home: Path, parent=None):
        super().__init__(parent)
        self.home = home
        self.processes = []
        self.timer = QTimer(self)
        self.timer.setInterval(300)
        self.timer.timeout.connect(self.poll)

    def running(self, app_id):
        # shortcut: tracks this Toolbox session; add cross-process leases before supporting unattended environment updates.
        return any(key == app_id and process.poll() is None for key, process, _ in self.processes)

    def start(self, app, installation, project_id):
        if not installation.available:
            raise RuntimeError(f"{app.name} is not installed or its environment is unavailable.")
        self.home.mkdir(parents=True, exist_ok=True)
        log_path = self.home / f"{app.app_id}-{uuid4().hex}.log"
        # A file avoids a full stderr pipe blocking the app. Popen keeps apps alive when Toolbox exits.
        with log_path.open("wb") as log:
            process = subprocess.Popen(
                [str(installation.python), "-I", "-m", app.package, "--project-id", str(project_id)],
                stdout=log, stderr=subprocess.STDOUT, env=app_environment(installation.python),
                start_new_session=True,
            )
        self.processes.append((app.app_id, process, log_path))
        self.timer.start()
        return process

    def poll(self):
        active = []
        for app_id, process, log_path in self.processes:
            code = process.poll()
            if code is None:
                active.append((app_id, process, log_path))
                continue
            if code:
                try:
                    with log_path.open("rb") as log:
                        log.seek(0, 2)
                        size = log.tell()
                        log.seek(max(0, size - 6000))
                        detail = log.read().decode("utf-8", errors="replace").strip()
                except OSError as exc:
                    detail = str(exc)
                self.failed.emit(app_id, f"The app exited with code {code}.\n\n{detail}\n\nLog: {log_path}")
            self.finished.emit(app_id)
        self.processes = active
        if not active:
            self.timer.stop()

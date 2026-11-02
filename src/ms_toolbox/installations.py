from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from ms_env import ensure, remove

from ms_toolbox.catalog import CatalogApp


def app_environment(python: Path) -> dict[str, str]:
    env = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
        env.pop(name, None)
    env["PATH"] = str(python.parent) + os.pathsep + env.get("PATH", "")
    return env


def bridge_call(python: Path, request: dict):
    result = subprocess.run(
        [str(python), "-I", str(Path(__file__).with_name("_bridge.py"))],
        input=json.dumps(request), text=True, capture_output=True,
        env=app_environment(python), timeout=30,
    )
    try:
        response = json.loads(result.stdout)
    except ValueError as exc:
        raise RuntimeError(result.stderr.strip() or "The selected Python did not return a valid response.") from exc
    if result.returncode:
        raise RuntimeError(response.get("error") or result.stderr.strip() or "The app's Python failed.")
    return response


@dataclass(frozen=True)
class Installation:
    python: Path | None = None
    version: str = ""
    kind: str = "Not installed"
    error: str = ""

    @property
    def available(self):
        return bool(self.python and self.version and not self.error)


class Installations:
    def __init__(self, home: Path):
        self.home = home
        self.path = home / "installations.json"
        self.linked = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        if not isinstance(self.linked, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in self.linked.items()):
            raise ValueError(f"Invalid installation registry: {self.path}")

    def managed_python(self, app: CatalogApp):
        prefix = Path(app.recipe(self.home).prefix)
        return prefix / ("python.exe" if sys.platform == "win32" else "bin/python")

    def inspect(self, app: CatalogApp) -> Installation:
        if app.app_id in self.linked:
            candidates = [(Path(self.linked[app.app_id]), "Linked")]
        else:
            candidates = [(self.managed_python(app), "Managed"), (Path(sys.executable), "Current environment")]
        for python, kind in candidates:
            if not python.is_file():
                if kind == "Linked":
                    return Installation(python=python, kind=kind, error="The linked Python no longer exists.")
                continue
            try:
                data = bridge_call(python, {"action": "probe", "distribution": app.distribution, "package": app.package})
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                return Installation(python=python, kind=kind, error=str(exc))
            if data["version"] or kind == "Linked":
                return Installation(python, data["version"], kind, data["error"] or ("The app is not installed in the linked environment." if not data["version"] else ""))
        return Installation()

    def _save(self, linked):
        self.home.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(linked, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)
        self.linked = linked

    def link(self, app: CatalogApp, python: Path):
        python = python.expanduser().absolute()
        data = bridge_call(python, {"action": "probe", "distribution": app.distribution, "package": app.package})
        if not data["version"] or data["error"]:
            raise ValueError(data["error"] or f"{app.name} is not installed in this environment.")
        self._save({**self.linked, app.app_id: str(python)})

    def unlink(self, app_id: str):
        self._save({k: v for k, v in self.linked.items() if k != app_id})

    def install(self, app: CatalogApp, busy=None):
        return ensure(app.recipe(self.home), busy=busy)

    def remove(self, app: CatalogApp):
        return remove(app.recipe(self.home))

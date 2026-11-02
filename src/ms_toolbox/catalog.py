from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from urllib.parse import urlparse

from ms_env import ToolSpec
from ms_flow.api import AppManifest


@dataclass(frozen=True)
class CatalogApp:
    app_id: str
    name: str
    description: str
    distribution: str
    version: str
    package: str
    scope: str
    repository: str
    color: str
    initial: str
    configurations: tuple[str, ...] = ()

    def __post_init__(self):
        if not re.fullmatch(r"[a-z][a-z0-9_]*", self.app_id):
            raise ValueError(f"Invalid app id: {self.app_id}")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", self.distribution):
            raise ValueError("Use a distribution name, not a URL or pip option.")
        if not re.fullmatch(r"[0-9][A-Za-z0-9_.+!-]*", self.version):
            raise ValueError("An app must pin its reviewed release.")
        if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", self.package):
            raise ValueError("Invalid launch package.")
        if not self.name.strip() or not self.scope.strip():
            raise ValueError("App name and scope are required.")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", self.color) or len(self.initial) != 1:
            raise ValueError("Apps need a color and a one-character icon.")
        url = urlparse(self.repository)
        if url.scheme != "https" or not url.hostname:
            raise ValueError("The repository must be an HTTPS URL.")
        for factory in self.configurations:
            if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*", factory):
                raise ValueError(f"Invalid configuration factory: {factory}")

    def manifest(self) -> AppManifest:
        return AppManifest(
            app_id=self.app_id, scope_id=self.scope, name=self.name,
            version=self.version, description=self.description, package_name=self.package,
        )

    def recipe(self, home: Path):
        return ToolSpec(
            name=self.app_id, version=self.version, info={"label": self.name},
            prefix="{tools_home}/apps/{name}", paths=("{python}",), commands=(),
            check=("{exe}", "-I", "-c", f"import {self.package}; import importlib.metadata as m; assert m.version({self.distribution!r}) == {self.version!r}"),
            conda=("python=3.12", "pip"), pip=(f"{self.distribution}=={self.version}",),
        ).recipe(str(home))


def load_catalog(directory=None) -> dict[str, CatalogApp]:
    directory = directory or files("ms_toolbox").joinpath("catalog")
    apps = {}
    for path in sorted(directory.iterdir(), key=lambda p: p.name):
        if not path.name.endswith(".toml"):
            continue
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        data["configurations"] = tuple(data.get("configurations", ()))
        app = CatalogApp(**data)
        if app.app_id in apps:
            raise ValueError(f"Duplicate catalog app: {app.app_id}")
        apps[app.app_id] = app
    return apps

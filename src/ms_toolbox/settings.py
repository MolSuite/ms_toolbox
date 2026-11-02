from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from ms_components.palettes import THEMES
from ms_flow.api import ConfigurationEntry, PydanticConfiguration

from ms_toolbox.installations import bridge_call


class Appearance(BaseModel):
    theme: str = Field("auto", json_schema_extra={"choices": ["auto", *sorted(THEMES)]})
    font_size: float = Field(11, ge=8, le=24, title="Font size (pt)")


class ToolboxSettings(BaseModel):
    appearance: Appearance = Field(default_factory=Appearance)


def toolbox_configuration(home: Path):
    return PydanticConfiguration(
        config_id="ms_toolbox", display_name="MolSuite Toolbox",
        model_type=ToolboxSettings, global_path=home / "config.toml",
        description="Appearance of MolSuite Toolbox. Application settings keep their own providers and files.",
    )


class AppConfiguration:
    """Expose a MolSuite provider in its app's interpreter to the shared editor."""

    has_project = False
    project_path = None
    icon_name = None

    def __init__(self, python: Path, factory: str):
        self.python = python
        self.factory = factory
        self._update(bridge_call(python, {"action": "snapshot", "factory": factory}))

    def _update(self, data):
        self.data = data
        self.config_id = data["config_id"]
        self.display_name = data["display_name"]
        self.description = data["description"]
        self.global_path = Path(data["global_path"])
        self.default_path = Path(data["default_path"]) if data["default_path"] else None

    def entries(self):
        annotations = {"bool": bool, "int": int, "float": float, "str": str, "path": Path, "list": list[str], "dict": dict[str, object], "tuple": tuple[object, ...], "set": set[str]}
        return tuple(ConfigurationEntry(**{**entry, "annotation": annotations[entry["annotation"]], "choices": tuple(entry["choices"])}) for entry in self.data["entries"])

    def get_value(self, path):
        return self.data["values"][path]

    def get_source(self, path):
        return self.data["sources"][path]

    def set_global_value(self, path, value):
        self._update(bridge_call(self.python, {"action": "set", "factory": self.factory, "path": path, "value": value}))

    def reset_value(self, path, target: Literal["default"]):
        self._update(bridge_call(self.python, {"action": "reset", "factory": self.factory, "path": path, "target": target}))

    def reload(self):
        self._update(bridge_call(self.python, {"action": "snapshot", "factory": self.factory}))

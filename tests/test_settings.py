import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, Field
from ms_flow.api import PydanticConfiguration

from ms_toolbox import _bridge
from ms_toolbox.settings import AppConfiguration, toolbox_configuration


class Preferences(BaseModel):
    cpus: int = Field(2, ge=1, le=8)
    names: list[str] = Field(default_factory=list)


def test_settings_use_the_app_provider_for_validation_and_persistence(tmp_path, monkeypatch):
    def provider():
        return PydanticConfiguration(config_id="test_app", display_name="Test App", model_type=Preferences, global_path=tmp_path / "app.toml")
    monkeypatch.setitem(sys.modules, "test_provider", SimpleNamespace(create=provider))
    monkeypatch.setattr("ms_toolbox.settings.bridge_call", lambda python, request: _bridge.handle(request))
    configuration = AppConfiguration(Path(sys.executable), "test_provider:create")
    assert configuration.entries()[0].annotation is int
    assert configuration.get_value("cpus") == 2
    configuration.set_global_value("cpus", 4)
    assert provider().get_value("cpus") == 4
    assert configuration.get_source("cpus") == "global"
    with pytest.raises(ValueError):
        configuration.set_global_value("cpus", 99)
    assert provider().get_value("cpus") == 4
    configuration.set_global_value("names", ["one", "two"])
    assert provider().get_value("names") == ["one", "two"]
    configuration.reset_value("cpus", "default")
    assert provider().get_value("cpus") == 2


def test_shared_settings_editor_can_edit_remote_configuration(qapp, tmp_path, monkeypatch):
    from ms_components.ms_settings import AppSettingsPanel
    def provider():
        return PydanticConfiguration(config_id="test_app", display_name="Test App", model_type=Preferences, global_path=tmp_path / "app.toml")
    monkeypatch.setitem(sys.modules, "test_provider", SimpleNamespace(create=provider))
    monkeypatch.setattr("ms_toolbox.settings.bridge_call", lambda python, request: _bridge.handle(request))
    configuration = AppConfiguration(Path(sys.executable), "test_provider:create")
    panel = AppSettingsPanel(configurations=[configuration])
    panel.editor("test_app", "cpus").setValue(5)
    panel.save_settings()
    assert provider().get_value("cpus") == 5
    panel.close()


def test_toolbox_settings_use_existing_theme_choices(tmp_path):
    config = toolbox_configuration(tmp_path)
    entry = next(e for e in config.entries() if e.path == "appearance.theme")
    assert "auto" in entry.choices and "dracula" in entry.choices

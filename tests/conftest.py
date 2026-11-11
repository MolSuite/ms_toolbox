import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pydantic.fields  # Load before Shiboken's feature importer.
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("MOLSUITE_HOME", str(tmp_path / "molsuite"))
    monkeypatch.setenv("MS_FLOW_WORKSPACE_ROOT", str(tmp_path / "empty"))

from __future__ import annotations

import argparse
import sys
from importlib.resources import files
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description="MolSuite Toolbox")
    parser.add_argument("--install-desktop-entry", action="store_true", help="Install a Linux desktop shortcut for this Python environment.")
    args = parser.parse_args(argv)
    if args.install_desktop_entry:
        return install_desktop_entry()

    import pydantic.fields  # Load before Shiboken's feature importer.
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox
    from ms_toolbox.window import ToolboxWindow

    app = QApplication(sys.argv[:1])
    app.setApplicationName("MolSuite Toolbox")
    app.setOrganizationName("MolSuite")
    app.setWindowIcon(QIcon(str(files("ms_toolbox").joinpath("resources/molsuite.svg"))))
    try:
        window = ToolboxWindow()
    except Exception as exc:
        QMessageBox.critical(None, "MolSuite Toolbox", str(exc))
        return 1
    window.show()
    return app.exec()


def install_desktop_entry():
    import os

    if sys.platform != "linux":
        raise SystemExit("Desktop entries are supported on Linux. Use molsuite on this platform.")
    if any(character in sys.executable for character in "=\n\r\t"):
        raise SystemExit("The desktop shortcut requires a Python path without '=' or line breaks/tabs.")
    home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    resources = files("ms_toolbox").joinpath("resources")
    applications = home / "applications"
    icons = home / "icons/hicolor/scalable/apps"
    applications.mkdir(parents=True, exist_ok=True)
    icons.mkdir(parents=True, exist_ok=True)
    # Exec has its own escaping rules; do not assume the environment is on the desktop's PATH.
    def quote(value):
        escaped = str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
        # The Desktop Entry string parser unescapes once before Exec unquotes the argument.
        return '"' + escaped.replace('\\', '\\\\') + '"'
    entry = resources.joinpath("molsuite.desktop").read_text(encoding="utf-8")
    entry = entry.replace("Exec=molsuite", f"Exec={quote(sys.executable)} -m ms_toolbox")
    (applications / "molsuite.desktop").write_text(entry, encoding="utf-8")
    (icons / "molsuite.svg").write_bytes(resources.joinpath("molsuite.svg").read_bytes())
    print(applications / "molsuite.desktop")
    return 0

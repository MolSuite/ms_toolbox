# MolSuite Toolbox

An independent desktop app for MolSuite applications, projects and settings. Shared
project APIs stay in `ms_flow`; project and settings widgets stay in `ms_components`.
AMDockVS does not need Toolbox installed to create or open its projects.

## Install and run

Python 3.12 or newer is required. From this repository:

```bash
python -m pip install .
ms-toolbox
```

The module entry point works too: `python -m ms_toolbox`.
This installs a graphical launcher in the selected Python environment, rather than
a standalone binary with its own Python runtime.

On Linux, add a shortcut to the desktop's application menu:

```bash
ms-toolbox --install-desktop-entry
```

The shortcut points to that environment's Python, so it works even when the
environment is not on the desktop's `PATH`. Windows and macOS use the installed
`ms-toolbox` launcher; native application bundles are not provided yet.

## Applications and installations

The catalog is bundled with the package and updated through reviewed pull requests.
There is no GitHub search, arbitrary plugin discovery, or scanning of users' conda
environments. An application is available for project creation only when its
distribution and launch module are present in one of these places:

1. A Python interpreter explicitly linked for that app in **Apps → Link Python…**.
2. The app's Toolbox-managed environment.
3. The Python environment running Toolbox.

An explicitly linked interpreter takes priority. A broken link is shown as an error
instead of silently switching to another installation. A source checkout without
installed distribution metadata is not an installed app. Launching uses `-I`, so a
neighboring repository or inherited `PYTHONPATH` cannot masquerade as an installation.

**Install catalog version** uses `ms_env` to install the reviewed, pinned release
into a separate managed environment. `ms_env` supplies/downloads micromamba as needed.
This operation needs network access and may download substantial scientific dependencies.
It does not install into or modify an environment linked by the user.

**Uninstall managed app** also delegates to `ms_env`: an environment without its
ownership stamp is left untouched. Unlinking only removes the registration. Neither
operation deletes projects or app settings.

Close every instance of an app before replacing or removing its managed environment.
Toolbox blocks changes for app processes started in its current session; processes
started elsewhere or surviving an earlier Toolbox session are not tracked yet.

## Projects

Toolbox uses `ProjectCatalogBackend` and `ProjectsMenuWidget`, with automatic workspace
discovery disabled. The shared MolSuite project catalog remains the source of truth.
In **All apps**, the table shows an **Application** column and stable app colors.
Selecting an app hides that redundant column. Apps absent from the reviewed catalog
still retain their projects and can be filtered by their stored app id.

Double-clicking a project starts its app with the selected interpreter and
`--project-id`. Toolbox stays open, watches the process and reports later failures
with the log path. If the app is missing, the error takes the user to its **Apps**
entry to install or link it. Process creation is not treated as proof of successful
app initialization.

## Settings and themes

The **Settings** page reuses `AppSettingsPanel`. It groups MolSuite and Toolbox settings
separately from each catalog app's settings. Toolbox uses the existing `ms_components`
themes without a fixed violet shell.
The shared Hosts and Executors pages use `KeptPage` and the MolSuite `Workspace`
APIs, including local CPU/GPU limits. They do not start execution pools merely by
opening the settings page. Close apps before changing their shared resource settings.

App providers run in their registered Python environment, using a small subprocess
bridge. The Toolbox package does not have to be installed there. Values are validated,
saved and reset by the app's own MolSuite configuration provider. Toolbox does not
rewrite another app's TOML itself or start its scientific runtime to load preferences.
The initial AMDockVS entry exposes its AMDock and contact-map configuration providers.
App-specific UI pages such as downloads or tool installation stay in their app.

Only global settings are edited here. Project-specific overrides remain in their
projects. Changing MolSuite's project catalog path takes effect after restarting
Toolbox.

## Contributing an app

Add one TOML file to [`src/ms_toolbox/catalog`](src/ms_toolbox/catalog), following
[`amdockvs.toml`](src/ms_toolbox/catalog/amdockvs.toml). The entry declares:

- A stable app id, name, scope and launch package.
- Its published distribution and the exact release reviewed for installation.
- An HTTPS repository URL, stable color and single-character icon.
- Optional configuration factories, written as `module:callable`.

Each configuration factory takes no arguments and returns a MolSuite configuration
provider, such as `PydanticConfiguration`. It must be lightweight and work without an
open project. The app must accept `python -m <package> --project-id <id>`.

A PR must identify the maintained repository, release, license and supported platforms,
and show that opening a project and editing global settings work. Review confirms the
declared integration, not every behavior of the contributed application. Catalog
entries execute installed app code when opening apps or settings and must be reviewed
accordingly. Updating an app's approved release uses another PR; Toolbox does not
guess whether a newer release is compatible.

## Compatibility before v1

This first version deliberately does not invent a project migration policy. The app
and MolSuite components remain responsible for validating their data formats. Toolbox
neither claims that an older app can open a newer project nor downgrades projects.
The catalog's approved app version is an installation choice, not the recorded creator
version of a project. A full format/migration contract remains shared work before v1.

The shared UI and runtime dependencies are bounded to the tested pre-v1 minor versions.
Widening those bounds requires running the tests against the new releases.

## Development

In the project's `MSDD_312` environment:

```bash
python -m pip install -e '.[dev]'
QT_QPA_PLATFORM=offscreen python -m pytest -q
python -m build
```

Tests cover curated catalog validation, explicit interpreter linking, late launch
failures, preserving projects after uninstall, the All-apps column, missing-app
navigation, and provider-based settings validation/persistence. They do not perform
real scientific-app installations or modify user environments.

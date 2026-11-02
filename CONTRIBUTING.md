# Contributing

Application integrations are proposed through pull requests to the bundled
[catalog](src/ms_toolbox/catalog). Include the repository, published release,
license, platforms and a reproducible check of project opening and global settings.
See the [catalog contract](README.md#contributing-an-app).

Do not add environment scans, install unpinned app releases, or duplicate project,
environment or configuration persistence already provided by MolSuite APIs.

For code changes, run the offscreen tests and build the wheel. Keep shared widgets
in `ms_components` and orchestration/project APIs in `ms_flow`. A fix to a shared
component belongs in that component's repository, with its callers checked.

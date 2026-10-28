# Contributing

Resolve Time Tracker is early, so small focused changes are preferred.

## Setup

Follow the [Development Guide](docs/development.md) for local setup and the Resolve development-menu workflow. If you are preparing the repository with an AI coding agent, use the [Agentic Development Prompt](docs/agentic-development-prompt.md).

## Test

Run the Python and frontend checks in the [Development Guide](docs/development.md#run-checks). It also covers focused tests and formatting; verification commands check formatting without changing files.

## Git and Releases

Use [development for integration and main for reviewed release source](docs/branch-workflow.md). Follow the [release policy](docs/releasing.md) for compatibility, version selection, and release preparation.

## Development Notes

- Keep runtime dependencies minimal. Prefer Python standard library.
- Keep tracking privacy-preserving: no keystroke logging, mouse-coordinate logging, screen capture, footage inspection, or cloud sync.
- Add a focused test for behavior changes.
- Keep platform-specific code behind small probes or helpers.
- Update README only for user-facing behavior; put project planning in `docs/roadmap.md`.

## Platform Changes

When changing install or activity detection code, check:

- Windows installer and Resolve menu path.
- macOS Resolve menu path and scripting API path.
- Linux Resolve menu path, scripting API path, and `xprintidle`/`xdotool` behavior.

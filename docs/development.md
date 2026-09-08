# Development Guide

## Prerequisites

- Git
- `uv`
- Node.js with pnpm
- DaVinci Resolve Studio for live integration testing

The project supports Python 3.10 through 3.13. Installer and development examples use Python 3.13.

## Repository Map

```text
frontend/   Electron shell, React dashboard, shadcn/ui, and frontend tests
scripts/    Resolve menu installer and runtime launcher
src/        Python tracking, Resolve integration, local API, exports, and SQLite
tests/      Python unit and integration tests
docs/       Architecture decisions, research, support, and contributor guides
install.*   User-facing bootstrap installers
uninstall.* User-facing uninstallers
```

## Set Up

From the repository root:

```powershell
uv sync --python 3.13
cd frontend
pnpm install --frozen-lockfile
cd ..
```

## Run the Desktop App

```powershell
cd frontend
pnpm run desktop:dev
```

Electron opens the dashboard and connects to the shared runtime. Start a tracked editing session with `uv run --python 3.13 scripts/ResolveTimeTracker.py --tracked-launch`. Without tracking, the dashboard starts temporary read-only reporting.

### Launch development mode from Resolve

Install this checkout's Resolve menu entries:

```powershell
uv run --python 3.13 scripts/install_resolve_menu.py
```

Restart Resolve, then choose **Workspace > Scripts > ResolveTimeTrackerDevMenu**. This starts Vite and Electron in development mode, so frontend source changes hot-reload without rebuilding `frontend/dist`.

Use **ResolveTimeTrackerMenu** to attach tracking to the open Resolve session. Close the dashboard before switching desktop launch modes. Close Resolve before replacing Python runtime code. Vite hot reload applies only to renderer source.

If the development entry is missing, rerun the installer above and restart Resolve. If startup fails, run `pnpm run desktop:dev` from `frontend/` to keep the error visible.

## Run Checks

Python, from the repository root:

```powershell
uv run --python 3.13 ruff format --check .
uv run --python 3.13 ruff check .
uv run --python 3.13 -m pytest -q
```

Frontend, from `frontend/`:

```powershell
pnpm run lint
pnpm run typecheck
pnpm test
pnpm run build
```

Format changed frontend files with `pnpm run format`.

## Run Individual Layers

Start the Python API and tracker without Electron:

```powershell
uv run --python 3.13 scripts/ResolveTimeTracker.py --tracked-launch
```

The runtime publishes its loopback port in `tracker.runtime.json` beside the database. That file contains a private lifecycle token; do not share it. No fixed port or dormant watcher is needed.

Run a packaged-style desktop smoke test after building the frontend:

```powershell
cd frontend
pnpm run build
pnpm run desktop:smoke
```

Use `--db path/to/test.sqlite3` when development should not touch normal tracking history.

Run the five-minute synthetic benchmark with `uv run --python 3.13 scripts/benchmark_runtime.py --output benchmark-runtime.json`. It measures the real runtime with synthetic Active Work, not Resolve scripting performance. The temporary database and simulated Resolve process are discarded. CPU and memory are reported, not CI thresholds.

## Architecture

- [Electron and Python sidecar decision](adr/0001-electron-shadcn-ui-python-sidecar.md)
- [Platform support](platform-support.md)
- [Project roadmap](roadmap.md)
- [Domain language](../CONTEXT.md)

See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution rules and platform-change checks.

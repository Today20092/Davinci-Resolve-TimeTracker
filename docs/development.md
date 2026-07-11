# Development Guide

## Prerequisites

- Git
- `uv`
- Node.js with npm
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
npm ci
cd ..
```

## Run the Desktop App

```powershell
cd frontend
npm run desktop:dev
```

Electron starts the Python tracker and opens the React development server. DaVinci Resolve must be running with a project open to show live project activity.

## Run Checks

Python, from the repository root:

```powershell
uv run --python 3.13 ruff format --check .
uv run --python 3.13 ruff check .
uv run --python 3.13 -m unittest discover -s tests
```

Frontend, from `frontend/`:

```powershell
npm run lint
npm run typecheck
npm test
npm run build
```

Format changed frontend files with `npm run format`.

## Run Individual Layers

Start the Python API and tracker without Electron:

```powershell
uv run --python 3.13 scripts/ResolveTimeTracker.py --api
```

Its local API is available at `http://127.0.0.1:8765`; interactive FastAPI documentation is at `/docs`.

Run a packaged-style desktop smoke test after building the frontend:

```powershell
cd frontend
npm run build
npm run desktop:smoke
```

Use `--db path/to/test.sqlite3` when development should not touch normal tracking history.

## Architecture

- [Electron and Python sidecar decision](adr/0001-electron-shadcn-ui-python-sidecar.md)
- [Platform support](platform-support.md)
- [Project roadmap](roadmap.md)
- [Domain language](../CONTEXT.md)

See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution rules and platform-change checks.

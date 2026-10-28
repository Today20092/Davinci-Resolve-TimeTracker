# Resolve Time Tracker

Privacy-preserving billable editing-time tracking for DaVinci Resolve Studio, with a Python runtime, SQLite storage, and an Electron dashboard.

## Development

For setup, repository structure, running the app, testing, linting, or builds, read the [Development Guide](docs/development.md). Before changing code, read [CONTRIBUTING.md](CONTRIBUTING.md) for contribution, privacy, and platform rules.

Before running live tracking or replacing runtime code, read [runtime and data safety](docs/development.md#runtime-and-data-safety) for test databases, private runtime tokens, and process shutdown.

For branch setup, integration, promotion, or cleanup, read the [Git workflow](docs/branch-workflow.md). For version selection, release-status wording, or release preparation, read the [release policy](docs/releasing.md).

## Agent skills

### Issue tracker

Issues and PRDs are tracked in GitHub Issues; external PRs are not a triage surface. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default triage label vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repo with root `CONTEXT.md` and ADRs under `docs/adr/`. See `docs/agents/domain.md`.

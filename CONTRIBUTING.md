# Contributing

Resolve Time Tracker is early, so small focused changes are preferred.

## Setup

```sh
uv sync
```

## Test

```sh
uv run -m unittest discover -s tests
```

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

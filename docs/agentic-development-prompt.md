# Agentic Development Prompt

Copy the prompt below into an AI coding agent with terminal access. Review every command before allowing it to modify your computer.

```text
Prepare a safe local development checkout of Resolve Time Tracker from
https://github.com/Today20092/Davinci-Resolve-TimeTracker.

1. Detect the operating system and whether the current directory is already the repository.
2. Before changing anything, inspect git status and preserve all repository files, branches, commits, tracked-time data, and unrelated worktree changes. Never reset, clean, overwrite, or delete them. The generated ResolveTimeTrackerMenu.py and ResolveTimeTrackerDevMenu.py launchers may be refreshed by the documented installer.
3. Verify Git, Node.js with npm, uv, and DaVinci Resolve Studio. Report a missing prerequisite instead of silently installing system-wide software.
4. Clone the repository only if it is not already present. Otherwise fetch safely and do not change branches or pull across local work without my approval.
5. From the repository root, run:
   uv sync --python 3.13
   cd frontend
   npm ci
6. Return to the repository root and install the Resolve menu launchers with:
   uv run --python 3.13 scripts/install_resolve_menu.py
7. Run the documented Python and frontend checks in docs/development.md. Do not hide failures behind later successful commands.
8. Verify that both ResolveTimeTrackerMenu.py and ResolveTimeTrackerDevMenu.py exist in this platform's DaVinci Resolve Utility scripts directory and that both reference the current checkout path.
9. Do not open, replace, upload, or delete tracker.sqlite3. Do not enable automatic startup unless I explicitly request it.
10. Report the checkout path, tool versions, check results, installed menu paths, and any manual steps still needed. Tell me to restart Resolve and launch Workspace > Scripts > ResolveTimeTrackerDevMenu for Vite hot reload.
```

The deterministic setup commands remain authoritative. This prompt only helps an agent run them carefully and explain failures.

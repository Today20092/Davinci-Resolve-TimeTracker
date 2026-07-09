# Electron shadcn UI with Python sidecar

Resolve Time Tracker will replace the Tkinter companion UI with an Electron desktop window using a Vite React, Tailwind, and shadcn/ui frontend, while keeping the existing Python code as the tracking engine sidecar. Electron owns presentation only; Python continues to own Resolve integration, SQLite storage, session logic, CSV export, and local runtime state. The sidecar HTTP API will live in a new `api.py` module instead of reusing the old Tkinter UI module, and it will use FastAPI rather than hand-rolled stdlib HTTP.

The app will prefer predictable cross-platform installation over small bundle size. Electron will launch the Python sidecar locally, the UI will call a localhost REST API for commands and queries, and Python will stream live status updates to the UI with server-sent events. The first install target can assume technical users are willing to run a repo install script; polished signed installers can come later if distribution demands it.

The existing Resolve Scripts menu flow remains the user entry point. Once the Electron UI exists, `--companion` will launch Electron instead of Tkinter.
